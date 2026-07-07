"""Обёртка над YOLOv8: подсчёт людей на кадре."""

import logging
import threading
from dataclasses import dataclass

import numpy as np

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

    def _get_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from ultralytics import YOLO

                    logger.info("Загрузка модели %s", self._model_path)
                    self._model = YOLO(self._model_path)
        return self._model

    def detect(self, frame: np.ndarray, conf: float) -> Detection:
        model = self._get_model()
        with self._lock:
            results = model.predict(
                frame,
                classes=[PERSON_CLASS_ID],
                conf=conf,
                verbose=False,
            )
        result = results[0]
        confidences = result.boxes.conf.tolist() if result.boxes is not None else []
        return Detection(
            person_count=len(confidences),
            confidences=[float(value) for value in confidences],
            annotated_frame=result.plot(),
        )
