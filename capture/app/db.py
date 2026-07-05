"""Очередь заданий camera_captures в PostgreSQL.

Одно соединение psycopg2 на процесс: параллельные потоки записи выполняют
короткие запросы под блокировкой, при обрыве связи соединение
восстанавливается автоматически.
"""

import logging
import threading
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
        lease_until = now() + make_interval(secs => %(lease_seconds)s),
        attempts = cc.attempts + 1,
        updated_at = now()
    FROM (
        SELECT target.id
        FROM camera_captures AS target
        JOIN cameras AS cam ON cam.id = target.camera_id
        WHERE target.status = 'pending'
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


class Database:
    """Обёртка над соединением psycopg2 с реконнектом и потокобезопасностью."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._lock = threading.Lock()
        self._conn: psycopg2.extensions.connection | None = None

    def _connection(self) -> psycopg2.extensions.connection:
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self._dsn)
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
                    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                        result = action(cur)
                    conn.commit()
                    return result
                except psycopg2.OperationalError as exc:
                    last_error = exc
                    self._drop_connection()
                    if attempt == 1:
                        logger.warning("Потеряно соединение с PostgreSQL, переподключение: %s", exc)
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
    ) -> list[CaptureTask]:
        """Захватывает пачку ближайших заданий своей группы одним UPDATE."""

        def action(cur: psycopg2.extensions.cursor) -> list[CaptureTask]:
            cur.execute(
                CLAIM_SQL,
                {
                    "worker_id": worker_id,
                    "capture_group": capture_group,
                    "lookahead_seconds": lookahead_seconds,
                    "lease_seconds": lease_seconds,
                    "batch_size": batch_size,
                },
            )
            return [CaptureTask(**row) for row in cur.fetchall()]

        return self._run(action)

    def mark_recording(self, capture_id: int, worker_id: str, lease_seconds: int) -> None:
        """Переводит задание в статус recording и продлевает lease."""

        def action(cur: psycopg2.extensions.cursor) -> None:
            cur.execute(
                """
                UPDATE camera_captures
                SET status = 'recording',
                    capture_started_at = now(),
                    lease_until = now() + make_interval(secs => %s),
                    updated_at = now()
                WHERE id = %s AND worker_id = %s
                """,
                (lease_seconds, capture_id, worker_id),
            )

        self._run(action)

    def mark_uploading(self, capture_id: int, worker_id: str) -> None:
        """Переводит задание в статус uploading."""

        def action(cur: psycopg2.extensions.cursor) -> None:
            cur.execute(
                """
                UPDATE camera_captures
                SET status = 'uploading', updated_at = now()
                WHERE id = %s AND worker_id = %s
                """,
                (capture_id, worker_id),
            )

        self._run(action)

    def mark_completed(
        self,
        capture_id: int,
        worker_id: str,
        bucket: str,
        object_key: str,
        size_bytes: int,
        duration_ms: int,
    ) -> None:
        """Фиксирует успех и создаёт задание распознавания одной транзакцией."""

        def action(cur: psycopg2.extensions.cursor) -> None:
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
                    error = NULL,
                    updated_at = now()
                WHERE id = %s AND worker_id = %s
                """,
                (bucket, object_key, size_bytes, duration_ms, capture_id, worker_id),
            )
            cur.execute(
                """
                INSERT INTO recognition_jobs (camera_capture_id)
                VALUES (%s)
                ON CONFLICT (camera_capture_id) DO NOTHING
                """,
                (capture_id,),
            )

        self._run(action)

    def release_claims(self, capture_ids: list[int], worker_id: str) -> int:
        """Возвращает ещё не начатые claimed-задания в очередь при остановке."""
        if not capture_ids:
            return 0

        def action(cur: psycopg2.extensions.cursor) -> int:
            cur.execute(
                """
                UPDATE camera_captures
                SET status = 'pending',
                    worker_id = NULL,
                    lease_until = NULL,
                    updated_at = now()
                WHERE id = ANY(%s)
                  AND worker_id = %s
                  AND status = 'claimed'
                """,
                (capture_ids, worker_id),
            )
            return cur.rowcount

        return self._run(action)

    def mark_retry(
        self,
        capture_id: int,
        worker_id: str,
        error: str,
        retry_delay_seconds: int,
    ) -> None:
        """Откладывает задание на повтор; в pending его вернёт реапер backend."""

        def action(cur: psycopg2.extensions.cursor) -> None:
            cur.execute(
                """
                UPDATE camera_captures
                SET status = 'retry_wait',
                    lease_until = now() + make_interval(secs => %s),
                    error = %s,
                    updated_at = now()
                WHERE id = %s AND worker_id = %s
                """,
                (retry_delay_seconds, error, capture_id, worker_id),
            )

        self._run(action)

    def mark_failed(self, capture_id: int, worker_id: str, error: str) -> None:
        """Помечает задание проваленным после исчерпания попыток."""

        def action(cur: psycopg2.extensions.cursor) -> None:
            cur.execute(
                """
                UPDATE camera_captures
                SET status = 'failed', error = %s, updated_at = now()
                WHERE id = %s AND worker_id = %s
                """,
                (error, capture_id, worker_id),
            )

        self._run(action)
