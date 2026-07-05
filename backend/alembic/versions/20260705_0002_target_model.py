"""Целевая модель: камеры, замеры, очереди записи и распознавания

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

CAMERA_AGGREGATION_VALUES = ("single", "maximum", "sum", "primary_backup")
ATTENDANCE_STATUS_VALUES = ("complete", "partial", "failed")


def _aggregation_enum(create_type: bool):
    """PG-тип camera_aggregation_mode используется в двух таблицах,
    поэтому создаётся один раз явно, а в колонках — без повторного CREATE TYPE."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(
            *CAMERA_AGGREGATION_VALUES,
            name="camera_aggregation_mode",
            create_type=create_type,
        )
    return sa.Enum(*CAMERA_AGGREGATION_VALUES, name="camera_aggregation_mode")


def _attendance_status_enum(create_type: bool):
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(
            *ATTENDANCE_STATUS_VALUES,
            name="attendance_calculation_status",
            create_type=create_type,
        )
    return sa.Enum(*ATTENDANCE_STATUS_VALUES, name="attendance_calculation_status")


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("ALTER TYPE session_status ADD VALUE IF NOT EXISTS 'cancelled'")
        _aggregation_enum(create_type=True).create(bind, checkfirst=True)
        _attendance_status_enum(create_type=True).create(bind, checkfirst=True)

    # --- камеры ---
    op.create_table(
        "cameras",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("rtsp_url", sa.String(length=1000), nullable=False),
        sa.Column(
            "capture_group",
            sa.String(length=100),
            nullable=False,
            server_default="default",
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_cameras_name"), "cameras", ["name"])

    op.create_table(
        "classroom_cameras",
        sa.Column(
            "classroom_id",
            sa.Integer(),
            sa.ForeignKey("classrooms.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "camera_id",
            sa.Integer(),
            sa.ForeignKey("cameras.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "role",
            sa.Enum("primary", "secondary", "backup", name="camera_role"),
            nullable=False,
            server_default="primary",
        ),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("zone_code", sa.String(length=50), nullable=True),
        sa.UniqueConstraint("camera_id", name="uq_classroom_cameras_camera"),
    )

    op.add_column(
        "classrooms",
        sa.Column(
            "aggregation_mode",
            _aggregation_enum(create_type=False),
            nullable=False,
            server_default="single",
        ),
    )

    # Существующие адреса камер переезжают в отдельную сущность
    op.execute(
        """
        INSERT INTO cameras (name, rtsp_url, capture_group, enabled)
        SELECT 'cam-' || number, camera_url, 'default', true
        FROM classrooms
        WHERE camera_url IS NOT NULL AND camera_url <> ''
        """
    )
    op.execute(
        """
        INSERT INTO classroom_cameras (classroom_id, camera_id, role, priority)
        SELECT c.id, cam.id, 'primary', 1
        FROM classrooms c
        JOIN cameras cam ON cam.name = 'cam-' || c.number
        WHERE c.camera_url IS NOT NULL AND c.camera_url <> ''
        """
    )
    with op.batch_alter_table("classrooms") as batch:
        batch.drop_column("camera_url")

    op.add_column(
        "sessions",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- замеры ---
    op.create_table(
        "measurements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "type",
            sa.Enum("after_start", "before_end", name="measurement_type"),
            nullable=False,
        ),
        sa.Column("planned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "scheduled",
                "capturing",
                "recognizing",
                "completed",
                "partially_completed",
                "failed",
                "cancelled",
                name="measurement_status",
            ),
            nullable=False,
            server_default="scheduled",
        ),
        sa.Column("final_people_count", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "aggregation_method",
            _aggregation_enum(create_type=False),
            nullable=False,
            server_default="single",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("session_id", "type", name="uq_measurements_session_type"),
    )
    op.create_index(op.f("ix_measurements_session_id"), "measurements", ["session_id"])
    op.create_index(
        "ix_measurements_due",
        "measurements",
        ["planned_at"],
        postgresql_where=sa.text("status = 'scheduled'"),
    )

    # --- очередь записи ---
    op.create_table(
        "camera_captures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "measurement_id",
            sa.Integer(),
            sa.ForeignKey("measurements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "camera_id",
            sa.Integer(),
            sa.ForeignKey("cameras.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "claimed",
                "recording",
                "uploading",
                "completed",
                "retry_wait",
                "failed",
                "cancelled",
                name="capture_status",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("planned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "duration_seconds", sa.SmallInteger(), nullable=False, server_default="20"
        ),
        sa.Column("worker_id", sa.String(length=100), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("capture_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("capture_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("original_bucket", sa.String(length=100), nullable=True),
        sa.Column("original_object_key", sa.String(length=700), nullable=True),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("measurement_id", "camera_id", name="uq_camera_captures_slot"),
    )
    op.create_index(
        op.f("ix_camera_captures_measurement_id"), "camera_captures", ["measurement_id"]
    )
    op.create_index(op.f("ix_camera_captures_camera_id"), "camera_captures", ["camera_id"])
    op.create_index(
        "ix_camera_captures_claim",
        "camera_captures",
        ["planned_at", "id"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_camera_captures_lease",
        "camera_captures",
        ["lease_until"],
        postgresql_where=sa.text("status IN ('claimed', 'recording', 'uploading')"),
    )

    # --- очередь распознавания ---
    op.create_table(
        "recognition_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "camera_capture_id",
            sa.Integer(),
            sa.ForeignKey("camera_captures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "processing",
                "retry_wait",
                "completed",
                "failed",
                "cancelled",
                name="recognition_status",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("worker_id", sa.String(length=100), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column(
            "model_name", sa.String(length=100), nullable=False, server_default="yolov8n"
        ),
        sa.Column(
            "model_version", sa.String(length=100), nullable=False, server_default="8"
        ),
        sa.Column("sample_rate_fps", sa.Float(), nullable=False, server_default="1"),
        sa.Column(
            "confidence_threshold", sa.Float(), nullable=False, server_default="0.35"
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("camera_capture_id", name="uq_recognition_jobs_capture"),
    )
    op.create_index(
        "ix_recognition_jobs_claim",
        "recognition_jobs",
        ["created_at", "id"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_recognition_jobs_lease",
        "recognition_jobs",
        ["lease_until"],
        postgresql_where=sa.text("status = 'processing'"),
    )

    op.create_table(
        "recognition_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recognition_job_id",
            sa.Integer(),
            sa.ForeignKey("recognition_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("people_count", sa.Integer(), nullable=False),
        sa.Column("detected_median", sa.Float(), nullable=False),
        sa.Column("detected_percentile_75", sa.Float(), nullable=False),
        sa.Column("detected_max", sa.Integer(), nullable=False),
        sa.Column("average_confidence", sa.Float(), nullable=True),
        sa.Column("sampled_frames", sa.Integer(), nullable=False),
        sa.Column("representative_frame_ms", sa.Integer(), nullable=False),
        sa.Column("annotated_bucket", sa.String(length=100), nullable=False),
        sa.Column("annotated_object_key", sa.String(length=700), nullable=False),
        sa.Column("media_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("recognition_job_id", name="uq_recognition_results_job"),
    )

    # --- итог занятия: новая структура на основе двух замеров ---
    # Старые агрегаты сохраняются: detected_avg переносится в detected_average,
    # оба новых счетчика получают прежнее среднее значение как legacy-оценку.
    op.add_column(
        "attendance_records",
        sa.Column("after_start_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "attendance_records",
        sa.Column("before_end_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "attendance_records",
        sa.Column("detected_average", sa.Float(), nullable=True),
    )
    op.add_column(
        "attendance_records",
        sa.Column(
            "calculation_status",
            _attendance_status_enum(create_type=False),
            nullable=True,
        ),
    )
    op.add_column(
        "attendance_records",
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.func.now(),
        ),
    )
    if is_postgres:
        op.execute(
            """
            UPDATE attendance_records
            SET after_start_count = ROUND(detected_avg)::integer,
                before_end_count = ROUND(detected_avg)::integer,
                detected_average = detected_avg,
                calculation_status = 'complete'
            WHERE calculation_status IS NULL
            """
        )
    else:
        op.execute(
            """
            UPDATE attendance_records
            SET after_start_count = CAST(ROUND(detected_avg) AS INTEGER),
                before_end_count = CAST(ROUND(detected_avg) AS INTEGER),
                detected_average = detected_avg,
                calculation_status = 'complete'
            WHERE calculation_status IS NULL
            """
        )
    with op.batch_alter_table("attendance_records") as batch:
        batch.alter_column(
            "calculation_status",
            existing_type=_attendance_status_enum(create_type=False),
            nullable=False,
        )
        batch.alter_column("detected_max", existing_type=sa.Integer(), nullable=True)
        batch.drop_column("detected_avg")
        batch.drop_column("snapshots_count")
    op.create_index(
        "ix_attendance_calculated", "attendance_records", ["calculated_at"]
    )

    # Покадровые замеры прежнего конвейера больше не используются приложением,
    # но таблица detection_snapshots оставлена для сохранения истории.

    # Индексы аналитики
    op.create_index("ix_schedule_group", "schedule", ["group_id"])
    op.create_index("ix_schedule_teacher", "schedule", ["teacher_id"])
    op.create_index("ix_schedule_discipline", "schedule", ["discipline_id"])


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index("ix_schedule_discipline", table_name="schedule")
    op.drop_index("ix_schedule_teacher", table_name="schedule")
    op.drop_index("ix_schedule_group", table_name="schedule")

    op.drop_index("ix_attendance_calculated", table_name="attendance_records")
    op.add_column(
        "attendance_records", sa.Column("detected_avg", sa.Float(), nullable=True)
    )
    op.add_column(
        "attendance_records",
        sa.Column("snapshots_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        """
        UPDATE attendance_records
        SET detected_avg = COALESCE(detected_average, after_start_count, before_end_count, 0),
            snapshots_count = CASE
                WHEN after_start_count IS NOT NULL AND before_end_count IS NOT NULL THEN 2
                WHEN after_start_count IS NOT NULL OR before_end_count IS NOT NULL THEN 1
                ELSE 0
            END,
            detected_max = COALESCE(detected_max, after_start_count, before_end_count, 0)
        """
    )
    with op.batch_alter_table("attendance_records") as batch:
        batch.alter_column("detected_avg", existing_type=sa.Float(), nullable=False)
        batch.alter_column("detected_max", existing_type=sa.Integer(), nullable=False)
        batch.drop_column("calculated_at")
        batch.drop_column("calculation_status")
        batch.drop_column("detected_average")
        batch.drop_column("before_end_count")
        batch.drop_column("after_start_count")

    op.drop_table("recognition_results")
    op.drop_index("ix_recognition_jobs_lease", table_name="recognition_jobs")
    op.drop_index("ix_recognition_jobs_claim", table_name="recognition_jobs")
    op.drop_table("recognition_jobs")
    op.drop_index("ix_camera_captures_lease", table_name="camera_captures")
    op.drop_index("ix_camera_captures_claim", table_name="camera_captures")
    op.drop_index(op.f("ix_camera_captures_camera_id"), table_name="camera_captures")
    op.drop_index(op.f("ix_camera_captures_measurement_id"), table_name="camera_captures")
    op.drop_table("camera_captures")
    op.drop_index("ix_measurements_due", table_name="measurements")
    op.drop_index(op.f("ix_measurements_session_id"), table_name="measurements")
    op.drop_table("measurements")

    op.drop_column("sessions", "created_at")

    op.add_column(
        "classrooms", sa.Column("camera_url", sa.String(length=500), nullable=True)
    )
    op.execute(
        """
        UPDATE classrooms
        SET camera_url = (
            SELECT cam.rtsp_url
            FROM classroom_cameras link
            JOIN cameras cam ON cam.id = link.camera_id
            WHERE link.classroom_id = classrooms.id
            ORDER BY link.priority
            LIMIT 1
        )
        """
    )
    with op.batch_alter_table("classrooms") as batch:
        batch.drop_column("aggregation_mode")

    op.drop_table("classroom_cameras")
    op.drop_index(op.f("ix_cameras_name"), table_name="cameras")
    op.drop_table("cameras")

    for type_name in (
        "attendance_calculation_status",
        "recognition_status",
        "capture_status",
        "measurement_status",
        "measurement_type",
        "camera_role",
        "camera_aggregation_mode",
    ):
        sa.Enum(name=type_name).drop(bind, checkfirst=True)
