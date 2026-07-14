"""Store reference labels and quality metrics for recognition materials.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-14
"""

import sqlalchemy as sa
from alembic import op


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recognition_uploads", sa.Column("label", sa.String(length=160), nullable=True)
    )
    op.add_column(
        "recognition_uploads",
        sa.Column("reference_people_count", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_recognition_uploads_reference_people_count",
        "recognition_uploads",
        "reference_people_count IS NULL OR reference_people_count >= 0",
    )

    op.add_column(
        "recognition_results",
        sa.Column("count_stddev", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "recognition_results",
        sa.Column("source_frames", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "recognition_results",
        sa.Column("source_duration_ms", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "recognition_results", sa.Column("absolute_error", sa.Integer(), nullable=True)
    )
    op.add_column(
        "recognition_results", sa.Column("relative_error", sa.Float(), nullable=True)
    )
    op.add_column(
        "recognition_results", sa.Column("within_tolerance", sa.Boolean(), nullable=True)
    )

    for column in ("count_stddev", "source_frames", "source_duration_ms"):
        op.alter_column("recognition_results", column, server_default=None)


def downgrade() -> None:
    for column in (
        "within_tolerance",
        "relative_error",
        "absolute_error",
        "source_duration_ms",
        "source_frames",
        "count_stddev",
    ):
        op.drop_column("recognition_results", column)

    op.drop_constraint(
        "ck_recognition_uploads_reference_people_count",
        "recognition_uploads",
        type_="check",
    )
    op.drop_column("recognition_uploads", "reference_people_count")
    op.drop_column("recognition_uploads", "label")
