"""Запись одного ролика с источника через subprocess ffmpeg."""

import logging
import os
import subprocess
import signal
import sys
import threading
import time

from app.config import get_settings

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
    command = [
        sys.executable,
        "-m",
        "app.ffmpeg_exec",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-protocol_whitelist",
        "rtsp,tcp",
        "-rw_timeout",
        "15000000",
        "-threads",
        "1",
    ]
    if source_url.startswith("rtsp://"):
        command += ["-rtsp_transport", "tcp"]
    command += ["-i", source_url, "-t", str(duration_seconds)]
    if transcode:
        command += ["-c:v", "libx264", "-preset", "ultrafast", "-an"]
    else:
        command += ["-c", "copy"]
    command += [
        "-threads",
        "1",
        "-fs",
        str(get_settings().max_capture_size_mb * 1024 * 1024),
        "-movflags",
        "+faststart",
        "-y",
        output_path,
    ]
    return command


def _attempt(
    source_url: str,
    duration_seconds: int,
    output_path: str,
    timeout_seconds: int,
    transcode: bool,
    cancelled: threading.Event | None = None,
) -> str | None:
    """Одна попытка записи; возвращает текст ошибки или None при успехе."""
    command = _build_command(source_url, duration_seconds, output_path, transcode)
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.monotonic() + timeout_seconds
    try:
        while process.poll() is None:
            if cancelled is not None and cancelled.is_set():
                raise RecordingError("capture_cancelled")
            if time.monotonic() >= deadline:
                raise RecordingError("capture_timeout")
            time.sleep(0.1)
    finally:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait()
    if process.returncode != 0:
        return "capture_decoder_failed"
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
    cancelled: threading.Event | None = None,
) -> None:
    """Записывает ролик длиной duration_seconds в output_path.

    Первая попытка копирует поток без перекодирования; если она не дала
    валидный файл, выполняется одна повторная попытка с перекодированием
    в H.264 без звука. Источником может быть RTSP, HTTP или локальный файл.
    """
    if not 1 <= duration_seconds <= get_settings().max_capture_duration_seconds:
        raise ValueError("capture_duration_limit")
    timeout_seconds = duration_seconds + extra_timeout_seconds
    error = _attempt(
        source_url,
        duration_seconds,
        output_path,
        timeout_seconds,
        transcode=False,
        cancelled=cancelled,
    )
    if error is None:
        return
    logger.warning(
        "Копирование потока не удалось (%s), повтор с перекодированием", error
    )
    error = _attempt(
        source_url,
        duration_seconds,
        output_path,
        timeout_seconds,
        transcode=True,
        cancelled=cancelled,
    )
    if error is not None:
        raise RecordingError(error)
