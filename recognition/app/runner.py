"""Parent-side child supervision; leases never depend on a decoder thread."""

import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

from app.config import settings


class LeaseLost(Exception):
    pass


class ChildFailure(Exception):
    def __init__(self, code: str, permanent: bool = False):
        super().__init__(code)
        self.permanent = permanent


def run_child(job, context, directory: str, heartbeat, stop):
    root = Path(directory)
    request, response = root / "request.json", root / "response.json"
    request.write_text(
        json.dumps(
            {
                "job": asdict(job),
                "context": asdict(context),
                "source": str(root / "source"),
                "annotated": str(root / "annotated.jpg"),
            }
        )
    )
    # Decoder/inference processes do not need DB or storage credentials.
    env = {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "PYTHONPATH", "SYSTEMROOT", "LANG", "LC_ALL"}
    }
    for key in (
        "model_path",
        "model_sha256",
        "inference_image_size",
        "inference_iou_threshold",
        "inference_max_detections",
        "max_sampled_frames",
        "evaluation_tolerance_people",
        "jpeg_quality",
        "job_timeout_seconds",
        "cpu_limit_seconds",
        "memory_limit_mb",
        "max_file_size_mb",
        "max_image_pixels",
        "max_video_frames",
        "max_video_duration_seconds",
        "max_decoded_bytes",
        "minio_bucket",
    ):
        env[key.upper()] = str(getattr(settings, key))
    env.update(
        {
            "TMPDIR": directory,
            "HOME": directory,
            "YOLO_CONFIG_DIR": directory,
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "YOLO_OFFLINE": "true",
            "YOLO_AUTOINSTALL": "false",
            "WORKER_CHILD": "1",
        }
    )
    deadline = time.monotonic() + settings.job_timeout_seconds
    process = subprocess.Popen(
        [sys.executable, "-m", "app.execute", str(request), str(response)],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    next_heartbeat = time.monotonic()
    try:
        while process.poll() is None:
            if stop.is_set():
                raise ChildFailure("worker_shutdown")
            if time.monotonic() >= deadline:
                raise ChildFailure("processing_timeout", permanent=True)
            if time.monotonic() >= next_heartbeat:
                if not heartbeat():
                    raise LeaseLost()
                next_heartbeat = time.monotonic() + settings.heartbeat_interval_seconds
            stop.wait(0.1)
        if not response.exists() or response.stat().st_size > 65536:
            raise ChildFailure("processing_resource_limit", permanent=True)
        payload = json.loads(response.read_text())
        if process.returncode or "error" in payload:
            code = payload.get("error", "processing_failed")
            raise ChildFailure(
                code,
                permanent=code
                in {
                    "ValueError",
                    "ProcessingError",
                    "UnidentifiedImageError",
                    "DecompressionBombError",
                    "DecompressionBombWarning",
                    "CalledProcessError",
                },
            )
        return payload["result"]
    finally:
        # Also kill decoder descendants after a child exits unexpectedly.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
