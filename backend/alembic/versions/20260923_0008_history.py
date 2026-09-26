"""Persist upload request identity, retry history and import confirmations."""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("uq_recognition_jobs_upload", "recognition_jobs", type_="unique")
    op.create_index("ix_recognition_jobs_upload_id", "recognition_jobs", ["upload_id"])
    op.alter_column("cameras", "rtsp_url", type_=sa.String(2000), existing_type=sa.String(1000))
    op.create_table("idempotency_records",
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("route", sa.String(80), primary_key=True),
        sa.Column("key", sa.String(120), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.Integer),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("recognition_corrections",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("job_id", sa.Integer, sa.ForeignKey("recognition_jobs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_id", sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("people_count", sa.Integer, nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("people_count >= 0", name="ck_correction_count"))
    op.create_index("ix_recognition_corrections_job_id", "recognition_corrections", ["job_id"])
    op.create_table("import_previews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed", sa.Boolean, nullable=False, server_default="false"))


def downgrade():
    raise RuntimeError("History cannot be discarded by an automatic downgrade; restore a backup")
