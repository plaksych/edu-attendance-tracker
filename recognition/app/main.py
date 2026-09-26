"""Воркер очереди распознавания: claim → обработка → фиксация результата."""

import logging
import signal
import threading
import tempfile
from types import SimpleNamespace

from app.config import settings
from app.db import ClaimedJob, Database
from app.runner import ChildFailure, LeaseLost, run_child
from app.storage import ObjectStorage

logger = logging.getLogger(__name__)

stop_event = threading.Event()


def _handle_signal(signum: int, _frame: object) -> None:
    logger.info("Получен сигнал %s, останов после текущего задания", signum)
    stop_event.set()


def _fail_job(
    db: Database, job: ClaimedJob, error: str, permanent: bool = False
) -> None:
    try:
        db.fail_job(job.id, job.claim_token, job.attempts, error, permanent=permanent)
    except Exception:
        logger.exception(
            "Не удалось зафиксировать ошибку задания %s; его вернёт в очередь backend "
            "по истечении lease",
            job.id,
        )


def _process_job(db: Database, storage: ObjectStorage, job: ClaimedJob) -> None:
    logger.info(
        "Задание %s принято (%s %s, попытка %s)",
        job.id,
        "загрузка" if job.upload_id is not None else "запись",
        job.upload_id if job.upload_id is not None else job.camera_capture_id,
        job.attempts,
    )
    try:
        context = db.fetch_source_context(job.id)
    except Exception:
        _fail_job(db, job, "source_unavailable")
        return
    if context is None:
        _fail_job(db, job, "источник распознавания не найден", permanent=True)
        return
    if context.original_object_key is None:
        _fail_job(db, job, "нет исходного файла", permanent=True)
        return

    try:
        with tempfile.TemporaryDirectory(prefix="recognition-job-") as directory:
            storage.download(
                context.original_bucket,
                context.original_object_key,
                f"{directory}/source",
            )
            payload = run_child(
                job,
                context,
                directory,
                lambda: db.heartbeat(job.id, job.claim_token),
                stop_event,
            )
            if stop_event.is_set() or not db.heartbeat(job.id, job.claim_token):
                raise LeaseLost()
            result = SimpleNamespace(**payload)
            storage.upload(
                result.annotated_object_key, f"{directory}/annotated.jpg", "image/jpeg"
            )
            if not db.complete_job(job.id, job.claim_token, result):
                raise LeaseLost()
    except LeaseLost:
        logger.warning("Job %s lost its lease; result not published", job.id)
        return
    except ChildFailure as exc:
        _fail_job(db, job, str(exc), permanent=exc.permanent)
        return
    except Exception:
        _fail_job(db, job, "processing_dependency_unavailable")
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
    storage = ObjectStorage()
    storage.check_bucket()

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
            _process_job(db, storage, job)
    finally:
        db.close()
    logger.info("Воркер %s остановлен", settings.worker_id)


if __name__ == "__main__":
    main()
