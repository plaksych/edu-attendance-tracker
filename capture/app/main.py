"""Capture Manager: воркер записи роликов с камер по расписанию.

Забирает из PostgreSQL задания camera_captures своей capture-группы,
дожидается planned_at, параллельными процессами ffmpeg пишет короткие
ролики, загружает их в MinIO и ставит задания распознавания. Экземпляры
масштабируются горизонтально: конкуренция за задания решается через
FOR UPDATE SKIP LOCKED.
"""

import logging
import os
import signal
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings, get_settings
from app.db import CaptureTask, Database
from app.recorder import record_clip
from app.storage import Storage, original_object_key

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


class CaptureLeaseLost(Exception):
    """Задание вернулось в очередь или было взято другим воркером."""


def _heartbeat_loop(
    db: Database, settings: Settings, task: CaptureTask, stop: threading.Event
) -> None:
    while not stop.wait(settings.heartbeat_interval_seconds):
        try:
            if not db.heartbeat(task.id, settings.worker_id, settings.lease_seconds):
                logger.warning("Потерян lease задания записи %s", task.id)
                return
        except Exception:
            logger.exception("Не удалось продлить lease задания записи %s", task.id)


def process_task(db: Database, storage: Storage, settings: Settings, task: CaptureTask) -> None:
    """Полный цикл одного задания: запись, загрузка, фиксация результата."""
    tmp_path: str | None = None
    heartbeat_stop = threading.Event()
    heartbeat_thread: threading.Thread | None = None
    try:
        if not db.mark_recording(task.id, settings.worker_id, settings.lease_seconds):
            raise CaptureLeaseLost()
        heartbeat_thread = threading.Thread(
            target=_heartbeat_loop,
            args=(db, settings, task, heartbeat_stop),
            name=f"capture-heartbeat-{task.id}",
            daemon=True,
        )
        heartbeat_thread.start()
        fd, tmp_path = tempfile.mkstemp(prefix=f"capture-{task.id}-", suffix=".mp4")
        os.close(fd)
        record_clip(
            task.rtsp_url,
            task.duration_seconds,
            tmp_path,
            settings.ffmpeg_extra_timeout_seconds,
        )
        if not db.mark_uploading(task.id, settings.worker_id):
            raise CaptureLeaseLost()
        object_key = original_object_key(task.session_id, task.measurement_id, task.camera_id)
        size_bytes = storage.upload_video(tmp_path, object_key)
        if not db.mark_completed(
            task.id,
            settings.worker_id,
            storage.bucket,
            object_key,
            size_bytes,
            task.duration_seconds * 1000,
        ):
            raise CaptureLeaseLost()
        logger.info("Задание %s выполнено: %s (%s байт)", task.id, object_key, size_bytes)
    except CaptureLeaseLost:
        logger.warning("Задание записи %s больше не принадлежит этому воркеру", task.id)
    except Exception as exc:  # noqa: BLE001 — любая ошибка фиксируется в задании
        _register_failure(db, settings, task, exc)
    finally:
        heartbeat_stop.set()
        if heartbeat_thread is not None:
            heartbeat_thread.join()
        if tmp_path is not None:
            Path(tmp_path).unlink(missing_ok=True)


def _register_failure(db: Database, settings: Settings, task: CaptureTask, exc: Exception) -> None:
    """Переводит задание в retry_wait или failed в зависимости от числа попыток."""
    error_text = str(exc) or exc.__class__.__name__
    try:
        if task.attempts >= settings.max_attempts:
            updated = db.mark_failed(task.id, settings.worker_id, error_text)
            if not updated:
                logger.warning("Задание записи %s больше не принадлежит этому воркеру", task.id)
                return
            logger.error(
                "Задание %s провалено после %s попыток: %s", task.id, task.attempts, error_text
            )
        else:
            updated = db.mark_retry(
                task.id, settings.worker_id, error_text, settings.retry_delay_seconds
            )
            if not updated:
                logger.warning("Задание записи %s больше не принадлежит этому воркеру", task.id)
                return
            logger.warning(
                "Задание %s отложено на повтор (попытка %s): %s",
                task.id,
                task.attempts,
                error_text,
            )
    except Exception:
        logger.exception("Не удалось зафиксировать ошибку задания %s", task.id)


def run_batch(
    db: Database,
    storage: Storage,
    settings: Settings,
    executor: ThreadPoolExecutor,
    tasks: list[CaptureTask],
    stop_event: threading.Event,
) -> None:
    """Дожидается planned_at и запускает готовые задания параллельно.

    Если остановка пришла до начала записи, ещё не начатые задания возвращаются
    в pending и могут быть быстро забраны другим экземпляром.
    """
    pending = sorted(tasks, key=lambda task: (task.planned_at, task.id))
    while pending:
        if stop_event.is_set():
            released = db.release_claims(
                [task.id for task in pending],
                settings.worker_id,
            )
            logger.info("Возвращено в очередь не начатых заданий: %s", released)
            return

        now = datetime.now(timezone.utc)
        due = [task for task in pending if task.planned_at <= now]
        if not due:
            wait_seconds = max((pending[0].planned_at - now).total_seconds(), 0.0)
            stop_event.wait(wait_seconds)
            continue
        pending = pending[len(due):]
        logger.info("Старт записи: %s заданий", len(due))
        futures = [executor.submit(process_task, db, storage, settings, task) for task in due]
        wait(futures)


def main() -> None:
    settings = get_settings()
    stop_event = threading.Event()

    def handle_signal(signum: int, _frame: object) -> None:
        logger.info(
            "Получен сигнал %s, завершение после текущих заданий", signal.Signals(signum).name
        )
        stop_event.set()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    db = Database(settings.database_url)
    storage = Storage(settings)
    storage.check_bucket()

    logger.info(
        "Capture Manager запущен: группа %s, воркер %s",
        settings.capture_group,
        settings.worker_id,
    )

    with ThreadPoolExecutor(max_workers=settings.claim_batch_size) as executor:
        while not stop_event.is_set():
            try:
                tasks = db.claim_batch(
                    worker_id=settings.worker_id,
                    capture_group=settings.capture_group,
                    lookahead_seconds=settings.claim_lookahead_seconds,
                    lease_seconds=settings.lease_seconds,
                    batch_size=settings.claim_batch_size,
                )
            except Exception:
                logger.exception("Не удалось захватить задания, пауза перед повтором")
                stop_event.wait(settings.poll_interval_seconds)
                continue
            if not tasks:
                stop_event.wait(settings.poll_interval_seconds)
                continue
            logger.info("Захвачено заданий: %s", len(tasks))
            run_batch(db, storage, settings, executor, tasks, stop_event)

    db.close()
    logger.info("Capture Manager остановлен")


if __name__ == "__main__":
    main()
