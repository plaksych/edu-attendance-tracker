"""Upgrade a populated former schema, preserving legacy and current history."""

import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text


@pytest.mark.skipif(
    not os.environ.get("BACKEND_TEST_DSN"), reason="BACKEND_TEST_DSN required"
)
def test_upgrade_populated_0005_and_schema_drift():
    dsn = os.environ["BACKEND_TEST_DSN"]
    root = Path(__file__).resolve().parents[1]
    schema = "migration_test_" + uuid4().hex
    engine = create_engine(dsn)
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    env = {**os.environ, "DATABASE_URL": dsn, "PGOPTIONS": f"-csearch_path={schema}"}

    def alembic(*args):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    try:
        alembic("upgrade", "0005")
        with engine.begin() as conn:
            conn.execute(text(f"SET LOCAL search_path TO {schema}"))
            conn.execute(
                text("""INSERT INTO groups(id,name,course,students_count) VALUES (1,'legacy',1,28);
                INSERT INTO disciplines(id,name) VALUES (1,'Legacy discipline');
                INSERT INTO schedule(id,group_id,discipline_id,weekday,starts_at,ends_at,week_type)
                    VALUES (1,1,1,1,'09:00','10:00','every');
                INSERT INTO sessions(id,schedule_id,date,status) VALUES (1,1,'2026-02-09','finished');
                INSERT INTO detection_snapshots(session_id,captured_at,person_count) VALUES (1,now(),17);
                INSERT INTO attendance_records(session_id,expected_count,detected_average,calculation_status)
                    VALUES (1,24,17,'complete');""")
            )
        alembic("upgrade", "head")
        alembic("check")
        with engine.connect() as conn:
            conn.execute(text(f"SET search_path TO {schema}"))
            assert (
                conn.scalar(
                    text("SELECT expected_count_snapshot FROM sessions WHERE id=1")
                )
                == 24
            )
            assert (
                conn.scalar(text("SELECT person_count FROM detection_snapshots")) == 17
            )
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        engine.dispose()
