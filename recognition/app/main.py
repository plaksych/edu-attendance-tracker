"""Воркер очереди распознавания: claim → обработка → фиксация результата."""

import logging
import signal
import threading

from app.config import settings
from app.db import ClaimedJob, Database
from app.detector import PersonDetector
from app.processor import JobProcessor
from app.storage import ObjectStorage

logger = logging.getLogger(__name__)

stop_event = threading.Event()


def _handle_signal(signum: int, _frame: object) -> None:
    logger.info("Получен сигнал %s, останов после текущего задания", signum)
    stop_event.set()


def _heartbeat_loop(db: Database, job_id: int, stop: threading.Event) -> None:
    """Продлевает lease задания, пока идёт обработка."""
    while not stop.wait(settings.heartbeat_interval_seconds):
        try:
            if not db.heartbeat(job_id):
                logger.warning(
                    "Heartbeat задания %s отклонён: задание больше не за воркером %s",
                    job_id,
                    settings.worker_id,
                )
                return
        except Exception:
            logger.exception("Ошибка heartbeat задания %s", job_id)


def _fail_job(db: Database, job: ClaimedJob, error: str, permanent: bool = False) -> None:
    try:
        db.fail_job(job.id, job.attempts, error, permanent=permanent)
    except Exception:
        logger.exception(
            "Не удалось зафиксировать ошибку задания %s; его вернёт в очередь backend "
            "по истечении lease",
            job.id,
        )


def _process_job(
    db: Database, heartbeat_db: Database, processor: JobProcessor, job: ClaimedJob
) -> None:
    logger.info(
        "Задание %s принято (%s %s, попытка %s)",
        job.id,
        "загрузка" if job.upload_id is not None else "запись",
        job.upload_id if job.upload_id is not None else job.camera_capture_id,
        job.attempts,
    )
    try:
        context = db.fetch_source_context(job.id)
    except Exception as exc:
        logger.exception("Не удалось получить источник для задания %s", job.id)
        _fail_job(db, job, f"ошибка чтения источника: {exc}")
        return
    if context is None:
        _fail_job(db, job, "источник распознавания не найден", permanent=True)
        return
    if context.original_object_key is None:
        _fail_job(db, job, "нет исходного файла", permanent=True)
        return

    heartbeat_stop = threading.Event()
    heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(heartbeat_db, job.id, heartbeat_stop),
        name=f"heartbeat-{job.id}",
        daemon=True,
    )
    heartbeat_thread.start()
    try:
        result = processor.process(job, context)
    except Exception as exc:
        logger.exception("Задание %s завершилось ошибкой", job.id)
        _fail_job(db, job, str(exc) or type(exc).__name__)
        return
    finally:
        heartbeat_stop.set()
        heartbeat_thread.join()

    try:
        if not db.complete_job(job.id, result):
            logger.warning("Результат задания %s не сохранён: lease потерян", job.id)
            return
    except Exception as exc:
        logger.exception("Не удалось сохранить результат задания %s", job.id)
        _fail_job(db, job, f"ошибка сохранения результата: {exc}")
        return
    logger.info("Задание %s выполнено", job.id)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    db = Database(settings.database_url)
    # Отдельное соединение: heartbeat живёт в фоновом потоке во время обработки
    heartbeat_db = Database(settings.database_url)
    storage = ObjectStorage()
    storage.check_bucket()
    processor = JobProcessor(storage=storage, detector=PersonDetector(settings.model_path))

    logger.info("Воркер %s запущен", settings.worker_id)
    try:
        while not stop_event.is_set():
            try:
                job = db.claim_job()
            except Exception:
                logger.exception("Не удалось забрать задание из очереди")
                stop_event.wait(settings.poll_interval_seconds)
                continue
            if job is None:
                stop_event.wait(settings.poll_interval_seconds)
                continue
            _process_job(db, heartbeat_db, processor, job)
    finally:
        db.close()
        heartbeat_db.close()
    logger.info("Воркер %s остановлен", settings.worker_id)


if __name__ == "__main__":
    main()
