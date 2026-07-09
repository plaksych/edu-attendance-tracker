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
RETURNING job.id, job.camera_capture_id, job.sample_rate_fps,
    job.confidence_threshold, job.attempts
"""

CAPTURE_CONTEXT_SQL = """
SELECT cc.original_bucket, cc.original_object_key, cc.camera_id,
    cc.measurement_id, m.session_id
FROM camera_captures cc
JOIN measurements m ON m.id = cc.measurement_id
WHERE cc.id = %s
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
    camera_capture_id: int
    sample_rate_fps: float
    confidence_threshold: float
    attempts: int


@dataclass
class CaptureContext:
    original_bucket: str | None
    original_object_key: str | None
    camera_id: int
    measurement_id: int
    session_id: int


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
                sample_rate_fps=float(row[2]),
                confidence_threshold=float(row[3]),
                attempts=row[4],
            )

        return self._run(operation)

    def fetch_capture_context(self, camera_capture_id: int) -> CaptureContext | None:
        """Возвращает данные записи камеры и session_id для построения ключей объектов."""

        def operation(conn: psycopg2.extensions.connection) -> CaptureContext | None:
            with conn, conn.cursor() as cur:
                cur.execute(CAPTURE_CONTEXT_SQL, (camera_capture_id,))
                row = cur.fetchone()
            if row is None:
                return None
            return CaptureContext(
                original_bucket=row[0],
                original_object_key=row[1],
                camera_id=row[2],
                measurement_id=row[3],
                session_id=row[4],
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
