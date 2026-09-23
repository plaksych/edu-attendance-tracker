"""Обёртка над YOLOv8: подсчёт людей на кадре."""

import logging
import hashlib
import hmac
import os
import re
import tempfile
import threading
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

PERSON_CLASS_ID = 0


@dataclass
class Detection:
    person_count: int
    confidences: list[float]
    annotated_frame: np.ndarray


class PersonDetector:
    """Потокобезопасный детектор: модель загружается один раз при первом обращении."""

    def __init__(self, model_path: str) -> None:
        self._model_path = model_path
        self._model = None
        self._lock = threading.Lock()
        self.metadata: dict = {}
        self._weights = None

    def _get_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    path = Path(self._model_path).resolve(strict=True)
                    expected = settings.model_sha256.lower()
                    if (
                        not re.fullmatch(r"[0-9a-f]{64}", expected)
                        or path.suffix != ".pt"
                    ):
                        raise ValueError(
                            "A trusted local checkpoint and SHA-256 are required"
                        )
                    # Load the exact private copy we hashed, not a path that can change.
                    self._weights = tempfile.TemporaryDirectory(
                        prefix="verified-model-"
                    )
                    verified = Path(self._weights.name) / "model.pt"
                    digest = hashlib.sha256()
                    with path.open("rb") as source, verified.open("xb") as target:
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            digest.update(chunk)
                            target.write(chunk)
                    if not hmac.compare_digest(digest.hexdigest(), expected):
                        self._weights.cleanup()
                        raise ValueError("Model SHA-256 mismatch")
                    os.environ["YOLO_OFFLINE"] = "true"
                    from ultralytics import YOLO

                    self._model = YOLO(str(verified), task="detect")
                    self.metadata = {
                        "engine": "server",
                        "provenance": "server_inference",
                        "model_name": path.name,
                        "model_sha256": digest.hexdigest(),
                        "runtime": "ultralytics",
                        "runtime_version": version("ultralytics"),
                        "image_size": settings.inference_image_size,
                        "iou_threshold": settings.inference_iou_threshold,
                        "max_detections": settings.inference_max_detections,
                        "person_class_id": PERSON_CLASS_ID,
                    }
        return self._model

    def detect(self, frame: np.ndarray, conf: float) -> Detection:
        model = self._get_model()
        with self._lock:
            results = model.predict(
                frame,
                classes=[PERSON_CLASS_ID],
                conf=conf,
                imgsz=settings.inference_image_size,
                iou=settings.inference_iou_threshold,
                max_det=settings.inference_max_detections,
                verbose=False,
            )
        result = results[0]
        confidences = result.boxes.conf.tolist() if result.boxes is not None else []
        return Detection(
            person_count=len(confidences),
            confidences=[float(value) for value in confidences],
            annotated_frame=result.plot(),
        )
