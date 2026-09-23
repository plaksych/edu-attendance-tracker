"""Real PostgreSQL migration and private S3 checks on an explicitly disposable CI DB."""

from datetime import timedelta
import argparse
import io
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--existing-db",
        action="store_true",
        help="Read/check an existing test schema; never migrate or seed it",
    )
    parser.add_argument(
        "--database-only", action="store_true", help="Report S3 as not_run, not passed"
    )
    args = parser.parse_args()
    import psycopg2
    from psycopg2.extensions import parse_dsn

    dsn = os.environ.get("TEST_DATABASE_URL") or os.environ.get("QUEUE_TEST_DSN")
    if not dsn:
        raise SystemExit("TEST_DATABASE_URL or QUEUE_TEST_DSN required")
    dsn = dsn.replace("postgresql+psycopg2://", "postgresql://", 1)
    parsed = parse_dsn(dsn)
    if parsed.get("dbname") != "attendance_test" or parsed.get("host") != "127.0.0.1":
        raise SystemExit("Integration checks require loopback attendance_test DB")
    if not args.existing_db and os.environ.get("CI_DISPOSABLE") != "true":
        raise SystemExit(
            "Migration/seed checks require CI_DISPOSABLE=true; use --existing-db for read-only checks"
        )
    root = Path(__file__).resolve().parents[1]
    connection = psycopg2.connect(dsn)
    connection.autocommit = True
    environment = {
        **os.environ,
        "ENVIRONMENT": "test",
        "DATABASE_URL": dsn,
        "SCHEDULER_ENABLED": "false",
    }

    def migrate(revision):
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", revision],
            cwd=root / "backend",
            env=environment,
            check=True,
        )

    if args.existing_db:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        config = Config(str(root / "backend/alembic.ini"))
        config.set_main_option("script_location", str(root / "backend/alembic"))
        heads = set(ScriptDirectory.from_config(config).get_heads())
        with connection.cursor() as cursor:
            cursor.execute("SELECT version_num FROM alembic_version")
            if {row[0] for row in cursor.fetchall()} != heads:
                raise SystemExit(
                    "Existing test DB is not at the repository migration head"
                )
        subprocess.run(
            [sys.executable, "-m", "alembic", "check"],
            cwd=root / "backend",
            env=environment,
            check=True,
        )
        print(
            "PASS: native existing test DB matches migration head and Alembic metadata; no migrations executed"
        )
    else:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'")
            if cursor.fetchone()[0]:
                raise SystemExit("Migration smoke requires an empty test database")
        migrate("0005")
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO groups(name, course, students_count) VALUES ('ci-migration-sentinel', 1, 17)"
            )
        migrate("head")
        migrate("head")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT students_count FROM groups WHERE name='ci-migration-sentinel'"
            )
            assert cursor.fetchone() == (17,)
        print("PASS: old-schema data preserved and upgrade head is idempotent")
    connection.close()
    if args.database_only:
        print(
            "NOT_RUN: S3 private access, signed Range and expiry (database-only requested)"
        )
        return
    from minio import Minio

    endpoint = os.environ["CI_S3_ENDPOINT"]
    client = Minio(
        endpoint,
        access_key="ci-storage-user",
        secret_key="ci-disposable-storage-secret",
        secure=False,
    )
    for attempt in range(30):
        try:
            client.list_buckets()
            break
        except Exception:
            if attempt == 29:
                raise
            time.sleep(1)
    bucket = "ci-check-" + uuid.uuid4().hex
    client.make_bucket(bucket)
    try:
        client.put_object(bucket, "fixture.bin", io.BytesIO(b"0123456789"), 10)
        try:
            urlopen(f"http://{endpoint}/{bucket}/fixture.bin", timeout=5)
        except HTTPError as exc:
            assert exc.code == 403
        else:
            raise AssertionError("Anonymous storage access accepted")
        signed = client.presigned_get_object(
            bucket, "fixture.bin", expires=timedelta(seconds=1)
        )
        with urlopen(
            Request(signed, headers={"Range": "bytes=2-4"}), timeout=5
        ) as response:
            assert response.status == 206 and response.read() == b"234"
        time.sleep(2)
        try:
            urlopen(signed, timeout=5)
        except HTTPError as exc:
            assert exc.code == 403
        else:
            raise AssertionError("Expired signed URL accepted")
    finally:
        client.remove_object(bucket, "fixture.bin")
        client.remove_bucket(bucket)
    print("PASS: private S3, signed Range and expiry")


if __name__ == "__main__":
    main()
