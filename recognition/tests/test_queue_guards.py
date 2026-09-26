from types import SimpleNamespace
import unittest

from app.db import Database


class Cursor:
    def __init__(self, rowcounts: list[int]) -> None:
        self._rowcounts = iter(rowcounts)
        self.calls: list[tuple[str, object]] = []
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, params=None) -> None:
        self.calls.append((statement, params))
        self.rowcount = next(self._rowcounts, 0)

    def fetchone(self):
        return None


class Connection:
    closed = False

    def __init__(self, cursor: Cursor) -> None:
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self._cursor

    def close(self) -> None:
        pass


def result() -> SimpleNamespace:
    return SimpleNamespace(
        people_count=12,
        detected_median=12.0,
        detected_percentile_75=13.0,
        detected_max=15,
        average_confidence=0.9,
        count_stddev=0.5,
        sampled_frames=20,
        source_frames=500,
        source_duration_ms=20_000,
        representative_frame_ms=10_000,
        absolute_error=1,
        relative_error=0.05,
        within_tolerance=True,
        annotated_bucket="clips",
        annotated_object_key="annotated/15.jpg",
        inference_metadata={"model_sha256": "a" * 64},
    )


class RecognitionQueueGuardTests(unittest.TestCase):
    def database(self, rowcounts: list[int]) -> tuple[Database, Cursor]:
        cursor = Cursor(rowcounts)
        connection = Connection(cursor)
        database = Database("postgresql://unused")
        database._connection = lambda: connection  # type: ignore[method-assign]
        return database, cursor

    def test_lost_lease_does_not_insert_result(self) -> None:
        database, cursor = self.database([0])

        completed = database.complete_job(42, "claim-1", result())

        self.assertFalse(completed)
        self.assertEqual(len(cursor.calls), 2)
        self.assertIn("status = 'processing'", cursor.calls[0][0])
        self.assertIn("claim_token = %s", cursor.calls[0][0])
        self.assertIn("lease_until > clock_timestamp()", cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1][-1], "claim-1")

    def test_owned_job_updates_state_before_result_insert(self) -> None:
        database, cursor = self.database([1, 1])

        completed = database.complete_job(42, "claim-1", result())

        self.assertTrue(completed)
        self.assertEqual(len(cursor.calls), 2)
        self.assertIn("UPDATE recognition_jobs", cursor.calls[0][0])
        self.assertIn("INSERT INTO recognition_results", cursor.calls[1][0])


if __name__ == "__main__":
    unittest.main()
