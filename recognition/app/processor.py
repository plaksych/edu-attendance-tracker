"""Обработка заданий: входной файл из MinIO, агрегаты и размеченный кадр."""

import logging
import math
import os
import shutil
import statistics
import tempfile
from dataclasses import dataclass
from pathlib import Path

import cv2

from app.config import settings
from app.db import ClaimedJob, SourceContext
from app.detector import Detection, PersonDetector
from app.storage import ObjectStorage, annotated_object_key, upload_annotated_object_key

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
    """Скачивает видео или изображение, запускает детектор и сохраняет кадр."""

    def __init__(self, storage: ObjectStorage, detector: PersonDetector) -> None:
        self._storage = storage
        self._detector = detector

    def process(self, job: ClaimedJob, context: SourceContext) -> ProcessingResult:
        tmp_dir = tempfile.mkdtemp(prefix="recognition-")
        try:
            source_path = os.path.join(tmp_dir, self._source_filename(context))
            self._storage.download(
                context.original_bucket, context.original_object_key or "", source_path
            )
            if context.media_type == "image":
                return self._process_image(job, context, source_path, tmp_dir)
            if context.media_type == "video":
                return self._process_video(job, context, source_path, tmp_dir)
            raise ProcessingError("неподдерживаемый тип входного файла")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @staticmethod
    def _source_filename(context: SourceContext) -> str:
        suffix = Path(context.filename or "").suffix.lower()
        if not suffix:
            suffix = ".jpg" if context.media_type == "image" else ".mp4"
        return f"source{suffix}"

    def _process_image(
        self,
        job: ClaimedJob,
        context: SourceContext,
        source_path: str,
        tmp_dir: str,
    ) -> ProcessingResult:
        frame = cv2.imread(source_path)
        if frame is None:
            raise ProcessingError("не удалось открыть изображение")

        detection = self._detector.detect(frame, job.confidence_threshold)
        object_key = self._annotated_key(context)
        self._store_annotated(tmp_dir, detection, object_key)

        count = detection.person_count
        return ProcessingResult(
            people_count=count,
            detected_median=float(count),
            detected_percentile_75=float(count),
            detected_max=count,
            average_confidence=(
                round(statistics.fmean(detection.confidences), 4)
                if detection.confidences
                else None
            ),
            sampled_frames=1,
            representative_frame_ms=0,
            annotated_bucket=settings.minio_bucket,
            annotated_object_key=object_key,
        )

    def _process_video(
        self,
        job: ClaimedJob,
        context: SourceContext,
        source_path: str,
        tmp_dir: str,
    ) -> ProcessingResult:
        cap = cv2.VideoCapture(source_path)
        try:
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
            detection = self._render_annotated(
                cap, best_index, job.confidence_threshold
            )

            object_key = self._annotated_key(context)
            self._store_annotated(tmp_dir, detection, object_key)
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
            cap.release()

    def _annotated_key(self, context: SourceContext) -> str:
        if context.source_kind == "upload":
            if context.upload_id is None:
                raise ProcessingError("для загруженного файла не указан идентификатор")
            return upload_annotated_object_key(context.upload_id)
        if None in (context.session_id, context.measurement_id, context.camera_id):
            raise ProcessingError("для записи камеры не хватает контекста")
        return annotated_object_key(
            context.session_id, context.measurement_id, context.camera_id
        )

    def _store_annotated(
        self, tmp_dir: str, detection: Detection, object_key: str
    ) -> None:
        annotated_path = os.path.join(tmp_dir, "annotated.jpg")
        written = cv2.imwrite(
            annotated_path,
            detection.annotated_frame,
            [cv2.IMWRITE_JPEG_QUALITY, settings.jpeg_quality],
        )
        if not written:
            raise ProcessingError("не удалось сохранить размеченный кадр")
        self._storage.upload(object_key, annotated_path, "image/jpeg")

    def _scan(
        self, cap: cv2.VideoCapture, step: int, conf: float
    ) -> tuple[list[tuple[int, int]], list[float], int]:
        """Первый проход: каждый step-й кадр через детектор, без хранения кадров в памяти."""
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
        """Кадр с числом людей ближе всего к итогу; при равенстве — ближе к центру."""
        middle = total_frames / 2
        best_index, _ = min(
            samples,
            key=lambda item: (abs(item[1] - people_count), abs(item[0] - middle)),
        )
        return best_index

    def _render_annotated(
        self, cap: cv2.VideoCapture, frame_index: int, conf: float
    ) -> Detection:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = cap.read()
        if not ok:
            raise ProcessingError("не удалось перечитать репрезентативный кадр")
        return self._detector.detect(frame, conf)


def _percentile_75(counts: list[int]) -> float:
    if len(counts) == 1:
        return float(counts[0])
    ordered = sorted(counts)
    index = math.ceil(0.75 * (len(ordered) - 1))
    return float(ordered[index])
