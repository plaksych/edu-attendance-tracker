"""Freeze capture configuration and preserve finalized recognition provenance.

Legacy configuration can only be recovered from current classroom links. Such
snapshots are explicitly marked legacy_current_link, not asserted to be original.
Missing links remain NULL/legacy_unknown; aggregation sorts unknown priorities
after known ones and breaks ties by camera ID, without consulting live links.
Sum requires distinct, nonempty snapshotted zones. No old count is recalculated.

Previously finalized measurements have no reliable evidence of which retry or
camera selection produced their count. They are marked legacy_unknown and receive
no fabricated source IDs. All new finalizations record exact result FKs.
Deleting referenced measurements or results requires a reviewed provenance purge.
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("camera_captures", sa.Column("role_snapshot", sa.String(20)))
    op.add_column("camera_captures", sa.Column("priority_snapshot", sa.Integer()))
    op.add_column("camera_captures", sa.Column("zone_code_snapshot", sa.String(50)))
    op.add_column(
        "camera_captures",
        sa.Column(
            "snapshot_origin", sa.String(30), nullable=False, server_default="unknown"
        ),
    )
    op.execute("UPDATE camera_captures SET snapshot_origin = 'legacy_unknown'")
    op.execute("""UPDATE camera_captures c SET
        role_snapshot = link.role::text, priority_snapshot = link.priority,
        zone_code_snapshot = link.zone_code, snapshot_origin = 'legacy_current_link'
        FROM measurements m JOIN sessions s ON s.id = m.session_id
        JOIN schedule sch ON sch.id = s.schedule_id
        JOIN classroom_cameras link ON link.classroom_id = sch.classroom_id
        WHERE c.measurement_id = m.id AND c.camera_id = link.camera_id""")
    op.add_column("measurements", sa.Column("source_reference_status", sa.String(30)))
    op.execute("""UPDATE measurements SET source_reference_status = 'legacy_unknown'
        WHERE status IN ('completed', 'partially_completed', 'failed', 'cancelled')""")
    op.create_table(
        "measurement_result_sources",
        sa.Column(
            "measurement_id",
            sa.Integer(),
            sa.ForeignKey("measurements.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "recognition_result_id",
            sa.Integer(),
            sa.ForeignKey("recognition_results.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("used_for_count", sa.Boolean(), nullable=False),
    )


def downgrade():
    raise RuntimeError(
        "Dropping immutable measurement provenance requires reviewed restoration"
    )
