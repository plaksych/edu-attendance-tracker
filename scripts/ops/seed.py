"""Offline synthetic catalogs only, restricted to an existing marked demo DB."""

import argparse
from datetime import date
import json

import psycopg2
from psycopg2 import sql

from common import read_env, require
from data import identity, pg_environment, validate_target
from manage import confirm


def seed(connection, env, teaching_date):
    validate_target(env, "seed")
    require(not connection.autocommit, "Seed requires a transactional connection")
    with connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute("SET LOCAL statement_timeout = '30s'")
            cursor.execute("LOCK TABLE ops_control.identity IN SHARE MODE")
            database, marker = identity(connection)
            validate_target(env, "seed", marker, database)
            cursor.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
            )
            tables = [row[0] for row in cursor.fetchall()]
            require(
                {
                    "alembic_version",
                    "groups",
                    "teachers",
                    "disciplines",
                    "classrooms",
                    "schedule",
                }
                <= set(tables),
                "Migrate the demo database before seeding",
            )
            # Lock every application table before the emptiness check and all writes.
            cursor.execute(
                sql.SQL("LOCK TABLE {} IN ACCESS EXCLUSIVE MODE").format(
                    sql.SQL(", ").join(
                        sql.Identifier("public", table) for table in tables
                    )
                )
            )
            for table in tables:
                if table == "alembic_version":
                    continue
                cursor.execute(
                    sql.SQL("SELECT EXISTS(SELECT 1 FROM {})").format(
                        sql.Identifier("public", table)
                    )
                )
                require(
                    not cursor.fetchone()[0], "Seed refuses nonempty application tables"
                )
            cursor.execute(
                "INSERT INTO teachers(full_name, email, department) "
                "VALUES ('Synthetic Demo Teacher', NULL, 'Synthetic department') RETURNING id"
            )
            teacher = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO classrooms(number, capacity, aggregation_mode) "
                "VALUES ('DEMO-101', 30, 'single') RETURNING id"
            )
            classroom = cursor.fetchone()[0]
            for name, discipline, starts, ends in (
                ("DEMO-A", "Synthetic Mathematics", "09:00", "10:30"),
                ("DEMO-B", "Synthetic Computing", "10:45", "12:15"),
            ):
                cursor.execute(
                    "INSERT INTO groups(name, course, faculty, students_count) "
                    "VALUES (%s, 1, 'Synthetic faculty', 20) RETURNING id",
                    (name,),
                )
                group = cursor.fetchone()[0]
                cursor.execute(
                    "INSERT INTO disciplines(name) VALUES (%s) RETURNING id",
                    (discipline,),
                )
                subject = cursor.fetchone()[0]
                cursor.execute(
                    "INSERT INTO schedule(group_id, teacher_id, discipline_id, classroom_id, "
                    "weekday, starts_at, ends_at, week_type, lesson_type) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, 'every', 'demo')",
                    (
                        group,
                        teacher,
                        subject,
                        classroom,
                        teaching_date.isoweekday(),
                        starts,
                        ends,
                    ),
                )
    return {
        "seed_version": 1,
        "teaching_date": teaching_date.isoformat(),
        "weekday": teaching_date.isoweekday(),
        "groups": 2,
        "teachers": 1,
        "disciplines": 2,
        "classrooms": 1,
        "schedule": 2,
        "users_created": 0,
        "recognition_results_created": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    env = read_env(args.env_file)
    validate_target(env, "seed")
    pg_environment(env)
    confirm("seed", env["OPS_NAMESPACE"])
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
    try:
        print(json.dumps(seed(connection, env, args.date), indent=2))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
