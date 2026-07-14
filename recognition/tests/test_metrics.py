import unittest

from app.metrics import calculate_count_metrics
from app.processor import JobProcessor


class RecognitionMetricTests(unittest.TestCase):
    def test_compares_median_with_reference_count(self) -> None:
        metrics = calculate_count_metrics([8, 9, 8, 7, 8], 9, tolerance_people=1)

        self.assertEqual(metrics.absolute_error, 1)
        self.assertAlmostEqual(metrics.relative_error or 0, 1 / 9)
        self.assertTrue(metrics.within_tolerance)
        self.assertGreater(metrics.count_stddev, 0)

    def test_zero_reference_has_absolute_but_no_relative_error(self) -> None:
        metrics = calculate_count_metrics([0], 0, tolerance_people=0)

        self.assertEqual(metrics.absolute_error, 0)
        self.assertIsNone(metrics.relative_error)
        self.assertTrue(metrics.within_tolerance)

    def test_sampling_step_limits_large_video(self) -> None:
        self.assertEqual(JobProcessor._sampling_step(25, 1, 10_000), 56)
        self.assertEqual(JobProcessor._sampling_step(25, 2, 100), 12)
