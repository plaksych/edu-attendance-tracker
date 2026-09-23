"""Queue-only maintenance and dedicated scheduler leadership tests."""

import os
import threading
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.scheduler import run_service
from app.services.scheduler import reap_expired_leases, ensure_camera_captures, measurement_times
from app.maintenance import run_tick, cleanup_orphans, _scan_positions

DSN = os.environ.get("QUEUE_TEST_DSN")


class MaintenanceUnitTests(unittest.TestCase):
    def test_short_session_measurements_are_distinct_and_inside_session(self):
        starts = datetime(2026, 9, 23, 10, tzinfo=timezone.utc)
        for minutes in (1, 10, 20, 29, 30):
            ends = starts + timedelta(minutes=minutes)
            first, second = measurement_times(starts, ends, timedelta(minutes=15))
            with self.subTest(minutes=minutes):
                self.assertLess(starts, first)
                self.assertLess(first, second)
                self.assertLess(second, ends)
                self.assertLessEqual(abs((first - starts) - timedelta(minutes=minutes / 3)),
                                     timedelta(microseconds=1))

    def test_long_session_keeps_configured_offsets(self):
        starts = datetime(2026, 9, 23, 10, tzinfo=timezone.utc)
        ends = starts + timedelta(minutes=90)
        self.assertEqual(measurement_times(starts, ends, timedelta(minutes=15)),
                         (starts + timedelta(minutes=15), ends - timedelta(minutes=15)))

    def test_nonpositive_session_duration_rejected(self):
        starts = datetime(2026, 9, 23, 10, tzinfo=timezone.utc)
        with self.assertRaises(ValueError):
            measurement_times(starts, starts, timedelta(minutes=15))

    def test_storage_failure_does_not_disable_recovery(self):
        with patch("app.maintenance.Session") as session, patch("app.maintenance.reap_expired_leases") as reap:
            with patch("app.maintenance.fail_stale_pending_captures"), patch("app.maintenance.cleanup_orphans", side_effect=OSError):
                run_tick(object())
            reap.assert_called_once_with(session.return_value.__enter__.return_value)

    def test_no_camera_keeps_measurement_available_for_upload(self):
        measurement = SimpleNamespace(session=SimpleNamespace(schedule=SimpleNamespace(classroom_id=None)), status="scheduled", upload=None)
        from unittest.mock import MagicMock
        db = MagicMock()
        db.scalars.return_value.unique.return_value.all.return_value = [measurement]
        self.assertEqual(ensure_camera_captures(db), 0)
        self.assertEqual(measurement.status, "scheduled")

    def test_uploaded_measurement_never_gets_camera_capture(self):
        from unittest.mock import MagicMock
        measurement = SimpleNamespace(upload=object())
        db = MagicMock()
        db.scalars.return_value.unique.return_value.all.return_value = [measurement]
        self.assertEqual(ensure_camera_captures(db), 0)
        db.execute.assert_not_called()
        query = db.scalars.call_args.args[0]
        from sqlalchemy.dialects import postgresql
        sql = str(query.compile(dialect=postgresql.dialect()))
        self.assertIn("FOR UPDATE OF measurements SKIP LOCKED", sql)
        self.assertIn("recognition_uploads", sql)

    def test_cleanup_preserves_referenced_and_live_attempts(self):
        from unittest.mock import MagicMock
        _scan_positions.clear()
        keys = [f"annotated/jobs/{i}/attempts/1/00000000-0000-0000-0000-000000000001.jpg"
                for i in (1, 2, 3)]
        objects = [SimpleNamespace(object_name=key,
                   last_modified=datetime.now(timezone.utc) - timedelta(days=2)) for key in keys]
        client = MagicMock()
        client.list_objects.side_effect = [objects, []]
        with patch("app.maintenance.Session") as session:
            session.return_value.__enter__.return_value.scalar.side_effect = [True, True, False]
            self.assertEqual(cleanup_orphans(object(), client), 1)
        self.assertEqual(client.remove_object.call_args.args[1], keys[2])

    def test_cleanup_never_deletes_recent_objects(self):
        from unittest.mock import MagicMock
        _scan_positions.clear()
        obj = SimpleNamespace(object_name="annotated/jobs/1/attempts/1/00000000-0000-0000-0000-000000000001.jpg",
                              last_modified=datetime.now(timezone.utc))
        client = MagicMock()
        client.list_objects.side_effect = [[obj], []]
        self.assertEqual(cleanup_orphans(object(), client), 0)
        client.remove_object.assert_not_called()


@unittest.skipUnless(DSN, "QUEUE_TEST_DSN not set")
class MaintenancePostgresTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(DSN, poolclass=NullPool)
        self.schema = "maintenance_test_" + uuid.uuid4().hex
        with self.engine.begin() as connection:
            connection.execute(text(f"CREATE SCHEMA {self.schema}"))
            for table in ("recognition_jobs", "camera_captures"):
                connection.execute(text(f"""CREATE TABLE {self.schema}.{table} (
                    id serial PRIMARY KEY, status text, worker_id text, claim_token text,
                    lease_until timestamptz, attempts int, error text,
                    updated_at timestamptz, finished_at timestamptz)"""))

    def tearDown(self):
        with self.engine.begin() as connection:
            connection.execute(text(f"DROP SCHEMA {self.schema} CASCADE"))
        self.engine.dispose()

    def test_upload_recovery_without_any_cameras_or_schedule(self):
        with self.engine.connect() as connection:
            connection.execute(text(f"SET search_path TO {self.schema}"))
            connection.execute(text("""INSERT INTO recognition_jobs(status, attempts, lease_until, claim_token)
                VALUES ('processing', 1, now() - interval '1 second', 'old'),
                ('processing', 999, now() - interval '1 second', 'old'),
                ('retry_wait', 1, now() - interval '1 second', 'old')"""))
            connection.commit()
            with Session(bind=connection) as db:
                reap_expired_leases(db)
            rows = connection.execute(text("SELECT status, claim_token FROM recognition_jobs ORDER BY id")).all()
            self.assertEqual(rows, [("retry_wait", None), ("failed", None), ("pending", None)])
            self.assertTrue(connection.scalar(text("SELECT lease_until > now() FROM recognition_jobs WHERE id=1")))

    def test_second_scheduler_does_no_work_while_lock_held(self):
        stop = threading.Event()
        called = []
        lock = 918267
        with self.engine.connect() as leader:
            leader.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock})
            leader.commit()
            timer = threading.Timer(0.15, stop.set)
            timer.start()
            try:
                run_service(lambda conn: called.append(1), lock, 0.01, stop, self.engine)
            finally:
                timer.join()
                leader.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock})
                leader.commit()
        self.assertEqual(called, [])

    def test_reconnect_reacquires_leadership_on_new_connection(self):
        stop = threading.Event()
        pids = []
        lock = 918268
        def tick(connection):
            pid = connection.scalar(text("SELECT pg_backend_pid()"))
            connection.commit()
            pids.append(pid)
            if len(pids) == 1:
                with self.engine.begin() as killer:
                    killer.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid})
                connection.execute(text("SELECT 1"))
            else:
                stop.set()
        timer = threading.Timer(3, stop.set)
        timer.start()
        try:
            run_service(tick, lock, 0.01, stop, self.engine)
        finally:
            timer.cancel()
            timer.join()
        self.assertEqual(len(pids), 2)
        self.assertNotEqual(pids[0], pids[1])
        with self.engine.connect() as connection:
            self.assertTrue(connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": lock}))
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock})
            connection.commit()
