"""Очередь recognition_jobs в PostgreSQL: claim, heartbeat, фиксация результата."""

import logging
import random
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, TypeVar

import psycopg2
import psycopg2.extensions
from psycopg2.extras import Json

from app.config import settings

if TYPE_CHECKING:
    from app.processor import ProcessingResult

logger = logging.getLogger(__name__)

T = TypeVar("T")

CLAIM_SQL = """
WITH selected AS (
    SELECT id FROM recognition_jobs
    WHERE status = 'pending' AND attempts < %s
    ORDER BY created_at, id
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
UPDATE recognition_jobs job
SET status = 'processing',
    worker_id = %s,
    claim_token = %s,
    lease_until = now() + make_interval(mins => %s),
    heartbeat_at = now(),
    attempts = attempts + 1,
    started_at = COALESCE(started_at, now()),
    updated_at = now()
FROM selected
WHERE job.id = selected.id
RETURNING job.id, job.camera_capture_id, job.upload_id, job.sample_rate_fps,
    job.confidence_threshold, job.attempts, job.claim_token
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
    ru.id,
    ru.reference_people_count
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
WHERE id = %s AND worker_id = %s AND claim_token = %s
    AND status = 'processing' AND lease_until > clock_timestamp()
"""

INSERT_RESULT_SQL = """
INSERT INTO recognition_results (
    recognition_job_id, people_count, detected_median, detected_percentile_75,
    detected_max, average_confidence, count_stddev, sampled_frames, source_frames,
    source_duration_ms, representative_frame_ms, absolute_error, relative_error,
    within_tolerance, annotated_bucket, annotated_object_key, media_expires_at,
    inference_metadata
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now() + make_interval(days => %s), %s)
"""

COMPLETE_JOB_SQL = """
UPDATE recognition_jobs
SET status = 'completed',
    finished_at = now(),
    lease_until = NULL,
    error = NULL,
    updated_at = now()
WHERE id = %s AND worker_id = %s AND claim_token = %s
    AND status = 'processing' AND lease_until > clock_timestamp()
"""

FAIL_JOB_SQL = """
UPDATE recognition_jobs
SET status = 'failed',
    error = %s,
    finished_at = now(),
    lease_until = NULL,
    updated_at = now()
WHERE id = %s AND worker_id = %s AND claim_token = %s
    AND status = 'processing' AND lease_until > clock_timestamp()
"""

RETRY_JOB_SQL = """
UPDATE recognition_jobs
SET status = 'retry_wait', error = %s,
    lease_until = now() + make_interval(secs => %s),
    updated_at = now()
WHERE id = %s AND worker_id = %s AND claim_token = %s
    AND status = 'processing' AND lease_until > clock_timestamp()
"""


@dataclass
class ClaimedJob:
    id: int
    camera_capture_id: int | None
    upload_id: int | None
    sample_rate_fps: float
    confidence_threshold: float
    attempts: int
    claim_token: str


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
    reference_people_count: int | None


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
            self._conn = psycopg2.connect(
                self._dsn,
                connect_timeout=5,
                options="-c statement_timeout=10000 -c lock_timeout=3000",
            )
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

        token = str(uuid.uuid4())

        def operation(conn: psycopg2.extensions.connection) -> ClaimedJob | None:
            with conn, conn.cursor() as cur:
                # Reconcile an unknown claim commit before attempting another claim.
                cur.execute(
                    """SELECT id, camera_capture_id, upload_id, sample_rate_fps,
                    confidence_threshold, attempts, claim_token FROM recognition_jobs
                    WHERE claim_token = %s AND worker_id = %s""",
                    (token, settings.worker_id),
                )
                row = cur.fetchone()
                if row is None:
                    cur.execute(
                        CLAIM_SQL,
                        (
                            settings.max_attempts,
                            settings.worker_id,
                            token,
                            settings.lease_minutes,
                        ),
                    )
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
                claim_token=row[6],
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
                reference_people_count=row[9],
            )

        return self._run(operation)

    def heartbeat(self, job_id: int, claim_token: str) -> bool:
        """Продлевает lease; False — задание больше не числится за этим воркером."""

        def operation(conn: psycopg2.extensions.connection) -> bool:
            with conn, conn.cursor() as cur:
                cur.execute(
                    HEARTBEAT_SQL,
                    (settings.lease_minutes, job_id, settings.worker_id, claim_token),
                )
                return cur.rowcount == 1

        return self._run(operation)

    def complete_job(
        self, job_id: int, claim_token: str, result: "ProcessingResult"
    ) -> bool:
        """Сохраняет результат только пока задание принадлежит этому воркеру."""

        def operation(conn: psycopg2.extensions.connection) -> bool:
            with conn, conn.cursor() as cur:
                cur.execute(COMPLETE_JOB_SQL, (job_id, settings.worker_id, claim_token))
                if cur.rowcount != 1:
                    cur.execute(
                        """SELECT 1 FROM recognition_jobs j
                        JOIN recognition_results r ON r.recognition_job_id = j.id
                        WHERE j.id = %s AND j.claim_token = %s AND j.status = 'completed'
                          AND r.annotated_object_key = %s""",
                        (job_id, claim_token, result.annotated_object_key),
                    )
                    return cur.fetchone() is not None
                cur.execute(
                    INSERT_RESULT_SQL,
                    (
                        job_id,
                        result.people_count,
                        result.detected_median,
                        result.detected_percentile_75,
                        result.detected_max,
                        result.average_confidence,
                        result.count_stddev,
                        result.sampled_frames,
                        result.source_frames,
                        result.source_duration_ms,
                        result.representative_frame_ms,
                        result.absolute_error,
                        result.relative_error,
                        result.within_tolerance,
                        result.annotated_bucket,
                        result.annotated_object_key,
                        settings.annotated_retention_days,
                        Json(result.inference_metadata),
                    ),
                )
                return True

        return self._run(operation)

    def fail_job(
        self,
        job_id: int,
        claim_token: str,
        attempts: int,
        error: str,
        permanent: bool = False,
    ) -> bool:
        """Переводит задание в failed либо в retry_wait, если попытки не исчерпаны."""
        error = error[:2000]
        final = permanent or attempts >= settings.max_attempts

        def operation(conn: psycopg2.extensions.connection) -> bool:
            with conn, conn.cursor() as cur:
                if final:
                    cur.execute(
                        FAIL_JOB_SQL, (error, job_id, settings.worker_id, claim_token)
                    )
                else:
                    cur.execute(
                        RETRY_JOB_SQL,
                        (
                            error,
                            retry_delay(attempts),
                            job_id,
                            settings.worker_id,
                            claim_token,
                        ),
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


def retry_delay(attempts: int) -> float:
    ceiling = min(
        settings.retry_max_delay_seconds,
        settings.retry_delay_seconds * 2 ** min(max(attempts - 1, 0), 16),
    )
    return random.uniform(ceiling / 2, ceiling)
