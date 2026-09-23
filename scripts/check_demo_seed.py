"""Exercise demo seeding in a disposable native database, including marker guards."""

from datetime import date
import os
from pathlib import Path
import subprocess
import sys
import uuid
from urllib.parse import quote

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import parse_dsn

sys.path.insert(0, str(Path(__file__).parent / "ops"))
from data import counts, provision_marker  # noqa: E402
from seed import seed  # noqa: E402
from tasks import ROOT, python  # noqa: E402


def refused(connection, env):
    before = counts(connection)
    connection.rollback()
    try:
        seed(connection, env, date(2026, 9, 23))
    except ValueError:
        pass
    else:
        raise AssertionError("Unsafe seed accepted")
    assert counts(connection) == before
    connection.rollback()


def main():
    dsn = os.environ.get("TEST_DATABASE_URL") or os.environ.get("QUEUE_TEST_DSN")
    if not dsn:
        raise SystemExit("Explicit TEST_DATABASE_URL required")
    params = parse_dsn(dsn.replace("postgresql+psycopg2://", "postgresql://", 1))
    assert params.get("host") in {"localhost", "127.0.0.1"}
    assert params.get("dbname") == "attendance_test"
    namespace = "attendance-demo-seedtest-" + uuid.uuid4().hex[:10]
    database = namespace.replace("-", "_")
    env = {
        "OPS_MODE": "demo",
        "OPS_NAMESPACE": namespace,
        "PGDATABASE": database,
        "S3_BUCKET": namespace,
        "OPS_INSTANCE_ID": str(uuid.uuid4()),
    }
    control = psycopg2.connect(**params)
    control.autocommit = True
    connection = None
    try:
        with control.cursor() as cursor:
            cursor.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database))
            )
        connection = psycopg2.connect(**{**params, "dbname": database})
        provision_marker(connection, env)
        connection.commit()
        user = quote(params["user"], safe="")
        password = quote(params.get("password", ""), safe="")
        url = f"postgresql://{user}:{password}@{params['host']}:{params.get('port', '5432')}/{database}"
        result = subprocess.run(
            [python("backend"), "-m", "alembic", "upgrade", "head"],
            cwd=ROOT / "backend",
            env={**os.environ, "ENVIRONMENT": "test", "DATABASE_URL": url},
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            "Isolated demo migration failed (output withheld)"
        )
        refused(connection, {**env, "OPS_MODE": "production"})
        with connection.cursor() as cursor:
            cursor.execute("UPDATE ops_control.identity SET mode='production'")
        connection.commit()
        refused(connection, env)
        with connection.cursor() as cursor:
            cursor.execute("UPDATE ops_control.identity SET mode='demo'")
        connection.commit()
        refused(connection, {**env, "OPS_INSTANCE_ID": str(uuid.uuid4())})
        blocker = psycopg2.connect(**{**params, "dbname": database})
        try:
            with blocker.cursor() as cursor:
                cursor.execute("LOCK TABLE groups IN ACCESS SHARE MODE")
            try:
                seed(connection, env, date(2026, 9, 23))
            except psycopg2.errors.LockNotAvailable:
                pass
            else:
                raise AssertionError("Seed did not respect concurrent table lock")
        finally:
            blocker.close()
        assert all(
            value == 0
            for table, value in counts(connection).items()
            if table != "alembic_version"
        )
        connection.rollback()
        evidence = seed(connection, env, date(2026, 9, 23))
        assert evidence["weekday"] == 3
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT weekday, starts_at::text, ends_at::text, week_type::text "
                "FROM schedule ORDER BY starts_at"
            )
            assert cursor.fetchall() == [
                (3, "09:00:00", "10:30:00", "every"),
                (3, "10:45:00", "12:15:00", "every"),
            ]
        actual = counts(connection)
        for table, expected in {
            "groups": 2,
            "teachers": 1,
            "disciplines": 2,
            "classrooms": 1,
            "schedule": 2,
        }.items():
            assert actual[table] == expected
        assert all(
            value == 0
            for table, value in actual.items()
            if table
            not in {
                "alembic_version",
                "groups",
                "teachers",
                "disciplines",
                "classrooms",
                "schedule",
            }
        )
        connection.rollback()
        refused(connection, env)
        print(
            "PASS: native demo seed; exact synthetic catalogs, no users/results; production/marker/nonempty/lock guards"
        )
    finally:
        if connection:
            connection.close()
        with control.cursor() as cursor:
            cursor.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                    sql.Identifier(database)
                )
            )
        control.close()


if __name__ == "__main__":
    main()
