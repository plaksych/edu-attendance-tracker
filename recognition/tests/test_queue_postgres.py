"""Opt-in real PostgreSQL tests; creates/drops only a random temporary schema."""

import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import psycopg2

from app.db import Database
from app.config import settings

DSN = os.environ.get("QUEUE_TEST_DSN")


@unittest.skipUnless(DSN, "QUEUE_TEST_DSN not set")
class PostgresQueueTests(unittest.TestCase):
    def setUp(self):
        self.schema = "queue_test_" + uuid.uuid4().hex
        self.control = psycopg2.connect(DSN)
        self.control.autocommit = True
        self.databases = []
        with self.control.cursor() as cur:
            cur.execute(f"CREATE SCHEMA {self.schema}")
            cur.execute(f"SET search_path TO {self.schema}")
            cur.execute("""CREATE TABLE recognition_jobs (
                id serial PRIMARY KEY, camera_capture_id int, upload_id int,
                sample_rate_fps float DEFAULT 1, confidence_threshold float DEFAULT 0.35,
                status text DEFAULT 'pending', worker_id text, claim_token varchar(36),
                lease_until timestamptz, heartbeat_at timestamptz,
                attempts int DEFAULT 0, started_at timestamptz, finished_at timestamptz,
                created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now(), error text);
                CREATE TABLE recognition_results (
                recognition_job_id int UNIQUE, people_count int, detected_median float,
                detected_percentile_75 float, detected_max int, average_confidence float,
                count_stddev float, sampled_frames int, source_frames int, source_duration_ms int,
                representative_frame_ms int, absolute_error int, relative_error float,
                within_tolerance bool, annotated_bucket text, annotated_object_key text,
                media_expires_at timestamptz, inference_metadata jsonb)""")

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
            with conn, conn.cursor() as cur:
                cur.execute(f"SET search_path TO {self.schema}")
            return conn

        database._connection = connection
        self.databases.append(database)
        return database

    def execute(self, sql, params=()):
        with self.control.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall() if cur.description else None

    def result(self, job):
        return SimpleNamespace(
            people_count=3,
            detected_median=3.0,
            detected_percentile_75=3.0,
            detected_max=3,
            average_confidence=0.8,
            count_stddev=0.0,
            sampled_frames=1,
            source_frames=1,
            source_duration_ms=0,
            representative_frame_ms=0,
            absolute_error=None,
            relative_error=None,
            within_tolerance=None,
            annotated_bucket="clips",
            annotated_object_key=f"annotated/{job.claim_token}.jpg",
            inference_metadata={"model_sha256": "a" * 64},
        )

    def test_concurrent_claims_do_not_share_jobs(self):
        self.execute(
            "INSERT INTO recognition_jobs(upload_id) SELECT n FROM generate_series(1, 8) n"
        )
        databases = [self.database() for _ in range(8)]
        with ThreadPoolExecutor(max_workers=8) as executor:
            jobs = list(executor.map(lambda db: db.claim_job(), databases))
        self.assertEqual(len({job.id for job in jobs}), 8)
        self.assertEqual(len({job.claim_token for job in jobs}), 8)
        self.assertTrue(all(job.attempts == 1 for job in jobs))

    def test_same_worker_stale_token_cannot_heartbeat_fail_or_publish(self):
        self.execute("INSERT INTO recognition_jobs(upload_id) VALUES (1)")
        database = self.database()
        old = database.claim_job()
        self.execute(
            "UPDATE recognition_jobs SET lease_until = now() - interval '1 second'"
        )
        self.assertFalse(database.heartbeat(old.id, old.claim_token))
        self.assertFalse(
            database.complete_job(old.id, old.claim_token, self.result(old))
        )
        self.execute(
            "UPDATE recognition_jobs SET status = 'pending', claim_token = NULL"
        )
        new = database.claim_job()
        self.assertEqual(new.attempts, 2)
        self.assertNotEqual(old.claim_token, new.claim_token)
        self.assertFalse(database.heartbeat(old.id, old.claim_token))
        self.assertFalse(
            database.fail_job(old.id, old.claim_token, old.attempts, "stale")
        )
        self.assertFalse(
            database.complete_job(old.id, old.claim_token, self.result(old))
        )
        self.assertTrue(
            database.complete_job(new.id, new.claim_token, self.result(new))
        )
        self.assertEqual(
            self.execute("SELECT annotated_object_key FROM recognition_results"),
            [(self.result(new).annotated_object_key,)],
        )

    def test_unknown_commit_result_is_reconciled_without_duplicate(self):
        self.execute("INSERT INTO recognition_jobs(upload_id) VALUES (1)")
        database = self.database()
        job = database.claim_job()
        self.assertTrue(
            database.complete_job(job.id, job.claim_token, self.result(job))
        )
        database.close()
        self.assertTrue(
            database.complete_job(job.id, job.claim_token, self.result(job))
        )
        self.assertEqual(
            self.execute("SELECT count(*) FROM recognition_results"), [(1,)]
        )

    def lose_next_commit_ack(self, database):
        connection = database._connection
        injected = []

        class AmbiguousCommit:
            def __init__(self, conn):
                self.conn = conn

            def __enter__(self):
                self.conn.__enter__()
                return self

            def __exit__(self, *args):
                self.conn.__exit__(*args)
                if not injected and args[0] is None:
                    injected.append(True)
                    raise psycopg2.OperationalError(
                        "injected lost COMMIT acknowledgement"
                    )

            def cursor(self):
                return self.conn.cursor()

        database._connection = lambda: AmbiguousCommit(connection())

    def test_lost_claim_commit_ack_does_not_claim_a_second_job(self):
        self.execute("INSERT INTO recognition_jobs(upload_id) VALUES (1), (2)")
        database = self.database()
        self.lose_next_commit_ack(database)
        job = database.claim_job()
        self.assertEqual(job.attempts, 1)
        self.assertEqual(
            self.execute("SELECT status, attempts FROM recognition_jobs ORDER BY id"),
            [("processing", 1), ("pending", 0)],
        )

    def test_lost_completion_commit_ack_is_reconciled(self):
        self.execute("INSERT INTO recognition_jobs(upload_id) VALUES (1)")
        database = self.database()
        job = database.claim_job()
        self.lose_next_commit_ack(database)
        self.assertTrue(
            database.complete_job(job.id, job.claim_token, self.result(job))
        )
        self.assertEqual(
            self.execute("SELECT count(*) FROM recognition_results"), [(1,)]
        )

    def test_exhausted_job_not_claimed_and_permanent_failure_not_retried(self):
        self.execute(
            "INSERT INTO recognition_jobs(upload_id, attempts) VALUES (1, %s)",
            (settings.max_attempts,),
        )
        database = self.database()
        self.assertIsNone(database.claim_job())
        self.execute("INSERT INTO recognition_jobs(upload_id) VALUES (2)")
        job = database.claim_job()
        self.assertTrue(
            database.fail_job(
                job.id, job.claim_token, job.attempts, "invalid", permanent=True
            )
        )
        self.assertEqual(
            self.execute(
                "SELECT status FROM recognition_jobs WHERE id = %s", (job.id,)
            ),
            [("failed",)],
        )

    def test_result_insert_failure_rolls_back_completion(self):
        self.execute("INSERT INTO recognition_jobs(upload_id) VALUES (1)")
        database = self.database()
        job = database.claim_job()
        self.execute("ALTER TABLE recognition_results ADD CHECK (people_count < 0)")
        with self.assertRaises(psycopg2.IntegrityError):
            database.complete_job(job.id, job.claim_token, self.result(job))
        self.assertEqual(
            self.execute("SELECT status FROM recognition_jobs"), [("processing",)]
        )
