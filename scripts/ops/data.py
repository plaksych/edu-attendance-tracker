"""Guarded host-side backup/restore/reset using PostgreSQL, MinIO and restic.

Requires a private ops env file, reachable private endpoints, stopped writers and
an administrator-provisioned DB identity. Never invokes Docker or starts services.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import uuid

from common import IMAGE_KEYS, read_env, require
from manage import confirm


def validate_target(env, action, identity=None, actual_database=None):
    mode = env.get("OPS_MODE")
    prefix = {"production": "prod", "demo": "demo", "restore": "restore"}.get(mode)
    namespace = env.get("OPS_NAMESPACE", "")
    require(
        prefix and re.fullmatch(f"attendance-{prefix}-[a-z0-9-]+", namespace),
        "Invalid target namespace",
    )
    require(
        env.get("PGDATABASE") == namespace.replace("-", "_"),
        "Database/namespace mismatch",
    )
    require(env.get("S3_BUCKET") == namespace, "Bucket/namespace mismatch")
    require(
        str(uuid.UUID(env.get("OPS_INSTANCE_ID", ""))) == env["OPS_INSTANCE_ID"],
        "Invalid instance UUID",
    )
    if action in {"reset", "seed"}:
        require(mode == "demo", "Reset/seed is restricted to marked demo databases")
    if action == "restore":
        require(mode == "restore", "Restore requires a separate restore namespace")
    if actual_database is not None:
        require(
            actual_database == env["PGDATABASE"],
            "Connected database differs from target",
        )
        require(
            identity == (mode, namespace, env["OPS_INSTANCE_ID"]),
            "Database identity mismatch",
        )


def pg_environment(env):
    result = {
        key: os.environ[key]
        for key in ("PATH", "HOME", "SYSTEMROOT")
        if key in os.environ
    }
    for key in (
        "PGHOST",
        "PGPORT",
        "PGDATABASE",
        "PGUSER",
        "PGPASSFILE",
        "PGSSLMODE",
        "PGSSLROOTCERT",
    ):
        if env.get(key):
            result[key] = env[key]
    result["PGCONNECT_TIMEOUT"] = "5"
    require(
        env.get("PGSSLMODE") in {"verify-full", "disable"}, "Set explicit PGSSLMODE"
    )
    require(
        env.get("PGSSLMODE") != "disable"
        or env.get("PGHOST") in {"127.0.0.1", "localhost"},
        "Non-loopback database connections require TLS verification",
    )
    password_file = Path(env.get("PGPASSFILE", ""))
    require(
        password_file.is_file() and password_file.stat().st_mode & 0o077 == 0,
        "Private PGPASSFILE required",
    )
    return result


def run(command, env):
    result = subprocess.run(
        command, env=env, capture_output=True, text=True, check=False
    )
    require(
        result.returncode == 0,
        f"{command[0]} failed; no success evidence written (output withheld)",
    )
    return result.stdout


def restic_environment(env):
    require(
        env.get("RESTIC_REPOSITORY", "").startswith(
            ("s3:", "sftp:", "rest:https://", "azure:", "gs:")
        ),
        "An encrypted off-host restic repository is required",
    )
    require(
        Path(env.get("RESTIC_PASSWORD_FILE", "")).is_file(),
        "RESTIC_PASSWORD_FILE required",
    )
    require(
        Path(env["RESTIC_PASSWORD_FILE"]).stat().st_mode & 0o077 == 0,
        "Restic password file must be private",
    )
    keys = (
        "RESTIC_REPOSITORY",
        "RESTIC_PASSWORD_FILE",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AZURE_ACCOUNT_NAME",
        "AZURE_ACCOUNT_KEY",
        "GOOGLE_APPLICATION_CREDENTIALS",
    )
    return {
        **{
            k: os.environ[k]
            for k in ("PATH", "HOME", "SSH_AUTH_SOCK")
            if k in os.environ
        },
        **{k: env[k] for k in keys if k in env},
    }


def connect(env):
    import psycopg2
    from minio import Minio

    pg_environment(env)
    connection = psycopg2.connect(
        host=env["PGHOST"],
        port=env.get("PGPORT", "5432"),
        dbname=env["PGDATABASE"],
        user=env["PGUSER"],
        passfile=env["PGPASSFILE"],
        sslmode=env["PGSSLMODE"],
        sslrootcert=env.get("PGSSLROOTCERT"),
        connect_timeout=5,
    )
    connection.autocommit = True
    secure = env.get("S3_SECURE") == "true"
    require(
        secure or env["S3_ENDPOINT"].split(":")[0] in {"localhost", "127.0.0.1"},
        "Private S3 requires TLS or a loopback tunnel",
    )
    client = Minio(
        env["S3_ENDPOINT"],
        access_key=env["S3_ACCESS_KEY"],
        secret_key=env["S3_SECRET_KEY"],
        secure=secure,
    )
    require(
        client.bucket_exists(env["S3_BUCKET"]), "Bucket must be provisioned separately"
    )
    return connection, client


def identity(connection):
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        database = cursor.fetchone()[0]
        cursor.execute(
            "SELECT mode, namespace, instance_id::text FROM ops_control.identity WHERE singleton"
        )
        row = cursor.fetchone()
    return database, row


def quiescent(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
            "AND pid <> pg_backend_pid() AND backend_type = 'client backend'"
        )
        require(
            cursor.fetchone()[0] == 0,
            "Stop API, scheduler, maintenance, workers and all other DB clients first",
        )


def counts(connection):
    from psycopg2 import sql

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )
        tables = [row[0] for row in cursor.fetchall()]
        result = {}
        for table in tables:
            cursor.execute(
                sql.SQL("SELECT count(*) FROM public.{}").format(sql.Identifier(table))
            )
            result[table] = cursor.fetchone()[0]
    return result


def object_inventory(client, bucket):
    return {
        obj.object_name: (obj.etag, obj.size)
        for obj in client.list_objects(bucket, recursive=True)
    }


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def references(connection, client, bucket, old_bucket=None):
    from psycopg2 import sql

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND column_name IN ('original_bucket', 'annotated_bucket')"
        )
        columns = cursor.fetchall()
        for table, bucket_column in columns:
            key_column = bucket_column.replace("_bucket", "_object_key")
            if old_bucket is not None:
                cursor.execute(
                    sql.SQL("UPDATE public.{} SET {} = %s WHERE {} = %s").format(
                        sql.Identifier(table),
                        sql.Identifier(bucket_column),
                        sql.Identifier(bucket_column),
                    ),
                    (bucket, old_bucket),
                )
            cursor.execute(
                sql.SQL("SELECT {}, {} FROM public.{} WHERE {} IS NOT NULL").format(
                    sql.Identifier(bucket_column),
                    sql.Identifier(key_column),
                    sql.Identifier(table),
                    sql.Identifier(key_column),
                )
            )
            for referenced_bucket, key in cursor.fetchall():
                require(
                    referenced_bucket == bucket,
                    "Cross-bucket reference: explicit recovery plan required",
                )
                client.stat_object(bucket, key)


def provision_marker(connection, env):
    require(
        not counts(connection),
        "Marker can only be provisioned before application migrations",
    )
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        require(
            cursor.fetchone()[0] == env["PGDATABASE"], "Connected database mismatch"
        )
        cursor.execute("CREATE SCHEMA ops_control")
        cursor.execute("REVOKE ALL ON SCHEMA ops_control FROM PUBLIC")
        cursor.execute(
            "CREATE TABLE ops_control.identity (singleton boolean PRIMARY KEY CHECK(singleton), "
            "mode text NOT NULL, namespace text NOT NULL, instance_id uuid NOT NULL)"
        )
        cursor.execute(
            "INSERT INTO ops_control.identity VALUES (true, %s, %s, %s)",
            (env["OPS_MODE"], env["OPS_NAMESPACE"], env["OPS_INSTANCE_ID"]),
        )


def backup(connection, client, env, folder, config_file):
    before = counts(connection)
    inventory = object_inventory(client, env["S3_BUCKET"])
    references(connection, client, env["S3_BUCKET"])
    run(
        [
            "pg_dump",
            "--format=custom",
            "--no-owner",
            "--no-acl",
            "--exclude-schema=ops_control",
            "--file",
            str(folder / "database.dump"),
        ],
        pg_environment(env),
    )
    objects = []
    (folder / "objects").mkdir()
    for index, key in enumerate(sorted(inventory)):
        path = folder / "objects" / str(index)
        stat = client.stat_object(env["S3_BUCKET"], key)
        client.fget_object(env["S3_BUCKET"], key, str(path))
        objects.append(
            {
                "key": key,
                "file": f"objects/{index}",
                "sha256": digest(path),
                "size": path.stat().st_size,
                "content_type": stat.content_type,
            }
        )
    require(
        before == counts(connection)
        and inventory == object_inventory(client, env["S3_BUCKET"]),
        "Data changed during backup; discard this attempt",
    )
    quiescent(connection)
    config = read_env(config_file)
    public_config = {
        key: config[key]
        for key in IMAGE_KEYS
        + (
            "TIMEZONE",
            "SEMESTER_START",
            "SEMESTER_END",
            "MODEL_SHA256",
            "ORIGINAL_RETENTION_DAYS",
            "ANNOTATED_RETENTION_DAYS",
        )
        if key in config
    }
    manifest = {
        "format": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "namespace": env["OPS_NAMESPACE"],
        "bucket": env["S3_BUCKET"],
        "counts": before,
        "objects": objects,
        "database_sha256": digest(folder / "database.dump"),
        "config": public_config,
        "keys": "Recover separately from owner-controlled key vault",
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))
    result = run(
        ["restic", "backup", "--json", "--tag", env["OPS_NAMESPACE"], str(folder)],
        restic_environment(env),
    )
    summary = next(
        (
            json.loads(line)
            for line in result.splitlines()
            if json.loads(line).get("message_type") == "summary"
        ),
        {},
    )
    require(summary.get("snapshot_id"), "Restic did not return a snapshot ID")
    return {
        "snapshot": summary["snapshot_id"],
        "point": manifest["created_at"],
        "status": "backup_created",
        "restore_verified": False,
    }


def restore(connection, client, env, folder, snapshot):
    require(
        re.fullmatch(r"[a-f0-9]{64}", snapshot or ""),
        "Exact 64-character snapshot ID required; no latest",
    )
    require(not counts(connection), "Restore refuses any existing public tables")
    require(
        not object_inventory(client, env["S3_BUCKET"]),
        "Restore refuses nonempty bucket",
    )
    run(
        ["restic", "restore", snapshot, "--target", str(folder)],
        restic_environment(env),
    )
    manifests = list(folder.rglob("manifest.json"))
    require(len(manifests) == 1, "Snapshot must contain exactly one backup manifest")
    root = manifests[0].parent
    manifest = json.loads(manifests[0].read_text())
    require(manifest.get("format") == 1, "Unsupported backup format")
    require(
        manifest["namespace"] != env["OPS_NAMESPACE"],
        "Restore must use another namespace",
    )
    require(
        digest(root / "database.dump") == manifest["database_sha256"],
        "Dump checksum mismatch",
    )
    for item in manifest["objects"]:
        require(
            re.fullmatch(r"objects/[0-9]+", item["file"]),
            "Invalid backup object filename",
        )
        path = root / item["file"]
        require(
            not path.is_symlink() and digest(path) == item["sha256"],
            "Object checksum mismatch",
        )
    quiescent(connection)
    for item in manifest["objects"]:
        client.fput_object(
            env["S3_BUCKET"],
            item["key"],
            str(root / item["file"]),
            content_type=item.get("content_type") or "application/octet-stream",
        )
    run(
        [
            "pg_restore",
            "--exit-on-error",
            "--single-transaction",
            "--no-owner",
            "--no-acl",
            "--dbname",
            env["PGDATABASE"],
            str(root / "database.dump"),
        ],
        pg_environment(env),
    )
    references(connection, client, env["S3_BUCKET"], old_bucket=manifest["bucket"])
    require(counts(connection) == manifest["counts"], "Restored row counts differ")
    for item in manifest["objects"]:
        response = client.get_object(env["S3_BUCKET"], item["key"])
        try:
            checksum = hashlib.sha256()
            for chunk in response.stream(1024 * 1024):
                checksum.update(chunk)
            require(
                checksum.hexdigest() == item["sha256"],
                "Restored media checksum differs",
            )
        finally:
            response.close()
            response.release_conn()
    return {
        "status": "data_restore_verified",
        "snapshot": snapshot,
        "point": manifest["created_at"],
        "application_smoke": "not_run",
        "namespace": env["OPS_NAMESPACE"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["mark", "backup", "restore", "reset", "retention"]
    )
    parser.add_argument("--env-file", required=True)
    parser.add_argument(
        "--config-file",
        help="Private Compose env file included without secrets in backup",
    )
    parser.add_argument("--snapshot")
    parser.add_argument(
        "--evidence", help="New private JSON evidence path, never overwritten"
    )
    parser.add_argument(
        "--quiesced",
        action="store_true",
        help="Owner confirms all writers and lifecycle deletion stopped",
    )
    args = parser.parse_args()
    os.umask(0o077)
    env = read_env(args.env_file)
    validate_target(env, args.action)
    confirm(args.action, env["OPS_NAMESPACE"])
    if args.action == "retention":
        run(
            [
                "restic",
                "forget",
                "--tag",
                env["OPS_NAMESPACE"],
                "--keep-daily",
                "7",
                "--keep-weekly",
                "4",
                "--keep-monthly",
                "12",
                "--prune",
            ],
            restic_environment(env),
        )
        return
    require(
        args.quiesced,
        "Explicit --quiesced acknowledgment required; also disable S3 lifecycle during copy",
    )
    connection, client = connect(env)
    try:
        quiescent(connection)
        if args.action == "mark":
            provision_marker(connection, env)
            print(
                "Database identity provisioned; do not grant ops_control access to runtime roles"
            )
            return
        database, marker = identity(connection)
        validate_target(env, args.action, marker, database)
        if args.action == "reset":
            # Identity is outside public and survives resets. No unscoped volume deletion.
            for obj in client.list_objects(env["S3_BUCKET"], recursive=True):
                client.remove_object(env["S3_BUCKET"], obj.object_name)
            with connection.cursor() as cursor:
                cursor.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
            print(
                "Demo data removed. Run migrations, grants and seed explicitly before restart."
            )
            return
        require(
            args.evidence and not Path(args.evidence).exists(),
            "New evidence path required",
        )
        require(
            args.action != "backup" or args.config_file, "Backup requires --config-file"
        )
        stage = Path(env.get("BACKUP_STAGING_DIR", ""))
        require(
            stage.is_dir() and env.get("BACKUP_STAGING_ENCRYPTED") == "true",
            "Owner-confirmed encrypted staging filesystem required",
        )
        started = time.monotonic()
        with tempfile.TemporaryDirectory(
            prefix="attendance-backup-", dir=stage
        ) as folder:
            if args.action == "backup":
                evidence = backup(
                    connection, client, env, Path(folder), args.config_file
                )
            else:
                evidence = restore(connection, client, env, Path(folder), args.snapshot)
        evidence["elapsed_seconds"] = round(time.monotonic() - started, 3)
        with Path(args.evidence).open("x") as output:
            json.dump(evidence, output, indent=2)
        print(
            f"{evidence['status']}; private evidence written. Application acceptance is separate."
        )
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # DB/S3 exceptions can embed credentials, connection details or object names.
        detail = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        raise SystemExit(
            f"Data operation refused/failed: {detail}; no success claimed"
        ) from None
