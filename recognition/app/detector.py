"""Обёртка над YOLOv8: подсчёт людей на кадре."""

import logging
import threading
from dataclasses import dataclass

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

PERSON_CLASS_ID = 0


@dataclass
class DetectionResult:
    person_count: int
    avg_confidence: float | None
    annotated_frame: np.ndarray


class PersonDetector:
    """Потокобезопасный детектор: модель загружается один раз при первом обращении."""

    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()

    def _get_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from ultralytics import YOLO

                    logger.info("Загрузка модели %s", settings.model_path)
                    self._model = YOLO(settings.model_path)
        return self._model

    def detect(self, frame: np.ndarray) -> DetectionResult:
        model = self._get_model()
        with self._lock:
            results = model.predict(
                frame,
                classes=[PERSON_CLASS_ID],
                conf=settings.confidence_threshold,
                verbose=False,
            )
        result = results[0]
        confidences = result.boxes.conf.tolist() if result.boxes is not None else []
        return DetectionResult(
            person_count=len(confidences),
            avg_confidence=round(sum(confidences) / len(confidences), 4)
            if confidences
            else None,
            annotated_frame=result.plot(),
        )


detector = PersonDetector()
