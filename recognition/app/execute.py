"""Private child entrypoint. No DB or object-store clients in this process."""

import json
import errno
import os
import resource
import shutil
import sys
import socket
from dataclasses import asdict
from pathlib import Path

from app.config import settings


def apply_limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (settings.cpu_limit_seconds,) * 2)
    resource.setrlimit(
        resource.RLIMIT_FSIZE, (settings.max_file_size_mb * 1024 * 1024,) * 2
    )
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    # RLIMIT_AS is meaningful on Linux, unlike macOS's allocator behavior.
    if sys.platform == "linux":
        resource.setrlimit(
            resource.RLIMIT_AS, (settings.memory_limit_mb * 1024 * 1024,) * 2
        )
        import pyseccomp as seccomp

        policy = seccomp.SyscallFilter(defaction=seccomp.ALLOW)
        for family in (socket.AF_INET, socket.AF_INET6, socket.AF_PACKET):
            policy.add_rule(
                seccomp.ERRNO(errno.EPERM), "socket", seccomp.Arg(0, seccomp.EQ, family)
            )
        policy.add_rule(seccomp.ERRNO(errno.EPERM), "io_uring_setup")
        policy.load()


class LocalStorage:
    def __init__(self, source: str, annotated: str):
        self.source, self.annotated = source, annotated

    def download(self, _bucket, _key, destination):
        os.link(self.source, destination)

    def upload(self, _key, source, _content_type):
        shutil.copyfile(source, self.annotated)


def main() -> None:
    apply_limits()
    request = json.loads(Path(sys.argv[1]).read_text())
    output = Path(sys.argv[2])
    try:
        # Imports happen after process resource limits and thread environment.
        from app.db import ClaimedJob, SourceContext
        from app.detector import PersonDetector
        from app.processor import JobProcessor

        processor = JobProcessor(
            LocalStorage(request["source"], request["annotated"]),
            PersonDetector(settings.model_path),
        )
        result = processor.process(
            ClaimedJob(**request["job"]), SourceContext(**request["context"])
        )
        output.write_text(json.dumps({"result": asdict(result)}, allow_nan=False))
    except Exception as exc:
        # Raw decoder/model errors can contain paths, URLs, or credentials.
        output.write_text(json.dumps({"error": type(exc).__name__}))
        sys.exit(2)


if __name__ == "__main__":
    os.umask(0o077)
    main()
