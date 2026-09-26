"""Explicit, namespace-bounded PostgreSQL role provisioning; never prints DSNs."""

import argparse
import re
from urllib.parse import unquote, urlsplit

import psycopg2
from psycopg2 import sql

from common import DSN_KEYS, read_env, require
from data import pg_environment
from manage import confirm

BACKEND_CRUD = {
    "groups",
    "teachers",
    "disciplines",
    "classrooms",
    "cameras",
    "classroom_cameras",
    "schedule",
    "sessions",
    "calendar_exceptions",
    "users",
    "login_sessions",
    "access_grants",
    "login_attempts",
    "measurements",
    "camera_captures",
    "recognition_uploads",
    "recognition_jobs",
    "recognition_results",
    "attendance_records",
    "idempotency_records",
    "import_previews",
}
BACKEND_APPEND = {
    "audit_events",
    "recognition_corrections",
    "measurement_result_sources",
}
BACKEND_READ = {"alembic_version", "detection_snapshots"}
KNOWN_TABLES = BACKEND_CRUD | BACKEND_APPEND | BACKEND_READ
GRANTS = {
    "BACKEND_DATABASE_URL": {
        **{table: "SELECT, INSERT, UPDATE, DELETE" for table in BACKEND_CRUD},
        **{table: "SELECT, INSERT" for table in BACKEND_APPEND},
        **{table: "SELECT" for table in BACKEND_READ},
    },
    "CAPTURE_DATABASE_URL": {
        "cameras": "SELECT",
        "measurements": "SELECT",
        "camera_captures": "SELECT, UPDATE",
        "recognition_jobs": "SELECT, INSERT",
    },
    "RECOGNITION_DATABASE_URL": {
        "recognition_jobs": "SELECT, UPDATE",
        "recognition_results": "SELECT, INSERT",
        "camera_captures": "SELECT",
        "measurements": "SELECT",
        "recognition_uploads": "SELECT",
    },
}


def role_config(env):
    project = env.get("COMPOSE_PROJECT_NAME", "")
    require(
        re.fullmatch(r"attendance-(prod|demo|dev|restore)-[a-z0-9-]+", project),
        "Invalid role target namespace",
    )
    database = project.replace("-", "_")
    require(env.get("DB_NAME") == database, "Database namespace mismatch")
    roles = {}
    for key in DSN_KEYS:
        dsn = urlsplit(env.get(key, ""))
        name, password = unquote(dsn.username or ""), unquote(dsn.password or "")
        require(
            dsn.scheme in {"postgresql", "postgresql+psycopg2"}
            and dsn.hostname == "db"
            and dsn.path == "/" + database
            and not dsn.query,
            f"Invalid {key} target",
        )
        require(
            name.startswith(database + "_")
            and len(name) <= 63
            and re.fullmatch(r"[a-z_][a-z0-9_]*", name),
            "Role must use database namespace prefix (max 63 chars)",
        )
        require(len(password) >= 24, "Role password must be at least 24 characters")
        roles[key] = (name, password)
    require(
        len({value[0] for value in roles.values()}) == 4, "Four distinct roles required"
    )
    require(
        env.get("DB_ADMIN_USER") not in {value[0] for value in roles.values()},
        "Administrator cannot be migration/runtime",
    )
    require(
        len({value[1] for value in roles.values()}) == 4,
        "Four distinct role passwords required",
    )
    return roles


def check_admin(connection, env):
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), session_user")
        require(
            cursor.fetchone() == (env["DB_NAME"], env["DB_ADMIN_USER"]),
            "Connected administrator/DB differs from reviewed target",
        )


def check_roles(cursor, env, roles):
    marker = "attendance-managed:" + env["COMPOSE_PROJECT_NAME"]
    for name, _ in roles.values():
        cursor.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, "
            "rolinherit, shobj_description(oid, 'pg_authid') FROM pg_roles WHERE rolname=%s",
            (name,),
        )
        row = cursor.fetchone()
        require(
            row is not None and row[:6] == (False,) * 6 and row[6] == marker,
            "Role attributes or ownership marker differ",
        )
        cursor.execute(
            "SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=%s)",
            (name,),
        )
        require(
            cursor.fetchone()[0] == 0,
            "Managed roles must not inherit membership privileges",
        )


def initialize(connection, env):
    roles = role_config(env)
    check_admin(connection, env)
    with connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'")
            require(
                cursor.fetchone()[0] == 0,
                "role-init requires empty public schema; use role-grants after migrate/restore",
            )
            for name, password in roles.values():
                cursor.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (name,))
                if not cursor.fetchone():
                    cursor.execute(
                        sql.SQL(
                            "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE "
                            "NOREPLICATION NOBYPASSRLS PASSWORD %s"
                        ).format(sql.Identifier(name)),
                        (password,),
                    )
                    cursor.execute(
                        sql.SQL("COMMENT ON ROLE {} IS %s").format(
                            sql.Identifier(name)
                        ),
                        ("attendance-managed:" + env["COMPOSE_PROJECT_NAME"],),
                    )
            check_roles(cursor, env, roles)
            migration = roles["MIGRATION_DATABASE_URL"][0]
            cursor.execute(
                sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(
                    sql.Identifier(env["DB_NAME"])
                )
            )
            cursor.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
            cursor.execute(
                sql.SQL("ALTER SCHEMA public OWNER TO {}").format(
                    sql.Identifier(migration)
                )
            )
            for name, _ in roles.values():
                cursor.execute(
                    sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                        sql.Identifier(env["DB_NAME"]), sql.Identifier(name)
                    )
                )
                cursor.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                        sql.Identifier(name)
                    )
                )


def apply_grants(connection, env):
    roles = role_config(env)
    check_admin(connection, env)
    migration = roles["MIGRATION_DATABASE_URL"][0]
    runtime = [roles[key][0] for key in GRANTS]
    with connection:
        with connection.cursor() as cursor:
            check_roles(cursor, env, roles)
            cursor.execute(
                "SELECT tablename, tableowner FROM pg_tables WHERE schemaname='public'"
            )
            tables = dict(cursor.fetchall())
            require(
                set(tables) == KNOWN_TABLES,
                "Unreviewed/missing tables: update explicit grant map after schema review",
            )
            require(
                set(tables.values()) <= {env["DB_ADMIN_USER"], migration},
                "Unexpected table owner; refuse ownership takeover",
            )
            cursor.execute(
                "SELECT count(*) FROM pg_class WHERE relowner IN (SELECT oid FROM pg_roles WHERE rolname=ANY(%s))",
                (runtime,),
            )
            require(
                cursor.fetchone()[0] == 0, "Runtime roles must not own database objects"
            )
            cursor.execute(
                sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(
                    sql.Identifier(env["DB_NAME"])
                )
            )
            cursor.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
            cursor.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC")
            cursor.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC")
            cursor.execute("REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC")
            cursor.execute(
                sql.SQL("ALTER SCHEMA public OWNER TO {}").format(
                    sql.Identifier(migration)
                )
            )
            for name in runtime:
                ident = sql.Identifier(name)
                cursor.execute(
                    sql.SQL("REVOKE ALL ON DATABASE {} FROM {}").format(
                        sql.Identifier(env["DB_NAME"]), ident
                    )
                )
                cursor.execute(
                    sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                        sql.Identifier(env["DB_NAME"]), ident
                    )
                )
                cursor.execute(
                    sql.SQL("REVOKE ALL ON SCHEMA public FROM {}").format(ident)
                )
                cursor.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(ident)
                )
                for objects in ("TABLES", "SEQUENCES", "FUNCTIONS"):
                    cursor.execute(
                        sql.SQL("REVOKE ALL ON ALL {} IN SCHEMA public FROM {}").format(
                            sql.SQL(objects), ident
                        )
                    )
            for owner in (migration, env["DB_ADMIN_USER"]):
                for grantee in [
                    sql.SQL("PUBLIC"),
                    *(sql.Identifier(name) for name in runtime),
                ]:
                    for objects in ("TABLES", "SEQUENCES", "FUNCTIONS"):
                        cursor.execute(
                            sql.SQL(
                                "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                                "REVOKE ALL ON {} FROM {}"
                            ).format(sql.Identifier(owner), sql.SQL(objects), grantee)
                        )
            for table in sorted(tables):
                cursor.execute(
                    sql.SQL("ALTER TABLE public.{} OWNER TO {}").format(
                        sql.Identifier(table), sql.Identifier(migration)
                    )
                )
            for key, grants in GRANTS.items():
                role = sql.Identifier(roles[key][0])
                for table, privileges in grants.items():
                    cursor.execute(
                        sql.SQL("GRANT {} ON TABLE public.{} TO {}").format(
                            sql.SQL(privileges), sql.Identifier(table), role
                        )
                    )
                    if "INSERT" in privileges:
                        cursor.execute(
                            "SELECT pg_get_serial_sequence(%s, a.attname) FROM pg_attribute a "
                            "WHERE a.attrelid=%s::regclass AND a.attnum>0 AND NOT a.attisdropped",
                            ("public." + table, "public." + table),
                        )
                        for (sequence,) in cursor.fetchall():
                            if sequence:
                                schema, name = sequence.split(".", 1)
                                cursor.execute(
                                    sql.SQL(
                                        "GRANT USAGE, SELECT ON SEQUENCE {}.{} TO {}"
                                    ).format(
                                        sql.Identifier(schema),
                                        sql.Identifier(name),
                                        role,
                                    )
                                )
            cursor.execute("SELECT to_regnamespace('ops_control')")
            if cursor.fetchone()[0] is not None:
                for name, _ in roles.values():
                    cursor.execute(
                        sql.SQL("REVOKE ALL ON SCHEMA ops_control FROM {}").format(
                            sql.Identifier(name)
                        )
                    )
                    cursor.execute(
                        sql.SQL(
                            "REVOKE ALL ON ALL TABLES IN SCHEMA ops_control FROM {}"
                        ).format(sql.Identifier(name))
                    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["role-init", "role-grants"])
    parser.add_argument(
        "--env-file",
        required=True,
        help="Private Compose env containing namespace and four DSNs",
    )
    parser.add_argument(
        "--admin-env-file",
        required=True,
        help="Private PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSFILE file",
    )
    args = parser.parse_args()
    env, admin = read_env(args.env_file), read_env(args.admin_env_file)
    role_config(env)
    require(
        admin.get("PGDATABASE") == env["DB_NAME"]
        and admin.get("PGUSER") == env["DB_ADMIN_USER"],
        "Admin connection target mismatch",
    )
    pg_environment(admin)
    confirm(args.action, env["COMPOSE_PROJECT_NAME"])
    connection = psycopg2.connect(
        host=admin["PGHOST"],
        port=admin.get("PGPORT", "5432"),
        dbname=admin["PGDATABASE"],
        user=admin["PGUSER"],
        passfile=admin["PGPASSFILE"],
        sslmode=admin["PGSSLMODE"],
        sslrootcert=admin.get("PGSSLROOTCERT"),
        connect_timeout=5,
    )
    try:
        (initialize if args.action == "role-init" else apply_grants)(connection, env)
    finally:
        connection.close()
    print("Role operation completed; no passwords or DSNs printed")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        detail = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        raise SystemExit(f"Role operation refused/failed: {detail}") from None
