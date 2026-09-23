"""Add private sessions, explicit teacher scope and immutable audit records."""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(120), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("auth_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('admin','operator','teacher','analyst')", name="ck_users_role"))
    op.create_table("login_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column("auth_version", sa.Integer, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_login_sessions_user_id", "login_sessions", ["user_id"])
    op.create_index("ix_login_sessions_expires_at", "login_sessions", ["expires_at"])
    op.create_table("access_grants",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("group_id", sa.Integer, sa.ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True))
    op.create_table("login_attempts",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False))
    op.create_table("audit_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("actor_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("object_type", sa.String(100), nullable=False),
        sa.Column("object_id", sa.String(120)),
        sa.Column("reason", sa.String(500)),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.add_column("recognition_uploads", sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")))
    op.add_column("recognition_uploads", sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id", ondelete="RESTRICT")))
    op.add_column("recognition_uploads", sa.Column("measurement_id", sa.Integer, sa.ForeignKey("measurements.id", ondelete="RESTRICT")))
    op.add_column("recognition_uploads", sa.Column("content_sha256", sa.String(64)))
    op.create_index("ix_recognition_uploads_owner_id", "recognition_uploads", ["owner_id"])
    op.create_index("ix_recognition_uploads_session_id", "recognition_uploads", ["session_id"])
    op.add_column("sessions", sa.Column("expected_count_snapshot", sa.Integer))
    op.add_column("sessions", sa.Column("aggregation_mode_snapshot", sa.String(30), server_default="single", nullable=False))
    op.execute("""UPDATE sessions s SET expected_count_snapshot = COALESCE(
        (SELECT expected_count FROM attendance_records a WHERE a.session_id=s.id),
        (SELECT g.students_count FROM schedule sc JOIN groups g ON g.id=sc.group_id WHERE sc.id=s.schedule_id))""")


def downgrade():
    raise RuntimeError("Security downgrade removes access controls. Restore a reviewed backup instead.")
