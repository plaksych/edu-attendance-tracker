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
        self.rowcount = next(self._rowcounts)


class Connection:
    closed = False

    def __init__(self, cursor: Cursor) -> None:
        self._cursor = cursor

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


class CaptureQueueGuardTests(unittest.TestCase):
    def database(self, rowcounts: list[int]) -> tuple[Database, Cursor]:
        cursor = Cursor(rowcounts)
        connection = Connection(cursor)
        database = Database("postgresql://unused")
        database._connection = lambda: connection  # type: ignore[method-assign]
        return database, cursor

    def test_completed_capture_does_not_enqueue_recognition_after_lease_loss(self) -> None:
        database, cursor = self.database([0])

        completed = database.mark_completed(
            15, "worker-1", "clips", "original/15.mp4", 1024, 20_000
        )

        self.assertFalse(completed)
        self.assertEqual(len(cursor.calls), 1)
        self.assertIn("status = 'uploading'", cursor.calls[0][0])

    def test_completed_capture_enqueues_recognition_only_after_state_update(self) -> None:
        database, cursor = self.database([1, 1])

        completed = database.mark_completed(
            15, "worker-1", "clips", "original/15.mp4", 1024, 20_000
        )

        self.assertTrue(completed)
        self.assertEqual(len(cursor.calls), 2)
        self.assertIn("INSERT INTO recognition_jobs", cursor.calls[1][0])


if __name__ == "__main__":
    unittest.main()
