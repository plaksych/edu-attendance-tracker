"""Fence worker attempts and retain the actual inference pipeline metadata."""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("camera_captures", "recognition_jobs"):
        op.add_column(table, sa.Column("claim_token", sa.String(36)))
        op.create_index(f"ix_{table}_claim_token", table, ["claim_token"])
    op.add_column("recognition_results", sa.Column("inference_metadata", JSONB))


def downgrade():
    raise RuntimeError("Worker fencing cannot be removed during service operation")
