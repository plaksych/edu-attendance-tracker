"""Add uploaded files as recognition job sources.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-09
"""

import sqlalchemy as sa
from alembic import op


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    media_type = sa.Enum("image", "video", name="recognition_media_type")
    op.create_table(
        "recognition_uploads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", media_type, nullable=False),
        sa.Column("original_bucket", sa.String(length=100), nullable=False),
        sa.Column("original_object_key", sa.String(length=700), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "original_object_key", name="uq_recognition_uploads_object_key"
        ),
    )
    op.create_index(
        "ix_recognition_uploads_created", "recognition_uploads", ["created_at", "id"]
    )

    op.alter_column(
        "recognition_jobs",
        "camera_capture_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.add_column(
        "recognition_jobs", sa.Column("upload_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "recognition_jobs_upload_id_fkey",
        "recognition_jobs",
        "recognition_uploads",
        ["upload_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_recognition_jobs_upload", "recognition_jobs", ["upload_id"]
    )
    op.create_check_constraint(
        "ck_recognition_jobs_single_source",
        "recognition_jobs",
        "(camera_capture_id IS NOT NULL AND upload_id IS NULL) "
        "OR (camera_capture_id IS NULL AND upload_id IS NOT NULL)",
    )


def downgrade() -> None:
    # Задания от ручных загрузок не имеют эквивалента в старой схеме.
    op.execute(
        "DELETE FROM recognition_jobs WHERE upload_id IS NOT NULL"
    )
    op.drop_constraint(
        "ck_recognition_jobs_single_source", "recognition_jobs", type_="check"
    )
    op.drop_constraint(
        "uq_recognition_jobs_upload", "recognition_jobs", type_="unique"
    )
    op.drop_constraint(
        "recognition_jobs_upload_id_fkey", "recognition_jobs", type_="foreignkey"
    )
    op.drop_column("recognition_jobs", "upload_id")
    op.alter_column(
        "recognition_jobs",
        "camera_capture_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.drop_index("ix_recognition_uploads_created", table_name="recognition_uploads")
    op.drop_table("recognition_uploads")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE recognition_media_type")
