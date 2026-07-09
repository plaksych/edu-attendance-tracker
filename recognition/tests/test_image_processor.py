import unittest

import cv2
import numpy as np

from app.db import ClaimedJob, SourceContext
from app.detector import Detection
from app.processor import JobProcessor


class Storage:
    def __init__(self) -> None:
        self.uploaded: tuple[str, str, np.ndarray] | None = None

    def download(self, _bucket: str, _key: str, destination: str) -> None:
        frame = np.full((12, 16, 3), 180, dtype=np.uint8)
        if not cv2.imwrite(destination, frame):
            raise AssertionError("Не удалось подготовить входное изображение")

    def upload(self, object_key: str, file_path: str, content_type: str) -> None:
        frame = cv2.imread(file_path)
        if frame is None:
            raise AssertionError("Не удалось прочитать размеченный кадр")
        self.uploaded = (object_key, content_type, frame)


class Detector:
    def detect(self, frame: np.ndarray, _confidence: float) -> Detection:
        return Detection(
            person_count=3,
            confidences=[0.91, 0.88, 0.84],
            annotated_frame=frame,
        )


class ImageProcessorTests(unittest.TestCase):
    def test_image_job_creates_single_frame_result_and_annotated_object(self) -> None:
        storage = Storage()
        processor = JobProcessor(storage=storage, detector=Detector())
        job = ClaimedJob(
            id=7,
            camera_capture_id=None,
            upload_id=42,
            sample_rate_fps=1.0,
            confidence_threshold=0.35,
            attempts=1,
        )
        source = SourceContext(
            source_kind="upload",
            media_type="image",
            original_bucket="attendance-clips",
            original_object_key="original/uploads/example.png",
            filename="example.png",
            camera_id=None,
            measurement_id=None,
            session_id=None,
            upload_id=42,
        )

        result = processor.process(job, source)

        self.assertEqual(result.people_count, 3)
        self.assertEqual(result.sampled_frames, 1)
        self.assertEqual(result.representative_frame_ms, 0)
        self.assertEqual(result.annotated_object_key, "annotated/uploads/42.jpg")
        self.assertIsNotNone(storage.uploaded)
        assert storage.uploaded is not None
        self.assertEqual(storage.uploaded[0], "annotated/uploads/42.jpg")
        self.assertEqual(storage.uploaded[1], "image/jpeg")


if __name__ == "__main__":
    unittest.main()
