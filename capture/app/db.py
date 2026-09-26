"""Очередь заданий camera_captures в PostgreSQL.

Одно соединение psycopg2 на процесс: параллельные потоки записи выполняют
короткие запросы под блокировкой, при обрыве связи соединение
восстанавливается автоматически.
"""

import logging
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

CLAIM_SQL = """
    UPDATE camera_captures AS cc
    SET status = 'claimed',
        worker_id = %(worker_id)s,
        claim_token = %(claim_token)s,
        lease_until = now() + make_interval(secs => %(lease_seconds)s),
        attempts = cc.attempts + 1,
        updated_at = now()
    FROM (
        SELECT target.id
        FROM camera_captures AS target
        JOIN cameras AS cam ON cam.id = target.camera_id
        WHERE target.status = 'pending'
          AND target.attempts < %(max_attempts)s
          AND cam.enabled
          AND cam.capture_group = %(capture_group)s
          AND target.planned_at <= now() + make_interval(secs => %(lookahead_seconds)s)
        ORDER BY target.planned_at, target.id
        LIMIT %(batch_size)s
        FOR UPDATE OF target SKIP LOCKED
    ) AS picked
    WHERE cc.id = picked.id
    RETURNING
        cc.id,
        cc.measurement_id,
        cc.camera_id,
        cc.planned_at,
        cc.duration_seconds,
        cc.attempts,
        cc.claim_token,
        (SELECT cam.rtsp_url FROM cameras AS cam WHERE cam.id = cc.camera_id) AS rtsp_url,
        (SELECT m.session_id FROM measurements AS m WHERE m.id = cc.measurement_id) AS session_id
"""


@dataclass(frozen=True)
class CaptureTask:
    """Задание на запись одного ролика, захваченное этим воркером."""

    id: int
    measurement_id: int
    camera_id: int
    planned_at: datetime
    duration_seconds: int
    attempts: int
    rtsp_url: str
    session_id: int
    claim_token: str


class Database:
    """Обёртка над соединением psycopg2 с реконнектом и потокобезопасностью."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._lock = threading.Lock()
        self._conn: psycopg2.extensions.connection | None = None

    def _connection(self) -> psycopg2.extensions.connection:
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(
                self._dsn,
                connect_timeout=5,
                options="-c statement_timeout=10000 -c lock_timeout=3000",
            )
            self._conn.autocommit = False
            logger.info("Установлено соединение с PostgreSQL")
        return self._conn

    def _drop_connection(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:  # noqa: BLE001 — соединение уже неработоспособно
                pass
            self._conn = None

    def _run(self, action: Callable[[psycopg2.extensions.cursor], Any]) -> Any:
        """Выполняет action в транзакции; при обрыве связи повторяет один раз."""
        with self._lock:
            last_error: psycopg2.OperationalError | None = None
            for attempt in (1, 2):
                conn = None
                try:
                    conn = self._connection()
                    with conn.cursor(
                        cursor_factory=psycopg2.extras.RealDictCursor
                    ) as cur:
                        result = action(cur)
                    conn.commit()
                    return result
                except (psycopg2.OperationalError, psycopg2.InterfaceError) as exc:
                    last_error = exc
                    self._drop_connection()
                    if attempt == 1:
                        logger.warning("PostgreSQL connection lost; reconnecting")
                except Exception:
                    if conn is not None and not conn.closed:
                        conn.rollback()
                    raise
            raise last_error  # type: ignore[misc]

    def close(self) -> None:
        """Закрывает соединение с базой."""
        with self._lock:
            self._drop_connection()

    def claim_batch(
        self,
        worker_id: str,
        capture_group: str,
        lookahead_seconds: int,
        lease_seconds: int,
        batch_size: int,
        max_attempts: int = 3,
    ) -> list[CaptureTask]:
        """Захватывает пачку ближайших заданий своей группы одним UPDATE."""

        token = str(uuid.uuid4())

        def action(cur: psycopg2.extensions.cursor) -> list[CaptureTask]:
            cur.execute(
                """SELECT cc.id, cc.measurement_id, cc.camera_id, cc.planned_at,
                cc.duration_seconds, cc.attempts, cc.claim_token, cam.rtsp_url, m.session_id
                FROM camera_captures cc JOIN cameras cam ON cam.id = cc.camera_id
                JOIN measurements m ON m.id = cc.measurement_id
                WHERE cc.claim_token = %s AND cc.worker_id = %s""",
                (token, worker_id),
            )
            existing = cur.fetchall()
            if existing:
                return [CaptureTask(**row) for row in existing]
            cur.execute(
                CLAIM_SQL,
                {
                    "worker_id": worker_id,
                    "claim_token": token,
                    "max_attempts": max_attempts,
                    "capture_group": capture_group,
                    "lookahead_seconds": lookahead_seconds,
                    "lease_seconds": lease_seconds,
                    "batch_size": batch_size,
                },
            )
            return [CaptureTask(**row) for row in cur.fetchall()]

        return self._run(action)

    def mark_recording(
        self, capture_id: int, worker_id: str, claim_token: str, lease_seconds: int
    ) -> bool:
        """Переводит своё claimed-задание в recording и продлевает lease."""

        def action(cur: psycopg2.extensions.cursor) -> bool:
            cur.execute(
                """
                UPDATE camera_captures
                SET status = 'recording',
                    capture_started_at = now(),
                    lease_until = now() + make_interval(secs => %s),
                    updated_at = now()
                WHERE id = %s AND worker_id = %s AND status = 'claimed'
                  AND claim_token = %s AND lease_until > clock_timestamp()
                """,
                (lease_seconds, capture_id, worker_id, claim_token),
            )
            return cur.rowcount == 1

        return self._run(action)

    def heartbeat(
        self, capture_id: int, worker_id: str, claim_token: str, lease_seconds: int
    ) -> bool:
        """Продлевает lease активной записи; False означает потерю задания."""

        def action(cur: psycopg2.extensions.cursor) -> bool:
            cur.execute(
                """
                UPDATE camera_captures
                SET lease_until = now() + make_interval(secs => %s),
                    updated_at = now()
                WHERE id = %s
                  AND worker_id = %s
                  AND status IN ('recording', 'uploading')
                  AND claim_token = %s AND lease_until > clock_timestamp()
                """,
                (lease_seconds, capture_id, worker_id, claim_token),
            )
            return cur.rowcount == 1

        return self._run(action)

    def mark_uploading(self, capture_id: int, worker_id: str, claim_token: str) -> bool:
        """Переводит своё recording-задание в статус uploading."""

        def action(cur: psycopg2.extensions.cursor) -> bool:
            cur.execute(
                """
                UPDATE camera_captures
                SET status = 'uploading', updated_at = now()
                WHERE id = %s AND worker_id = %s AND status = 'recording'
                  AND claim_token = %s AND lease_until > clock_timestamp()
                """,
                (capture_id, worker_id, claim_token),
            )
            return cur.rowcount == 1

        return self._run(action)

    def mark_completed(
        self,
        capture_id: int,
        worker_id: str,
        claim_token: str,
        bucket: str,
        object_key: str,
        size_bytes: int,
        duration_ms: int,
    ) -> bool:
        """Фиксирует успех своего uploading-задания и создаёт задачу распознавания."""

        def action(cur: psycopg2.extensions.cursor) -> bool:
            cur.execute(
                """
                UPDATE camera_captures
                SET status = 'completed',
                    original_bucket = %s,
                    original_object_key = %s,
                    content_type = 'video/mp4',
                    size_bytes = %s,
                    duration_ms = %s,
                    capture_finished_at = now(),
                    worker_id = NULL,
                    lease_until = NULL,
                    error = NULL,
                    updated_at = now()
                WHERE id = %s AND worker_id = %s AND status = 'uploading'
                  AND claim_token = %s AND lease_until > clock_timestamp()
                """,
                (
                    bucket,
                    object_key,
                    size_bytes,
                    duration_ms,
                    capture_id,
                    worker_id,
                    claim_token,
                ),
            )
            if cur.rowcount != 1:
                cur.execute(
                    """SELECT 1 FROM camera_captures cc
                    JOIN recognition_jobs j ON j.camera_capture_id = cc.id
                    WHERE cc.id = %s AND cc.claim_token = %s AND cc.status = 'completed'
                      AND cc.original_object_key = %s""",
                    (capture_id, claim_token, object_key),
                )
                return cur.fetchone() is not None
            cur.execute(
                """
                INSERT INTO recognition_jobs (camera_capture_id)
                VALUES (%s)
                ON CONFLICT (camera_capture_id) DO NOTHING
                """,
                (capture_id,),
            )
            return True

        return self._run(action)

    def release_claims(self, claims: list[tuple[int, str]], worker_id: str) -> int:
        """Возвращает ещё не начатые claimed-задания в очередь при остановке."""
        if not claims:
            return 0

        def action(cur: psycopg2.extensions.cursor) -> int:
            released = 0
            for capture_id, token in claims:
                cur.execute(
                    """
                    UPDATE camera_captures
                    SET status = 'pending', worker_id = NULL, lease_until = NULL,
                        updated_at = now()
                    WHERE id = %s AND worker_id = %s AND status = 'claimed'
                        AND claim_token = %s AND lease_until > clock_timestamp()
                    """,
                    (capture_id, worker_id, token),
                )
                released += cur.rowcount
            return released

        return self._run(action)

    def mark_retry(
        self,
        capture_id: int,
        worker_id: str,
        claim_token: str,
        error: str,
        retry_delay_seconds: int,
    ) -> bool:
        """Откладывает задание на повтор; в pending его вернёт реапер backend."""

        def action(cur: psycopg2.extensions.cursor) -> bool:
            cur.execute(
                """
                UPDATE camera_captures
                SET status = 'retry_wait',
                    lease_until = now() + make_interval(secs => %s),
                    error = %s,
                    updated_at = now()
                WHERE id = %s
                  AND worker_id = %s
                  AND status IN ('claimed', 'recording', 'uploading')
                  AND claim_token = %s AND lease_until > clock_timestamp()
                """,
                (retry_delay_seconds, error[:2000], capture_id, worker_id, claim_token),
            )
            return cur.rowcount == 1

        return self._run(action)

    def mark_failed(
        self, capture_id: int, worker_id: str, claim_token: str, error: str
    ) -> bool:
        """Помечает задание проваленным после исчерпания попыток."""

        def action(cur: psycopg2.extensions.cursor) -> bool:
            cur.execute(
                """
                UPDATE camera_captures
                SET status = 'failed',
                    lease_until = NULL,
                    error = %s,
                    updated_at = now()
                WHERE id = %s
                  AND worker_id = %s
                  AND status IN ('claimed', 'recording', 'uploading')
                  AND claim_token = %s AND lease_until > clock_timestamp()
                """,
                (error[:2000], capture_id, worker_id, claim_token),
            )
            return cur.rowcount == 1

        return self._run(action)
