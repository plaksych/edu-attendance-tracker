"""Начальная схема: справочники, расписание, занятия, посещаемость

Revision ID: 0001
Revises:
Create Date: 2026-07-03

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

session_status = sa.Enum(
    "scheduled", "in_progress", "finished", name="session_status"
)
week_type = sa.Enum("every", "white", "green", name="week_type")


def upgrade() -> None:
    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("course", sa.Integer(), nullable=False),
        sa.Column("faculty", sa.String(length=200), nullable=True),
        sa.Column("students_count", sa.Integer(), nullable=False),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_groups_name"), "groups", ["name"])

    op.create_table(
        "teachers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("department", sa.String(length=200), nullable=True),
        sa.UniqueConstraint("full_name", name="uq_teachers_full_name"),
    )
    op.create_index(op.f("ix_teachers_full_name"), "teachers", ["full_name"])

    op.create_table(
        "disciplines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_disciplines_name"), "disciplines", ["name"])

    op.create_table(
        "classrooms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number", sa.String(length=50), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("camera_url", sa.String(length=500), nullable=True),
        sa.UniqueConstraint("number"),
    )
    op.create_index(op.f("ix_classrooms_number"), "classrooms", ["number"])

    op.create_table(
        "schedule",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "group_id",
            sa.Integer(),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "teacher_id",
            sa.Integer(),
            sa.ForeignKey("teachers.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "discipline_id",
            sa.Integer(),
            sa.ForeignKey("disciplines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "classroom_id",
            sa.Integer(),
            sa.ForeignKey("classrooms.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("starts_at", sa.Time(), nullable=False),
        sa.Column("ends_at", sa.Time(), nullable=False),
        sa.Column("week_type", week_type, nullable=False, server_default="every"),
        sa.Column("lesson_type", sa.String(length=20), nullable=True),
        sa.UniqueConstraint(
            "group_id", "weekday", "starts_at", "week_type", name="uq_schedule_group_slot"
        ),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "schedule_id",
            sa.Integer(),
            sa.ForeignKey("schedule.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("status", session_status, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("schedule_id", "date", name="uq_sessions_schedule_date"),
    )
    op.create_index(op.f("ix_sessions_date"), "sessions", ["date"])

    op.create_table(
        "detection_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("person_count", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("frame_path", sa.String(length=500), nullable=True),
    )
    op.create_index(
        op.f("ix_detection_snapshots_session_id"),
        "detection_snapshots",
        ["session_id"],
    )

    op.create_table(
        "attendance_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("expected_count", sa.Integer(), nullable=False),
        sa.Column("detected_avg", sa.Float(), nullable=False),
        sa.Column("detected_max", sa.Integer(), nullable=False),
        sa.Column("snapshots_count", sa.Integer(), nullable=False),
        sa.Column("attendance_rate", sa.Float(), nullable=True),
        sa.UniqueConstraint("session_id"),
    )


def downgrade() -> None:
    op.drop_table("attendance_records")
    op.drop_table("detection_snapshots")
    op.drop_table("sessions")
    op.drop_table("schedule")
    op.drop_table("classrooms")
    op.drop_table("disciplines")
    op.drop_table("teachers")
    op.drop_table("groups")
    session_status.drop(op.get_bind(), checkfirst=True)
    week_type.drop(op.get_bind(), checkfirst=True)
