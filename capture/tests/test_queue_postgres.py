import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg2

from app.db import Database

DSN = os.environ.get("QUEUE_TEST_DSN")


@unittest.skipUnless(DSN, "QUEUE_TEST_DSN not set")
class CapturePostgresTests(unittest.TestCase):
    def setUp(self):
        self.schema = "capture_test_" + uuid.uuid4().hex
        self.control = psycopg2.connect(DSN)
        self.control.autocommit = True
        self.databases = []
        with self.control.cursor() as cur:
            cur.execute(f"CREATE SCHEMA {self.schema}")
            cur.execute(f"SET search_path TO {self.schema}")
            cur.execute("""CREATE TABLE cameras(id int PRIMARY KEY, enabled bool DEFAULT true,
                capture_group text DEFAULT 'default', rtsp_url text);
                CREATE TABLE measurements(id int PRIMARY KEY, session_id int);
                CREATE TABLE camera_captures(id serial PRIMARY KEY, measurement_id int DEFAULT 1,
                camera_id int DEFAULT 1, planned_at timestamptz DEFAULT now(),
                duration_seconds int DEFAULT 20, attempts int DEFAULT 0, status text DEFAULT 'pending',
                worker_id text, claim_token varchar(36), lease_until timestamptz,
                updated_at timestamptz DEFAULT now(), capture_started_at timestamptz,
                capture_finished_at timestamptz, original_bucket text, original_object_key text,
                content_type text, size_bytes bigint, duration_ms int, error text);
                CREATE TABLE recognition_jobs(id serial PRIMARY KEY, camera_capture_id int UNIQUE);
                INSERT INTO cameras(id, rtsp_url) VALUES (1, 'encrypted:test');
                INSERT INTO measurements(id, session_id) VALUES (1, 1)""")

    def tearDown(self):
        for database in self.databases:
            database.close()
        with self.control.cursor() as cur:
            cur.execute(f"DROP SCHEMA {self.schema} CASCADE")
        self.control.close()

    def database(self):
        database = Database(DSN)
        original = database._connection

        def connection():
            conn = original()
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {self.schema}")
            conn.commit()
            return conn

        database._connection = connection
        self.databases.append(database)
        return database

    def execute(self, sql, params=()):
        with self.control.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall() if cur.description else None

    def claim(self, database):
        return database.claim_batch("same-worker", "default", 10, 300, 1)

    def test_multiple_workers_claim_distinct_captures(self):
        self.execute(
            "INSERT INTO camera_captures(camera_id) SELECT 1 FROM generate_series(1,4)"
        )
        databases = [self.database() for _ in range(4)]
        with ThreadPoolExecutor(max_workers=4) as executor:
            tasks = [batch[0] for batch in executor.map(self.claim, databases)]
        self.assertEqual(len({task.id for task in tasks}), 4)

    def test_stale_worker_cannot_transition_release_or_complete(self):
        self.execute("INSERT INTO camera_captures DEFAULT VALUES")
        database = self.database()
        old = self.claim(database)[0]
        self.execute(
            "UPDATE camera_captures SET lease_until = now() - interval '1 second'"
        )
        self.assertFalse(
            database.mark_recording(old.id, "same-worker", old.claim_token, 300)
        )
        self.execute(
            "UPDATE camera_captures SET status = 'pending', claim_token = NULL"
        )
        new = self.claim(database)[0]
        self.assertEqual(
            database.release_claims([(old.id, old.claim_token)], "same-worker"), 0
        )
        self.assertTrue(
            database.mark_recording(new.id, "same-worker", new.claim_token, 300)
        )
        self.assertFalse(
            database.heartbeat(old.id, "same-worker", old.claim_token, 300)
        )
        self.assertFalse(
            database.mark_uploading(old.id, "same-worker", old.claim_token)
        )
        self.assertTrue(database.mark_uploading(new.id, "same-worker", new.claim_token))
        self.assertFalse(
            database.mark_completed(
                old.id, "same-worker", old.claim_token, "bucket", "old.mp4", 1024, 1000
            )
        )
        self.assertTrue(
            database.mark_completed(
                new.id, "same-worker", new.claim_token, "bucket", "new.mp4", 1024, 1000
            )
        )
        database.close()
        self.assertTrue(
            database.mark_completed(
                new.id, "same-worker", new.claim_token, "bucket", "new.mp4", 1024, 1000
            )
        )
        self.assertEqual(self.execute("SELECT count(*) FROM recognition_jobs"), [(1,)])
        self.assertEqual(
            self.execute("SELECT original_object_key FROM camera_captures"),
            [("new.mp4",)],
        )
