"""Обработка видеопотока камеры: снятие кадров, инференс, отправка результатов."""

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

import cv2
import httpx

from app.config import settings
from app.detector import detector

logger = logging.getLogger(__name__)


class StreamWorker(threading.Thread):
    """Поток обработки одной камеры в рамках одного занятия.

    Источник может быть RTSP-потоком или путём к видеофайлу — cv2.VideoCapture
    работает с обоими вариантами одинаково.
    """

    def __init__(self, session_id: int, source: str) -> None:
        super().__init__(name=f"stream-{session_id}", daemon=True)
        self.session_id = session_id
        self.source = source
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def stopped(self) -> bool:
        return self._stop_event.is_set()

    def run(self) -> None:
        logger.info("Session %s: старт обработки %s", self.session_id, self.source)
        while not self.stopped:
            capture = cv2.VideoCapture(self.source)
            if not capture.isOpened():
                logger.warning(
                    "Session %s: не удалось открыть поток, повтор через %s c",
                    self.session_id,
                    settings.reconnect_delay,
                )
                capture.release()
                self._stop_event.wait(settings.reconnect_delay)
                continue

            self._process_stream(capture)
            capture.release()

            # Для видеофайла поток заканчивается сам — выходим без переподключения
            if not self.source.startswith(("rtsp://", "rtmp://", "http")):
                break
        logger.info("Session %s: обработка остановлена", self.session_id)

    def _process_stream(self, capture: cv2.VideoCapture) -> None:
        while not self.stopped:
            # Сбрасываем накопившийся буфер, чтобы взять актуальный кадр
            capture.grab()
            ok, frame = capture.retrieve()
            if not ok:
                logger.warning("Session %s: поток прервался", self.session_id)
                return

            captured_at = datetime.now(timezone.utc)
            try:
                result = detector.detect(frame)
            except Exception:
                logger.exception("Session %s: ошибка инференса", self.session_id)
                self._stop_event.wait(settings.snapshot_interval)
                continue

            frame_path = self._save_frame(result.annotated_frame, captured_at)
            self._send_snapshot(captured_at, result.person_count, result.avg_confidence, frame_path)

            logger.info(
                "Session %s: %s чел. (conf=%s)",
                self.session_id,
                result.person_count,
                result.avg_confidence,
            )
            self._stop_event.wait(settings.snapshot_interval)

    def _save_frame(self, frame, captured_at: datetime) -> str | None:
        directory = Path(settings.snapshot_dir) / str(self.session_id)
        try:
            directory.mkdir(parents=True, exist_ok=True)
            filename = captured_at.strftime("%Y%m%d_%H%M%S") + ".jpg"
            cv2.imwrite(str(directory / filename), frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            return f"{self.session_id}/{filename}"
        except OSError:
            logger.exception("Session %s: не удалось сохранить кадр", self.session_id)
            return None

    def _send_snapshot(
        self,
        captured_at: datetime,
        person_count: int,
        confidence: float | None,
        frame_path: str | None,
    ) -> None:
        url = f"{settings.backend_url}/api/v1/sessions/{self.session_id}/snapshots"
        payload = {
            "captured_at": captured_at.isoformat(),
            "person_count": person_count,
            "confidence": confidence,
            "frame_path": frame_path,
        }
        try:
            response = httpx.post(url, json=payload, timeout=15.0)
            if response.status_code == 409:
                # Занятие закрыли на стороне backend — дорабатывать нет смысла
                logger.info(
                    "Session %s: backend больше не принимает замеры, останавливаюсь",
                    self.session_id,
                )
                self.stop()
                return
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Session %s: не удалось отправить замер: %s", self.session_id, exc)


class StreamManager:
    """Реестр активных потоков обработки."""

    def __init__(self) -> None:
        self._workers: dict[int, StreamWorker] = {}
        self._lock = threading.Lock()

    def start(self, session_id: int, source: str) -> bool:
        with self._lock:
            existing = self._workers.get(session_id)
            if existing is not None and existing.is_alive() and not existing.stopped:
                return False
            worker = StreamWorker(session_id, source)
            self._workers[session_id] = worker
            worker.start()
            return True

    def stop(self, session_id: int) -> bool:
        with self._lock:
            worker = self._workers.pop(session_id, None)
        if worker is None:
            return False
        worker.stop()
        return True

    def stop_all(self) -> None:
        with self._lock:
            workers = list(self._workers.values())
            self._workers.clear()
        for worker in workers:
            worker.stop()

    def active(self) -> list[dict]:
        with self._lock:
            return [
                {"session_id": w.session_id, "source": w.source}
                for w in self._workers.values()
                if w.is_alive() and not w.stopped
            ]


manager = StreamManager()
