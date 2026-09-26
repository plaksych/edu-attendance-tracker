"""Non-destructive legacy 0009 -> 0010 backfill and schema consistency."""

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
def test_0010_backfills_available_links_without_fabricating_old_result_sources():
    dsn = os.environ["BACKEND_TEST_DSN"]
    root = Path(__file__).resolve().parents[1]
    schema = "source_migration_" + uuid4().hex
    engine = create_engine(dsn)
    with engine.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
    env = {**os.environ, "DATABASE_URL": dsn, "PGOPTIONS": f"-csearch_path={schema}"}

    def alembic(*args):
        command = subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
        )
        assert command.returncode == 0, command.stdout + command.stderr

    try:
        alembic("upgrade", "0009")
        with engine.begin() as connection:
            connection.execute(text(f"SET LOCAL search_path TO {schema}"))
            connection.execute(
                text("""
                INSERT INTO groups(id,name,course,students_count) VALUES (1,'legacy',1,20);
                INSERT INTO disciplines(id,name) VALUES (1,'Legacy');
                INSERT INTO classrooms(id,number) VALUES (1,'legacy room');
                INSERT INTO schedule(id,group_id,discipline_id,classroom_id,weekday,starts_at,ends_at,week_type)
                    VALUES (1,1,1,1,1,'09:00','10:00','every');
                INSERT INTO sessions(id,schedule_id,date,status)
                    VALUES (1,1,'2026-02-09','finished');
                INSERT INTO measurements(id,session_id,type,planned_at,status,final_people_count)
                    VALUES (1,1,'after_start',now(),'completed',11),
                           (2,1,'before_end',now(),'scheduled',NULL);
                INSERT INTO cameras(id,name,rtsp_url) VALUES
                    (1,'linked','encrypted:test'), (2,'missing link','encrypted:test');
                INSERT INTO classroom_cameras(classroom_id,camera_id,role,priority,zone_code)
                    VALUES (1,1,'backup',3,'legacy-zone');
                INSERT INTO camera_captures(id,measurement_id,camera_id,planned_at,status)
                    VALUES (1,1,1,now(),'completed'), (2,2,2,now(),'pending');
                INSERT INTO recognition_jobs(id,camera_capture_id,status) VALUES (1,1,'completed');
                INSERT INTO recognition_results(id,recognition_job_id,people_count,detected_median,
                    detected_percentile_75,detected_max,average_confidence,sampled_frames,
                    representative_frame_ms,annotated_bucket,annotated_object_key,
                    count_stddev,source_frames,source_duration_ms)
                    VALUES (1,1,11,11,11,11,0.9,1,0,'private','legacy.jpg',0,1,0);
            """)
            )
        alembic("upgrade", "0010")
        alembic("check")
        with engine.connect() as connection:
            connection.execute(text(f"SET search_path TO {schema}"))
            assert connection.execute(
                text("""SELECT role_snapshot, priority_snapshot,
                zone_code_snapshot, snapshot_origin FROM camera_captures ORDER BY id""")
            ).all() == [
                ("backup", 3, "legacy-zone", "legacy_current_link"),
                (None, None, None, "legacy_unknown"),
            ]
            assert connection.execute(
                text("""SELECT status::text, final_people_count,
                source_reference_status FROM measurements ORDER BY id""")
            ).all() == [
                ("completed", 11, "legacy_unknown"),
                ("scheduled", None, None),
            ]
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM measurement_result_sources")
                )
                == 0
            )
            assert (
                connection.scalar(
                    text("SELECT people_count FROM recognition_results WHERE id=1")
                )
                == 11
            )
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "0010"
            )
    finally:
        with engine.begin() as connection:
            connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        engine.dispose()
