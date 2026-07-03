import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class RecognitionUnavailable(Exception):
    pass


def start_stream(session_id: int, rtsp_url: str) -> None:
    """Просит recognition-сервис начать обработку потока камеры."""
    try:
        response = httpx.post(
            f"{settings.recognition_url}/streams/start",
            json={"session_id": session_id, "rtsp_url": rtsp_url},
            timeout=10.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("Recognition service start failed for session %s: %s", session_id, exc)
        raise RecognitionUnavailable(str(exc)) from exc


def stop_stream(session_id: int) -> None:
    """Останавливает обработку потока. Ошибки не критичны: занятие всё равно закрываем."""
    try:
        response = httpx.post(
            f"{settings.recognition_url}/streams/stop",
            json={"session_id": session_id},
            timeout=10.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Recognition service stop failed for session %s: %s", session_id, exc)
