"""Запись одного ролика с источника через subprocess ffmpeg."""

import logging
import os
import subprocess

logger = logging.getLogger(__name__)

# Файлы меньше этого размера считаем битыми: валидный mp4 с видео так не весит
MIN_VALID_SIZE_BYTES = 1024


class RecordingError(Exception):
    """Не удалось записать ролик с источника."""


def _build_command(
    source_url: str,
    duration_seconds: int,
    output_path: str,
    transcode: bool,
) -> list[str]:
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    if source_url.startswith("rtsp://"):
        command += ["-rtsp_transport", "tcp"]
    command += ["-i", source_url, "-t", str(duration_seconds)]
    if transcode:
        command += ["-c:v", "libx264", "-preset", "ultrafast", "-an"]
    else:
        command += ["-c", "copy"]
    command += ["-movflags", "+faststart", "-y", output_path]
    return command


def _attempt(
    source_url: str,
    duration_seconds: int,
    output_path: str,
    timeout_seconds: int,
    transcode: bool,
) -> str | None:
    """Одна попытка записи; возвращает текст ошибки или None при успехе."""
    command = _build_command(source_url, duration_seconds, output_path, transcode)
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return f"ffmpeg не уложился в {timeout_seconds} с и был остановлен"
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        return f"ffmpeg завершился с кодом {completed.returncode}: {stderr[-500:]}"
    try:
        size = os.path.getsize(output_path)
    except OSError:
        size = 0
    if size < MIN_VALID_SIZE_BYTES:
        return f"записанный файл подозрительно мал ({size} байт)"
    return None


def record_clip(
    source_url: str,
    duration_seconds: int,
    output_path: str,
    extra_timeout_seconds: int,
) -> None:
    """Записывает ролик длиной duration_seconds в output_path.

    Первая попытка копирует поток без перекодирования; если она не дала
    валидный файл, выполняется одна повторная попытка с перекодированием
    в H.264 без звука. Источником может быть RTSP, HTTP или локальный файл.
    """
    timeout_seconds = duration_seconds + extra_timeout_seconds
    error = _attempt(source_url, duration_seconds, output_path, timeout_seconds, transcode=False)
    if error is None:
        return
    logger.warning("Копирование потока не удалось (%s), повтор с перекодированием", error)
    error = _attempt(source_url, duration_seconds, output_path, timeout_seconds, transcode=True)
    if error is not None:
        raise RecordingError(error)
