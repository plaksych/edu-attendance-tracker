"""Protect attendance history from configuration deletion.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-09
"""

from alembic import op


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "camera_captures_camera_id_fkey", "camera_captures", type_="foreignkey"
    )
    op.create_foreign_key(
        "camera_captures_camera_id_fkey",
        "camera_captures",
        "cameras",
        ["camera_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint("sessions_schedule_id_fkey", "sessions", type_="foreignkey")
    op.create_foreign_key(
        "sessions_schedule_id_fkey",
        "sessions",
        "schedule",
        ["schedule_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "sessions_schedule_id_fkey", "sessions", type_="foreignkey"
    )
    op.create_foreign_key(
        "sessions_schedule_id_fkey",
        "sessions",
        "schedule",
        ["schedule_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "camera_captures_camera_id_fkey", "camera_captures", type_="foreignkey"
    )
    op.create_foreign_key(
        "camera_captures_camera_id_fkey",
        "camera_captures",
        "cameras",
        ["camera_id"],
        ["id"],
        ondelete="CASCADE",
    )
