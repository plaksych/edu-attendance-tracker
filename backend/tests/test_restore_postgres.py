"""PostgreSQL-only restore drill. This does not certify object-store recovery."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


@pytest.mark.skipif(
    not os.environ.get("RESTORE_TEST_DSN"), reason="Explicit RESTORE_TEST_DSN required"
)
def test_database_backup_restore(tmp_path):
    assert shutil.which("pg_dump") and shutil.which("pg_restore")
    url = make_url(os.environ["RESTORE_TEST_DSN"])
    assert url.host in {"localhost", "127.0.0.1"}, (
        "Drill is restricted to isolated localhost PostgreSQL"
    )
    control = create_engine(url, isolation_level="AUTOCOMMIT")
    names = ["restore_source_" + uuid4().hex, "restore_target_" + uuid4().hex]
    root = Path(__file__).resolve().parents[1]

    def run(command, **kwargs):
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=60, **kwargs
        )
        assert result.returncode == 0, result.stderr

    try:
        with control.connect() as conn:
            for name in names:
                conn.execute(text(f'CREATE DATABASE "{name}"'))
        source = url.set(database=names[0])
        target = url.set(database=names[1])
        env = {
            **os.environ,
            "DATABASE_URL": source.render_as_string(hide_password=False),
        }
        run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=root, env=env)
        engine = create_engine(source)
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO groups(name,course,students_count) VALUES ('RESTORE-CHECK',1,23)"
                )
            )
        engine.dispose()
        path = tmp_path / "database.dump"
        run(
            [
                "pg_dump",
                "--format=custom",
                "--no-owner",
                "--file",
                str(path),
                source.set(drivername="postgresql").render_as_string(
                    hide_password=False
                ),
            ]
        )
        run(
            [
                "pg_restore",
                "--exit-on-error",
                "--no-owner",
                "--dbname",
                target.set(drivername="postgresql").render_as_string(
                    hide_password=False
                ),
                str(path),
            ]
        )
        engine = create_engine(target)
        with engine.connect() as conn:
            assert (
                conn.scalar(
                    text("SELECT students_count FROM groups WHERE name='RESTORE-CHECK'")
                )
                == 23
            )
            assert (
                conn.scalar(text("SELECT version_num FROM alembic_version")) == "0010"
            )
        engine.dispose()
    finally:
        with control.connect() as conn:
            for name in names:
                conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        control.dispose()
