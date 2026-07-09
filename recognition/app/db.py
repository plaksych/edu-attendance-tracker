"""Очередь recognition_jobs в PostgreSQL: claim, heartbeat, фиксация результата."""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, TypeVar

import psycopg2
import psycopg2.extensions

from app.config import settings

if TYPE_CHECKING:
    from app.processor import ProcessingResult

logger = logging.getLogger(__name__)

T = TypeVar("T")

CLAIM_SQL = """
WITH selected AS (
    SELECT id FROM recognition_jobs
    WHERE status = 'pending'
    ORDER BY created_at, id
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
UPDATE recognition_jobs job
SET status = 'processing',
    worker_id = %s,
    lease_until = now() + make_interval(mins => %s),
    heartbeat_at = now(),
    attempts = attempts + 1,
    started_at = COALESCE(started_at, now()),
    updated_at = now()
FROM selected
WHERE job.id = selected.id
RETURNING job.id, job.camera_capture_id, job.upload_id, job.sample_rate_fps,
    job.confidence_threshold, job.attempts
"""

SOURCE_CONTEXT_SQL = """
SELECT
    CASE WHEN job.upload_id IS NULL THEN 'capture' ELSE 'upload' END AS source_kind,
    CASE WHEN job.upload_id IS NULL THEN 'video' ELSE ru.media_type::text END AS media_type,
    COALESCE(cc.original_bucket, ru.original_bucket) AS original_bucket,
    COALESCE(cc.original_object_key, ru.original_object_key) AS original_object_key,
    COALESCE(ru.filename, cc.original_object_key) AS filename,
    cc.camera_id,
    cc.measurement_id,
    measurement.session_id,
    ru.id
FROM recognition_jobs job
LEFT JOIN camera_captures cc ON cc.id = job.camera_capture_id
LEFT JOIN measurements measurement ON measurement.id = cc.measurement_id
LEFT JOIN recognition_uploads ru ON ru.id = job.upload_id
WHERE job.id = %s
"""

HEARTBEAT_SQL = """
UPDATE recognition_jobs
SET heartbeat_at = now(),
    lease_until = now() + make_interval(mins => %s),
    updated_at = now()
WHERE id = %s AND worker_id = %s AND status = 'processing'
"""

INSERT_RESULT_SQL = """
INSERT INTO recognition_results (
    recognition_job_id, people_count, detected_median, detected_percentile_75,
    detected_max, average_confidence, sampled_frames, representative_frame_ms,
    annotated_bucket, annotated_object_key, media_expires_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now() + make_interval(days => %s))
ON CONFLICT (recognition_job_id) DO NOTHING
"""

COMPLETE_JOB_SQL = """
UPDATE recognition_jobs
SET status = 'completed',
    finished_at = now(),
    lease_until = NULL,
    error = NULL,
    updated_at = now()
WHERE id = %s AND worker_id = %s AND status = 'processing'
"""

FAIL_JOB_SQL = """
UPDATE recognition_jobs
SET status = 'failed',
    error = %s,
    finished_at = now(),
    lease_until = NULL,
    updated_at = now()
WHERE id = %s AND worker_id = %s AND status = 'processing'
"""

RETRY_JOB_SQL = """
UPDATE recognition_jobs
SET status = 'retry_wait', error = %s,
    lease_until = now() + make_interval(secs => %s),
    updated_at = now()
WHERE id = %s AND worker_id = %s AND status = 'processing'
"""


@dataclass
class ClaimedJob:
    id: int
    camera_capture_id: int | None
    upload_id: int | None
    sample_rate_fps: float
    confidence_threshold: float
    attempts: int


@dataclass
class SourceContext:
    source_kind: str
    media_type: str
    original_bucket: str | None
    original_object_key: str | None
    filename: str | None
    camera_id: int | None
    measurement_id: int | None
    session_id: int | None
    upload_id: int | None


class Database:
    """Подключение к PostgreSQL с восстановлением после обрыва соединения."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._conn: psycopg2.extensions.connection | None = None

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def _connection(self) -> psycopg2.extensions.connection:
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self._dsn)
        return self._conn

    def _run(self, operation: Callable[[psycopg2.extensions.connection], T]) -> T:
        """Выполняет операцию, один раз переподключаясь при обрыве соединения."""
        try:
            return operation(self._connection())
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            logger.warning("Соединение с БД потеряно, переподключение")
            self.close()
            return operation(self._connection())

    def claim_job(self) -> ClaimedJob | None:
        """Забирает одно pending-задание, помечая его processing за этим воркером."""

        def operation(conn: psycopg2.extensions.connection) -> ClaimedJob | None:
            with conn, conn.cursor() as cur:
                cur.execute(CLAIM_SQL, (settings.worker_id, settings.lease_minutes))
                row = cur.fetchone()
            if row is None:
                return None
            return ClaimedJob(
                id=row[0],
                camera_capture_id=row[1],
                upload_id=row[2],
                sample_rate_fps=float(row[3]),
                confidence_threshold=float(row[4]),
                attempts=row[5],
            )

        return self._run(operation)

    def fetch_source_context(self, job_id: int) -> SourceContext | None:
        """Возвращает источник задания и параметры для построения ключа результата."""

        def operation(conn: psycopg2.extensions.connection) -> SourceContext | None:
            with conn, conn.cursor() as cur:
                cur.execute(SOURCE_CONTEXT_SQL, (job_id,))
                row = cur.fetchone()
            if row is None:
                return None
            return SourceContext(
                source_kind=row[0],
                media_type=row[1],
                original_bucket=row[2],
                original_object_key=row[3],
                filename=row[4],
                camera_id=row[5],
                measurement_id=row[6],
                session_id=row[7],
                upload_id=row[8],
            )

        return self._run(operation)

    def heartbeat(self, job_id: int) -> bool:
        """Продлевает lease; False — задание больше не числится за этим воркером."""

        def operation(conn: psycopg2.extensions.connection) -> bool:
            with conn, conn.cursor() as cur:
                cur.execute(
                    HEARTBEAT_SQL, (settings.lease_minutes, job_id, settings.worker_id)
                )
                return cur.rowcount == 1

        return self._run(operation)

    def complete_job(self, job_id: int, result: "ProcessingResult") -> bool:
        """Сохраняет результат только пока задание принадлежит этому воркеру."""

        def operation(conn: psycopg2.extensions.connection) -> bool:
            with conn, conn.cursor() as cur:
                cur.execute(
                    COMPLETE_JOB_SQL, (job_id, settings.worker_id)
                )
                if cur.rowcount != 1:
                    return False
                cur.execute(
                    INSERT_RESULT_SQL,
                    (
                        job_id,
                        result.people_count,
                        result.detected_median,
                        result.detected_percentile_75,
                        result.detected_max,
                        result.average_confidence,
                        result.sampled_frames,
                        result.representative_frame_ms,
                        result.annotated_bucket,
                        result.annotated_object_key,
                        settings.annotated_retention_days,
                    ),
                )
                return True

        return self._run(operation)

    def fail_job(
        self, job_id: int, attempts: int, error: str, permanent: bool = False
    ) -> bool:
        """Переводит задание в failed либо в retry_wait, если попытки не исчерпаны."""
        error = error[:2000]
        final = permanent or attempts >= settings.max_attempts

        def operation(conn: psycopg2.extensions.connection) -> bool:
            with conn, conn.cursor() as cur:
                if final:
                    cur.execute(FAIL_JOB_SQL, (error, job_id, settings.worker_id))
                else:
                    cur.execute(
                        RETRY_JOB_SQL,
                        (error, settings.retry_delay_seconds, job_id, settings.worker_id),
                    )
                return cur.rowcount == 1

        updated = self._run(operation)
        if not updated:
            logger.warning("Задание %s больше не принадлежит этому воркеру", job_id)
            return False
        if final:
            logger.error("Задание %s окончательно провалено: %s", job_id, error)
        else:
            logger.warning(
                "Задание %s отправлено на повтор (попытка %s из %s): %s",
                job_id,
                attempts,
                settings.max_attempts,
                error,
            )
        return True
