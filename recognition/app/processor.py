"""Обработка одного задания: видео из MinIO → агрегаты по людям и размеченный кадр."""

import logging
import math
import os
import shutil
import statistics
import tempfile
from dataclasses import dataclass

import cv2

from app.config import settings
from app.db import CaptureContext, ClaimedJob
from app.detector import PersonDetector
from app.storage import ObjectStorage, annotated_object_key

logger = logging.getLogger(__name__)

DEFAULT_FPS = 25.0


class ProcessingError(Exception):
    """Ошибка обработки, текст которой пригоден для поля error задания."""


@dataclass
class ProcessingResult:
    people_count: int
    detected_median: float
    detected_percentile_75: float
    detected_max: int
    average_confidence: float | None
    sampled_frames: int
    representative_frame_ms: int
    annotated_bucket: str
    annotated_object_key: str


class JobProcessor:
    """Скачивает ролик, сэмплирует кадры детектором и собирает агрегаты."""

    def __init__(self, storage: ObjectStorage, detector: PersonDetector) -> None:
        self._storage = storage
        self._detector = detector

    def process(self, job: ClaimedJob, context: CaptureContext) -> ProcessingResult:
        tmp_dir = tempfile.mkdtemp(prefix="recognition-")
        cap = None
        try:
            video_path = os.path.join(tmp_dir, "source.mp4")
            self._storage.download(
                context.original_bucket, context.original_object_key, video_path
            )

            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ProcessingError("не удалось открыть видеофайл")

            fps = cap.get(cv2.CAP_PROP_FPS)
            if not fps or math.isnan(fps) or fps <= 0:
                fps = DEFAULT_FPS
            sample_rate = job.sample_rate_fps if job.sample_rate_fps > 0 else 1.0
            step = max(1, round(fps / sample_rate))

            samples, confidences, total_frames = self._scan(
                cap, step, job.confidence_threshold
            )
            if not samples:
                raise ProcessingError("не удалось прочитать кадры видео")

            counts = [count for _, count in samples]
            median = float(statistics.median(counts))
            people_count = round(median)
            best_index = self._representative_frame(samples, people_count, total_frames)

            annotated_path = os.path.join(tmp_dir, "annotated.jpg")
            self._render_annotated(
                cap, best_index, job.confidence_threshold, annotated_path
            )

            object_key = annotated_object_key(
                context.session_id, context.measurement_id, context.camera_id
            )
            self._storage.upload(object_key, annotated_path, "image/jpeg")

            logger.info(
                "Задание %s: кадров %s, людей %s (медиана %.1f, максимум %s)",
                job.id,
                len(samples),
                people_count,
                median,
                max(counts),
            )
            return ProcessingResult(
                people_count=people_count,
                detected_median=median,
                detected_percentile_75=_percentile_75(counts),
                detected_max=max(counts),
                average_confidence=(
                    round(statistics.fmean(confidences), 4) if confidences else None
                ),
                sampled_frames=len(samples),
                representative_frame_ms=int(best_index / fps * 1000),
                annotated_bucket=settings.minio_bucket,
                annotated_object_key=object_key,
            )
        finally:
            if cap is not None:
                cap.release()
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _scan(
        self, cap: cv2.VideoCapture, step: int, conf: float
    ) -> tuple[list[tuple[int, int]], list[float], int]:
        """Первый проход: каждый step-й кадр через детектор, кадры в память не складываем."""
        samples: list[tuple[int, int]] = []
        confidences: list[float] = []
        frame_index = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_index % step == 0:
                detection = self._detector.detect(frame, conf)
                samples.append((frame_index, detection.person_count))
                confidences.extend(detection.confidences)
            frame_index += 1
        return samples, confidences, frame_index

    @staticmethod
    def _representative_frame(
        samples: list[tuple[int, int]], people_count: int, total_frames: int
    ) -> int:
        """Кадр с числом людей ближе всего к итогу; при равенстве — ближе к середине ролика."""
        middle = total_frames / 2
        best_index, _ = min(
            samples,
            key=lambda item: (abs(item[1] - people_count), abs(item[0] - middle)),
        )
        return best_index

    def _render_annotated(
        self, cap: cv2.VideoCapture, frame_index: int, conf: float, output_path: str
    ) -> None:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = cap.read()
        if not ok:
            raise ProcessingError("не удалось перечитать репрезентативный кадр")
        detection = self._detector.detect(frame, conf)
        written = cv2.imwrite(
            output_path,
            detection.annotated_frame,
            [cv2.IMWRITE_JPEG_QUALITY, settings.jpeg_quality],
        )
        if not written:
            raise ProcessingError("не удалось сохранить размеченный кадр")


def _percentile_75(counts: list[int]) -> float:
    if len(counts) == 1:
        return float(counts[0])
    ordered = sorted(counts)
    index = math.ceil(0.75 * (len(ordered) - 1))
    return float(ordered[index])
