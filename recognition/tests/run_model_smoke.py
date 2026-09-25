"""Explicit opt-in real CPU smoke. Never collected by ordinary unittest discovery.

Run with an isolated environment containing the pinned server dependencies:
  PYTHONPATH=recognition /tmp/venv/bin/python recognition/tests/run_model_smoke.py --output /tmp/smoke
"""

import argparse
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import time


def installed_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def child(kind: str, directory: Path) -> None:
    from app.execute import LocalStorage, apply_limits, configure_runtime

    apply_limits()

    import cv2
    import torch

    configure_runtime()

    from app.config import settings
    from app.db import ClaimedJob, SourceContext
    from app.detector import PersonDetector
    from app.processor import JobProcessor
    from dataclasses import asdict

    token = "00000000-0000-0000-0000-000000000001"
    source = directory / ("blank.png" if kind == "image" else "blank.mp4")
    annotated = directory / f"{kind}-annotated.jpg"
    detector = PersonDetector(settings.model_path)
    processor = JobProcessor(LocalStorage(str(source), str(annotated)), detector)
    job = ClaimedJob(1 if kind == "image" else 2, None, 1, 2.0, 0.35, 1, token)
    context = SourceContext(
        "upload", kind, "smoke-only", "synthetic", source.name, None, None, None, 1, 0
    )
    started = time.perf_counter()
    result = processor.process(job, context)
    elapsed = time.perf_counter() - started
    device = str(detector._model.predictor.device)
    assert device == "cpu", device
    assert torch.get_num_threads() == 1
    assert torch.get_num_interop_threads() == 1
    assert result.people_count == 0, result.people_count
    assert result.inference_metadata["model_sha256"] == settings.model_sha256
    assert result.sampled_frames >= 1
    assert annotated.is_file() and cv2.imread(str(annotated)) is not None
    usage = resource.getrusage(resource.RUSAGE_SELF)
    payload = {
        "status": "passed",
        "media_type": kind,
        "device": device,
        "torch_version": torch.__version__,
        "torch_threads": torch.get_num_threads(),
        "torch_interop_threads": torch.get_num_interop_threads(),
        "pipeline_seconds": round(elapsed, 4),
        "process_cpu_seconds": round(usage.ru_utime + usage.ru_stime, 4),
        "peak_rss_mib": round(
            usage.ru_maxrss / (1048576 if sys.platform == "darwin" else 1024), 2
        ),
        "result": asdict(result),
        "annotated_path": str(annotated),
    }
    (directory / f"{kind}-result.json").write_text(json.dumps(payload, indent=2))
    if detector._weights is not None:
        detector._weights.cleanup()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--child", choices=("image", "video"))
    args = parser.parse_args()
    directory = args.output.resolve()
    if args.child:
        child(args.child, directory)
        return

    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "model-manifest.json").read_text())
    weights = root.parent / "yolov8n.pt"
    with weights.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    if digest != manifest["sha256"]:
        raise ValueError("Repository weights differ from the reviewed manifest")
    from PIL import Image

    Image.new("RGB", (96, 64), color="black").save(directory / "blank.png")
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=64x64:d=0.5:r=4",
            "-threads",
            "1",
            "-c:v",
            "mpeg4",
            "-y",
            str(directory / "blank.mp4"),
        ],
        check=True,
        timeout=10,
    )

    env = {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "LANG", "LC_ALL", "SYSTEMROOT"}
    }
    env.update(
        {
            "PYTHONPATH": str(root),
            "WORKER_CHILD": "1",
            "MODEL_PATH": str(weights),
            "MODEL_SHA256": digest,
            "HOME": str(directory),
            "TMPDIR": str(directory),
            "YOLO_CONFIG_DIR": str(directory / "yolo"),
            "MPLCONFIGDIR": str(directory / "matplotlib"),
            "YOLO_OFFLINE": "true",
            "YOLO_AUTOINSTALL": "false",
            "CUDA_VISIBLE_DEVICES": "",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "VECLIB_MAXIMUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "CPU_LIMIT_SECONDS": "30",
            "MEMORY_LIMIT_MB": "1536",
            "MAX_FILE_SIZE_MB": "32",
            "JOB_TIMEOUT_SECONDS": "30",
            "MAX_SAMPLED_FRAMES": "2",
            "MAX_VIDEO_FRAMES": "4",
            "MAX_VIDEO_DURATION_SECONDS": "2",
            "MAX_IMAGE_PIXELS": "1000000",
            "MAX_DECODED_BYTES": "1000000",
            "INFERENCE_IMAGE_SIZE": "960",
        }
    )
    results = []
    for kind in ("image", "video"):
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--output",
            str(directory),
            "--child",
            kind,
        ]
        if sys.platform == "darwin" and shutil.which("sandbox-exec"):
            command = [
                "sandbox-exec",
                "-p",
                "(version 1)(allow default)(deny network*)",
                *command,
            ]
        started = time.perf_counter()
        with (directory / f"{kind}.log").open("wb") as log:
            process = subprocess.Popen(
                command,
                env=env,
                start_new_session=True,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                code = process.wait(timeout=45)
                if code:
                    raise subprocess.CalledProcessError(code, command)
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
        result = json.loads((directory / f"{kind}-result.json").read_text())
        result["child_wall_seconds"] = round(time.perf_counter() - started, 4)
        results.append(result)
    evidence = {
        "python": sys.version,
        "model_sha256": digest,
        "network_policy": "deny network*"
        if sys.platform == "darwin"
        else "Linux seccomp",
        "installed_dependencies": {
            name: installed_version(name)
            for name in (
                "torch",
                "torchvision",
                "ultralytics",
                "Pillow",
                "cryptography",
                "numpy",
                "opencv-python-headless",
            )
        },
        "security_audit": {
            "report": "scripts/ops/evidence/dependency-audit/summary.json",
            "scope": "Reported separately; inference smoke does not assess vulnerabilities.",
        },
        "cases": results,
    }
    (directory / "evidence.json").write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
