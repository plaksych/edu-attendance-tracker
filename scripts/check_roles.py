"""Native role/grant test using a newly-created temporary database, never production."""

import os
from pathlib import Path
import secrets
import subprocess
import sys
from urllib.parse import quote
import uuid

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import parse_dsn

sys.path.insert(0, str(Path(__file__).parent / "ops"))
from roles import apply_grants, initialize, role_config  # noqa: E402
from tasks import ROOT, python  # noqa: E402


def main():
    dsn = os.environ.get("TEST_DATABASE_URL") or os.environ.get("QUEUE_TEST_DSN")
    if not dsn:
        raise SystemExit("Explicit TEST_DATABASE_URL required")
    dsn = dsn.replace("postgresql+psycopg2://", "postgresql://", 1)
    parameters = parse_dsn(dsn)
    assert (
        parameters.get("host") in {"localhost", "127.0.0.1"}
        and parameters.get("dbname") == "attendance_test"
    )
    suffix = uuid.uuid4().hex[:10]
    project = "attendance-dev-rolecheck-" + suffix
    database = project.replace("-", "_")
    config = {
        "COMPOSE_PROJECT_NAME": project,
        "DB_NAME": database,
        "DB_ADMIN_USER": parameters["user"],
    }
    for key, label in [
        ("BACKEND_DATABASE_URL", "api"),
        ("MIGRATION_DATABASE_URL", "migrate"),
        ("CAPTURE_DATABASE_URL", "capture"),
        ("RECOGNITION_DATABASE_URL", "recognition"),
    ]:
        config[key] = (
            f"postgresql://{database}_{label}:{secrets.token_hex(24)}@db:5432/{database}"
        )
    roles = role_config(config)
    control = psycopg2.connect(dsn)
    control.autocommit = True
    connection = None
    try:
        with control.cursor() as cursor:
            cursor.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database))
            )
        connection = psycopg2.connect(**{**parameters, "dbname": database})
        initialize(connection, config)
        role, password = roles["MIGRATION_DATABASE_URL"]
        url = f"postgresql://{quote(role)}:{quote(password)}@{parameters['host']}:{parameters.get('port', '5432')}/{database}"
        result = subprocess.run(
            [python("backend"), "-m", "alembic", "upgrade", "head"],
            cwd=ROOT / "backend",
            env={**os.environ, "DATABASE_URL": url, "ENVIRONMENT": "test"},
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise AssertionError(
                "Migration as non-superuser schema owner failed (DSN output withheld)"
            )
        apply_grants(connection, config)
        apply_grants(connection, config)  # Idempotent after migrate/restore.
        connection.autocommit = True
        with connection.cursor() as cursor:
            api = roles["BACKEND_DATABASE_URL"][0]
            cursor.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(api)))
            cursor.execute(
                "INSERT INTO audit_events(action, object_type, request_id) VALUES ('role-test','test','test')"
            )
            cursor.execute("SELECT count(*) FROM audit_events")
            assert cursor.fetchone()[0] == 1
            cursor.execute("SELECT count(*) FROM measurement_result_sources")
            assert cursor.fetchone()[0] == 0
            cursor.execute(
                "SELECT has_table_privilege(current_user, 'measurement_result_sources', 'INSERT')"
            )
            assert cursor.fetchone()[0]
            for statement in (
                "UPDATE audit_events SET action='tampered'",
                "DELETE FROM audit_events",
                "TRUNCATE audit_events",
                "UPDATE measurement_result_sources SET used_for_count=false",
                "DELETE FROM measurement_result_sources",
                "TRUNCATE measurement_result_sources",
                "CREATE TABLE public.forbidden(id int)",
            ):
                try:
                    cursor.execute(statement)
                except psycopg2.errors.InsufficientPrivilege:
                    pass
                else:
                    raise AssertionError("Backend privilege escalation accepted")
            cursor.execute("RESET ROLE")
            for key in ("CAPTURE_DATABASE_URL", "RECOGNITION_DATABASE_URL"):
                name = roles[key][0]
                cursor.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(name)))
                for table in (
                    "users",
                    "login_sessions",
                    "audit_events",
                    "measurement_result_sources",
                ):
                    try:
                        cursor.execute(
                            sql.SQL("SELECT * FROM public.{}").format(
                                sql.Identifier(table)
                            )
                        )
                    except psycopg2.errors.InsufficientPrivilege:
                        pass
                    else:
                        raise AssertionError("Worker read privileged application data")
                cursor.execute("RESET ROLE")
                for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                    cursor.execute(
                        "SELECT has_table_privilege(%s, 'measurement_result_sources', %s)",
                        (name, privilege),
                    )
                    assert not cursor.fetchone()[0]
        print(
            "PASS: native temporary DB migrations as owner, grants idempotent, audit/provenance append-only, worker access denied"
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
            for name, _ in roles.values():
                cursor.execute(
                    sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(name))
                )
        control.close()


if __name__ == "__main__":
    main()
