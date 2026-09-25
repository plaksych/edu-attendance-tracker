import hashlib
import tempfile
import threading
import subprocess
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from app.config import settings
from app.db import retry_delay
from app.detector import PersonDetector
from app.media_keys import annotated_object_key
from app.processor import JobProcessor, ProcessingError
from app.runner import ChildFailure, LeaseLost, run_child


class SecurityTests(unittest.TestCase):
    def test_child_runtime_applies_thread_budget_to_all_pools(self):
        from app.execute import configure_runtime

        cv = SimpleNamespace(setNumThreads=Mock())
        torch = SimpleNamespace(set_num_threads=Mock(), set_num_interop_threads=Mock())
        torch_utils = SimpleNamespace(NUM_THREADS=16)
        utils = SimpleNamespace(NUM_THREADS=16, torch_utils=torch_utils)
        runtime = SimpleNamespace(utils=utils)
        with (
            patch.dict(
                sys.modules,
                {
                    "cv2": cv,
                    "torch": torch,
                    "ultralytics": runtime,
                    "ultralytics.utils": utils,
                    "ultralytics.utils.torch_utils": torch_utils,
                },
            ),
            patch.object(settings, "inference_threads", 2),
        ):
            configure_runtime()
        torch.set_num_threads.assert_called_once_with(2)
        torch.set_num_interop_threads.assert_called_once_with(1)
        cv.setNumThreads.assert_called_once_with(2)
        self.assertEqual(utils.NUM_THREADS, 2)
        self.assertEqual(torch_utils.NUM_THREADS, 2)

    def test_immutable_keys_even_when_attempt_counter_reused(self):
        first = annotated_object_key(1, 1, "00000000-0000-0000-0000-000000000001")
        second = annotated_object_key(1, 1, "00000000-0000-0000-0000-000000000002")
        self.assertNotEqual(first, second)

    def test_missing_weights_never_import_runtime(self):
        with patch.dict("sys.modules", {"ultralytics": None}):
            with self.assertRaises(FileNotFoundError):
                PersonDetector("/nonexistent/model.pt")._get_model()

    def test_wrong_hash_rejected_before_runtime_import(self):
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "model.pt"
            model.write_bytes(b"not an executable checkpoint")
            with patch.object(settings, "model_sha256", "0" * 64):
                with patch.dict("sys.modules", {"ultralytics": None}):
                    with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                        PersonDetector(str(model))._get_model()

    def test_runtime_loads_verified_copy_and_records_actual_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "model.pt"
            model.write_bytes(b"trusted test fixture")
            digest = hashlib.sha256(model.read_bytes()).hexdigest()
            loaded = []

            def factory(path, **kwargs):
                loaded.append(Path(path))
                self.assertNotEqual(Path(path), model)
                self.assertEqual(
                    hashlib.sha256(Path(path).read_bytes()).hexdigest(), digest
                )
                return object()

            with (
                patch.object(settings, "model_sha256", digest),
                patch("app.detector.version", return_value="test"),
            ):
                with patch.dict(
                    "sys.modules", {"ultralytics": SimpleNamespace(YOLO=factory)}
                ):
                    detector = PersonDetector(str(model))
                    detector._get_model()
                    self.assertEqual(detector.metadata["model_sha256"], digest)
                    detector._weights.cleanup()

    def test_backoff_is_bounded_and_jittered(self):
        for attempt in (1, 2, 3, 99):
            ceiling = min(
                settings.retry_max_delay_seconds,
                settings.retry_delay_seconds * 2 ** min(attempt - 1, 16),
            )
            samples = [retry_delay(attempt) for _ in range(20)]
            self.assertTrue(all(ceiling / 2 <= value <= ceiling for value in samples))
            self.assertGreater(len(set(samples)), 1)

    def test_sample_cap_does_not_trust_frame_metadata(self):
        class Capture:
            count = 0

            def read(self):
                self.count += 1
                return (
                    (True, np.zeros((2, 2, 3), dtype=np.uint8))
                    if self.count <= 20
                    else (False, None)
                )

        detector = SimpleNamespace(
            detect=lambda *_: SimpleNamespace(person_count=1, confidences=[])
        )
        with patch.object(settings, "max_sampled_frames", 3):
            samples, _, count = JobProcessor(None, detector)._scan(Capture(), 1, 0.5)
        self.assertEqual(len(samples), 3)
        self.assertEqual(count, 20)

    def test_decoded_budget_is_enforced(self):
        cap = SimpleNamespace(read=lambda: (True, np.zeros((2, 2, 3), dtype=np.uint8)))
        with patch.object(settings, "max_decoded_bytes", 1):
            with self.assertRaises(ProcessingError):
                JobProcessor(None, None)._scan(cap, 1, 0.5)

    def test_lost_lease_terminates_child(self):
        from dataclasses import dataclass

        @dataclass
        class Empty:
            pass

        process = SimpleNamespace(pid=123, poll=lambda: None, wait=lambda: None)
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch("app.runner.subprocess.Popen", return_value=process),
                patch("app.runner.os.killpg") as kill,
            ):
                with self.assertRaises(LeaseLost):
                    run_child(
                        Empty(), Empty(), directory, lambda: False, threading.Event()
                    )
                kill.assert_called_once()

    def test_shutdown_terminates_child_without_publication(self):
        from dataclasses import dataclass

        @dataclass
        class Empty:
            pass

        stop = threading.Event()
        stop.set()
        process = SimpleNamespace(pid=123, poll=lambda: None, wait=lambda: None)
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch("app.runner.subprocess.Popen", return_value=process),
                patch("app.runner.os.killpg") as kill,
            ):
                with self.assertRaisesRegex(ChildFailure, "worker_shutdown"):
                    run_child(Empty(), Empty(), directory, lambda: True, stop)
                kill.assert_called_once()

    def test_real_child_timeout_kills_and_reaps_process(self):
        from dataclasses import dataclass

        @dataclass
        class Empty:
            pass

        popen = subprocess.Popen
        processes = []

        def sleeper(*_args, **kwargs):
            process = popen(
                [sys.executable, "-c", "import time; time.sleep(30)"], **kwargs
            )
            processes.append(process)
            return process

        start = time.monotonic()
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch("app.runner.subprocess.Popen", side_effect=sleeper),
                patch.object(settings, "job_timeout_seconds", 1),
            ):
                with self.assertRaisesRegex(ChildFailure, "processing_timeout"):
                    run_child(
                        Empty(), Empty(), directory, lambda: True, threading.Event()
                    )
        self.assertIsNotNone(processes[0].returncode)
        self.assertLess(time.monotonic() - start, 5)
