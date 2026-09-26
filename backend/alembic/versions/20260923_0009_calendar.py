"""Calendar overrides and a single explicit upload source for each measurement."""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("calendar_exceptions",
        sa.Column("day", sa.Date, primary_key=True),
        sa.Column("teaching", sa.Boolean, nullable=False),
        sa.Column("weekday", sa.SmallInteger),
        sa.Column("week_type", sa.String(10)),
        sa.Column("reason", sa.String(300), nullable=False))
    op.create_unique_constraint("uq_upload_measurement", "recognition_uploads", ["measurement_id"])


def downgrade():
    raise RuntimeError("Calendar/history rollback requires reviewed restoration")
