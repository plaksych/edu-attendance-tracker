"""Set process limits before exec; safe when the parent is multithreaded."""

import os
import resource
import sys

from app.config import get_settings


def main():
    settings = get_settings()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(
        resource.RLIMIT_FSIZE, (settings.max_capture_size_mb * 1024 * 1024,) * 2
    )
    resource.setrlimit(
        resource.RLIMIT_CPU, (settings.max_capture_duration_seconds + 30,) * 2
    )
    if sys.platform == "linux":
        resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024,) * 2)
    os.execvp("ffmpeg", ["ffmpeg", *sys.argv[1:]])


if __name__ == "__main__":
    main()
