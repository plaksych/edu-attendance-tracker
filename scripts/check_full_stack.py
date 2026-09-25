"""Disposable Linux CI: HTTP upload, real worker, aggregation and DB/S3 recovery.

Uses generated empty-scene media, never classroom photos. This verifies wiring,
not detector accuracy. No services are started unless CI_DISPOSABLE=true and all
dependencies are loopback test endpoints. Production settings are never read.
"""

import argparse
from contextlib import closing, contextmanager
from datetime import datetime, time as day_time, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "disposable-pipeline-test-password"


def check_endpoints(dsn, endpoint):
    from psycopg2.extensions import parse_dsn

    parsed = parse_dsn(dsn)
    if (
        os.environ.get("CI_DISPOSABLE") != "true"
        or parsed.get("host") != "127.0.0.1"
        or parsed.get("dbname") != "attendance_test"
        or urlsplit("http://" + endpoint).hostname != "127.0.0.1"
    ):
        raise ValueError("Explicit disposable CI database and loopback S3 required")
    return parsed


@contextmanager
def process(command, env, cwd, log, pass_fds=()):
    with log.open("wb") as output:
        child = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            pass_fds=pass_fds,
        )
        try:
            yield child
        finally:
            try:
                os.killpg(child.pid, signal.SIGTERM)
                child.wait(timeout=15)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                pass
            finally:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()


@contextmanager
def api(env, log):
    import httpx

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        port = listener.getsockname()[1]
        with (
            process(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--fd",
                    str(listener.fileno()),
                    "--no-proxy-headers",
                ],
                env,
                ROOT / "backend",
                log,
                (listener.fileno(),),
            ) as child,
            httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=20) as client,
        ):
            for _ in range(100):
                if child.poll() is not None:
                    raise AssertionError("API exited; inspect API log")
                try:
                    if client.get("/health", timeout=0.5).status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.1)
            else:
                raise AssertionError("API startup timed out")
            yield client


def login(client):
    response = client.post(
        "/api/v1/auth/login", json={"username": "operator", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]


def wait_result(client, identity, worker, digest):
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        assert worker.poll() is None, "Worker exited; inspect worker log"
        response = client.get(f"/api/v1/recognition/uploads/{identity}")
        assert response.status_code == 200, response.text
        job = response.json()["job"]
        if job["status"] == "completed":
            result = job["result"]
            assert result["people_count"] == 0, "Empty-scene false detection"
            assert result["sampled_frames"] >= 1
            assert result["inference_metadata"]["model_sha256"] == digest
            return job
        assert job["status"] not in {"failed", "cancelled", "retry_wait"}, job
        time.sleep(0.25)
    raise AssertionError("Recognition timed out")


def media_checks(client, identity, original):
    import httpx
    from PIL import Image

    response = client.get(f"/api/v1/recognition/uploads/{identity}/media")
    assert response.status_code == 200, response.text
    links = response.json()
    assert links["source_url"] and links["annotated_url"], links
    with httpx.Client(timeout=20) as media:
        source = media.get(links["source_url"])
        assert source.status_code == 200 and source.content == original
        annotated = media.get(links["annotated_url"])
        assert annotated.status_code == 200
        with Image.open(io.BytesIO(annotated.content)) as picture:
            picture.verify()
        anonymous = media.get(links["source_url"].split("?", 1)[0])
        assert anonymous.status_code == 403
    return hashlib.sha256(annotated.content).hexdigest()


def seed(dsn):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as DbSession
    from app.core.security import password_hasher
    from app.models import (
        Classroom,
        Discipline,
        Group,
        Measurement,
        Schedule,
        Session,
        Teacher,
        User,
    )

    engine = create_engine(dsn)
    try:
        with DbSession(engine) as db:
            now = datetime.now(timezone.utc)
            lesson = Session(
                schedule=Schedule(
                    group=Group(name="Pipeline fixture", students_count=20),
                    discipline=Discipline(name="Integration test"),
                    teacher=Teacher(full_name="Test teacher"),
                    classroom=Classroom(number="CI"),
                    weekday=now.isoweekday(),
                    starts_at=day_time(0),
                    ends_at=day_time(23, 59),
                ),
                date=now.date(),
                expected_count_snapshot=20,
                status="in_progress",
                measurements=[
                    Measurement(type=kind, planned_at=now)
                    for kind in ("after_start", "before_end")
                ],
            )
            db.add_all(
                [
                    lesson,
                    User(
                        username="operator",
                        role="operator",
                        password_hash=password_hasher.hash(PASSWORD),
                    ),
                ]
            )
            db.commit()
            return (
                lesson.id,
                [m.id for m in lesson.measurements],
                now.date().isoformat(),
            )
    finally:
        engine.dispose()


def aggregate(dsn, lesson_id):
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session as DbSession
    from app.models import AttendanceRecord, Session
    from app.services.aggregation import (
        aggregate_ready_measurements,
        finalize_finished_sessions,
    )

    engine = create_engine(dsn)
    try:
        with DbSession(engine) as db:
            assert aggregate_ready_measurements(db) == 2
            lesson = db.get(Session, lesson_id)
            assert all(
                m.source_results and m.final_people_count == 0
                for m in lesson.measurements
            )
            lesson.status = "finished"
            lesson.finished_at = datetime.now(timezone.utc)
            db.commit()
            assert finalize_finished_sessions(db) == 1
            record = db.scalar(
                select(AttendanceRecord).where(AttendanceRecord.session_id == lesson_id)
            )
            assert record.expected_count == 20 and record.detected_average == 0
            assert (
                record.attendance_rate == 0
                and record.calculation_status.value == "complete"
            )
    finally:
        engine.dispose()


def recover(parsed, client, source_db, source_bucket, target_db, target_bucket, folder):
    import psycopg2
    from data import (
        backup,
        restore,
        provision_marker,
        quiescent,
        run,
        restic_environment,
    )

    passfile = folder / "pgpass"
    passfile.write_text(
        ":".join(
            [parsed["host"], parsed["port"], "*", parsed["user"], parsed["password"]]
        )
        + "\n"
    )
    passfile.chmod(0o600)
    password = folder / "restic-password"
    password.write_text(uuid4().hex)
    password.chmod(0o600)
    repository = source_bucket + "-backup"
    client.make_bucket(repository)
    common = {
        "PGHOST": parsed["host"],
        "PGPORT": parsed["port"],
        "PGUSER": parsed["user"],
        "PGPASSFILE": str(passfile),
        "PGSSLMODE": "disable",
        "RESTIC_REPOSITORY": f"s3:http://{os.environ['CI_S3_ENDPOINT']}/{repository}",
        "RESTIC_PASSWORD_FILE": str(password),
        "AWS_ACCESS_KEY_ID": "ci-storage-user",
        "AWS_SECRET_ACCESS_KEY": "ci-disposable-storage-secret",
    }
    source = {
        **common,
        "PGDATABASE": source_db,
        "S3_BUCKET": source_bucket,
        "OPS_NAMESPACE": source_bucket,
        "OPS_MODE": "demo",
        "OPS_INSTANCE_ID": str(uuid4()),
    }
    target = {
        **common,
        "PGDATABASE": target_db,
        "S3_BUCKET": target_bucket,
        "OPS_NAMESPACE": target_bucket,
        "OPS_MODE": "restore",
        "OPS_INSTANCE_ID": str(uuid4()),
    }
    run(["restic", "init"], restic_environment(source))
    config = folder / "public-config"
    config.write_text("TIMEZONE=UTC\n")
    config.chmod(0o600)
    source_folder, target_folder = folder / "backup", folder / "restore"
    source_folder.mkdir()
    target_folder.mkdir()
    with closing(psycopg2.connect(**{**parsed, "dbname": source_db})) as connection:
        connection.autocommit = True
        quiescent(connection)
        saved = backup(connection, client, source, source_folder, config)
    with closing(psycopg2.connect(**{**parsed, "dbname": target_db})) as connection:
        connection.autocommit = True
        provision_marker(connection, target)
        quiescent(connection)
        restored = restore(connection, client, target, target_folder, saved["snapshot"])
    return {"backup": saved, "restore": restored, "repository_bucket": repository}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--recognition-python", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    args = parser.parse_args()
    dsn, endpoint = os.environ["QUEUE_TEST_DSN"], os.environ["CI_S3_ENDPOINT"]
    parsed = check_endpoints(dsn, endpoint)
    if sys.platform != "linux":
        raise ValueError("Full-stack verification runs on disposable Linux CI only")
    import psycopg2
    from psycopg2 import sql
    from minio import Minio
    from PIL import Image

    manifest = json.loads((ROOT / "recognition/model-manifest.json").read_text())
    model = args.model.absolute()
    assert hashlib.sha256(model.read_bytes()).hexdigest() == manifest["sha256"]
    output = args.output.absolute()
    output.mkdir(parents=True, exist_ok=False)
    evidence = {
        "status": "failed",
        "scope": "synthetic empty-scene functional test; not classroom accuracy or production TLS/IAM",
        "revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "checks": [],
    }
    token = uuid4().hex[:12]
    source_bucket, target_bucket = (
        "attendance-demo-" + token,
        "attendance-restore-" + token,
    )
    databases = [name.replace("-", "_") for name in (source_bucket, target_bucket)]
    buckets, created_databases = [], []
    storage = Minio(
        endpoint,
        access_key="ci-storage-user",
        secret_key="ci-disposable-storage-secret",
        secure=False,
    )
    control = psycopg2.connect(dsn)
    control.autocommit = True
    try:
        for database in databases:
            with control.cursor() as cursor:
                cursor.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database))
                )
            created_databases.append(database)
        for bucket in (source_bucket, target_bucket):
            storage.make_bucket(bucket)
            buckets.append(bucket)
        # SQLAlchemy and worker both accept URL form, not libpq keyword DSNs.
        from sqlalchemy.engine import URL

        def database_url(name):
            return URL.create(
                "postgresql",
                username=parsed["user"],
                password=parsed["password"],
                host=parsed["host"],
                port=int(parsed["port"]),
                database=name,
            ).render_as_string(hide_password=False)

        source_dsn = database_url(databases[0])
        env = {
            key: os.environ[key]
            for key in ("PATH", "HOME", "LANG")
            if key in os.environ
        }
        env.update(
            {
                "ENVIRONMENT": "test",
                "DATABASE_URL": source_dsn,
                "SESSION_SECURE": "false",
                "MINIO_ENDPOINT": endpoint,
                "MINIO_PUBLIC_ENDPOINT": endpoint,
                "MINIO_ACCESS_KEY": "ci-storage-user",
                "MINIO_SECRET_KEY": "ci-disposable-storage-secret",
                "MINIO_BUCKET": source_bucket,
                "MINIO_SECURE": "false",
                "MINIO_PUBLIC_SECURE": "false",
                "SCHEDULER_ENABLED": "false",
                "MODEL_PATH": str(model),
                "MODEL_SHA256": manifest["sha256"],
                "POLL_INTERVAL_SECONDS": "1",
                "HEARTBEAT_INTERVAL_SECONDS": "1",
                "MAX_SAMPLED_FRAMES": "3",
                "INFERENCE_IMAGE_SIZE": "960",
                "MAX_ATTEMPTS": "1",
                "JOB_TIMEOUT_SECONDS": "120",
                "CPU_LIMIT_SECONDS": "90",
                "MEMORY_LIMIT_MB": "2304",
                "OMP_NUM_THREADS": "1",
                "OPENBLAS_NUM_THREADS": "1",
                "MKL_NUM_THREADS": "1",
            }
        )
        os.environ.update(env)
        sys.path.insert(0, str(ROOT / "backend"))
        sys.path.insert(0, str(ROOT / "scripts/ops"))
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT / "backend",
            env=env,
            check=True,
        )
        lesson_id, measurements, date = seed(source_dsn)
        image = io.BytesIO()
        Image.new("RGB", (96, 64), "black").save(image, "PNG")
        video = output / "empty-scene.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=96x64:d=1:r=2",
                "-threads",
                "1",
                "-c:v",
                "mpeg4",
                str(video),
            ],
            check=True,
            timeout=20,
        )
        originals = [
            ("empty.png", "image/png", image.getvalue()),
            ("empty.mp4", "video/mp4", video.read_bytes()),
        ]
        identities, digests, job_ids = [], [], []
        with (
            api(env, output / "api.log") as client,
            process(
                [str(args.recognition_python.absolute()), "-m", "app.main"],
                env,
                ROOT / "recognition",
                output / "worker.log",
            ) as worker,
        ):
            login(client)
            for measurement, (name, mime, content) in zip(
                measurements, originals, strict=True
            ):
                options = {
                    "session_id": str(lesson_id),
                    "measurement_id": str(measurement),
                    "reference_people_count": "0",
                }
                headers = {"Idempotency-Key": uuid4().hex}
                response = client.post(
                    "/api/v1/recognition/uploads",
                    files={"file": (name, content, mime)},
                    data=options,
                    headers=headers,
                )
                assert response.status_code == 202, response.text
                identity = response.json()["id"]
                duplicate = client.post(
                    "/api/v1/recognition/uploads",
                    files={"file": (name, content, mime)},
                    data=options,
                    headers=headers,
                )
                assert (
                    duplicate.status_code == 202 and duplicate.json()["id"] == identity
                )
                job = wait_result(client, identity, worker, manifest["sha256"])
                evidence["checks"].append(
                    {
                        "media_type": mime,
                        "upload_id": identity,
                        "job_id": job["id"],
                        "result": job["result"],
                    }
                )
                identities.append(identity)
                job_ids.append(job["id"])
                digests.append(media_checks(client, identity, content))
            aggregate(source_dsn, lesson_id)
            csv_path = f"/api/v1/stats/export.csv?date_from={date}&date_to={date}"
            report = client.get(csv_path)
            assert report.status_code == 200 and "Pipeline fixture" in report.text
            assert len(report.text.strip().splitlines()) == 2
            (output / "attendance.csv").write_text(report.text)
            retry_path = f"/api/v1/recognition/uploads/{identities[0]}/retry"
            retry_headers = {"Idempotency-Key": uuid4().hex}
            retry = client.post(retry_path, headers=retry_headers)
            assert retry.status_code == 202, retry.text
            retried = wait_result(client, identities[0], worker, manifest["sha256"])
            assert retried["id"] != job_ids[0]
            replay = client.post(retry_path, headers=retry_headers)
            assert (
                replay.status_code == 202
                and replay.json()["job"]["id"] == retried["id"]
            )
            history = client.get(
                f"/api/v1/recognition/uploads/{identities[0]}/history"
            ).json()
            assert len(history["jobs"]) == 2
            assert all(job["status"] == "completed" for job in history["jobs"])
            from app.core.database import SessionLocal
            from app.models import Measurement
            from app.services.aggregation import aggregate_ready_measurements

            with SessionLocal() as db:
                assert aggregate_ready_measurements(db) == 0
                for measurement, job_id in zip(measurements, job_ids, strict=True):
                    saved = db.get(Measurement, measurement)
                    assert [
                        source.recognition_job_id for source in saved.source_results
                    ] == [job_id]
            assert client.get(csv_path).text == report.text
            digests[0] = media_checks(client, identities[0], originals[0][2])
            evidence["checks"].append(
                "Retry creates a new result; replay creates no third attempt; finalized measurement sources and CSV remain unchanged"
            )
        evidence["checks"].append(
            "HTTP upload, replay, real image/video inference, signed media, private S3, aggregation and CSV passed"
        )
        from app.core.database import engine

        engine.dispose()
        buckets.append(source_bucket + "-backup")
        with tempfile.TemporaryDirectory(prefix="pipeline-recovery-") as directory:
            evidence["recovery"] = recover(
                parsed,
                storage,
                databases[0],
                source_bucket,
                databases[1],
                target_bucket,
                Path(directory),
            )
        restored_env = {
            **env,
            "DATABASE_URL": database_url(databases[1]),
            "MINIO_BUCKET": target_bucket,
        }
        with api(restored_env, output / "restored-api.log") as client:
            login(client)
            assert client.get(csv_path).text == report.text
            for identity, (_, _, content), digest in zip(
                identities, originals, digests, strict=True
            ):
                assert media_checks(client, identity, content) == digest
        evidence["checks"].append(
            "Restored API returns identical CSV, source bytes and annotated bytes in a separate namespace"
        )
        evidence["status"] = "passed"
    finally:
        (output / "evidence.json").write_text(
            json.dumps(evidence, indent=2, default=str)
        )
        for bucket in reversed(buckets):
            if storage.bucket_exists(bucket):
                for item in storage.list_objects(bucket, recursive=True):
                    storage.remove_object(bucket, item.object_name)
                storage.remove_bucket(bucket)
        for database in reversed(created_databases):
            with control.cursor() as cursor:
                cursor.execute(
                    sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                        sql.Identifier(database)
                    )
                )
        control.close()
    print(
        "PASS: real upload-to-report pipeline and joint DB/S3 restore; see evidence.json"
    )


if __name__ == "__main__":
    main()
