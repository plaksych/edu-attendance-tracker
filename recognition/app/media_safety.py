"""Bound input decoding and deny protocols in uploaded containers."""

import json
import math
import subprocess
import warnings
from pathlib import Path

from PIL import Image

from app.config import settings


def validate_image(path: str) -> None:
    Image.MAX_IMAGE_PIXELS = settings.max_image_pixels
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(path) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("unsupported_image_format")
            if image.width * image.height > settings.max_image_pixels:
                raise ValueError("image_pixel_limit")
            image.verify()


def normalize_video(path: str, directory: str) -> str:
    # Input is a cached pipe, not a URL. Cache permits seeking in ordinary MP4.
    # Referenced local files and network URLs are
    # unavailable to demuxers; only the generated AVI reaches OpenCV.
    with open(path, "rb") as source:
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-protocol_whitelist",
                "cache,pipe",
                "-i",
                "cache:pipe:0",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,duration,nb_frames:format=duration",
                "-of",
                "json",
            ],
            stdin=source,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=20,
            check=True,
        )
    info = json.loads(probe.stdout)
    stream = info["streams"][0]
    width, height = int(stream["width"]), int(stream["height"])
    if min(width, height) <= 0 or width * height > settings.max_image_pixels:
        raise ValueError("video_pixel_limit")
    duration = float(stream.get("duration", info.get("format", {}).get("duration", 0)))
    if not math.isfinite(duration) or duration > settings.max_video_duration_seconds:
        raise ValueError("video_duration_limit")
    output = str(Path(directory) / "sanitized.avi")
    with open(path, "rb") as source:
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-protocol_whitelist",
                "cache,pipe",
                "-threads",
                "1",
                "-i",
                "cache:pipe:0",
                "-map",
                "0:v:0",
                "-an",
                "-sn",
                "-dn",
                "-t",
                str(settings.max_video_duration_seconds + 1),
                "-frames:v",
                str(settings.max_video_frames + 1),
                "-c:v",
                "mjpeg",
                "-q:v",
                "3",
                "-threads",
                "1",
                "-y",
                output,
            ],
            stdin=source,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=settings.job_timeout_seconds,
            check=True,
        )
    return output
