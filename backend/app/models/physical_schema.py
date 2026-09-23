"""Indexes and preserved legacy storage must remain visible to Alembic comparisons."""
from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Table, text
from app.core.database import Base

Table("detection_snapshots", Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("session_id", Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("captured_at", DateTime(timezone=True), nullable=False),
    Column("person_count", Integer, nullable=False),
    Column("confidence", Float), Column("frame_path", String(500)))

for name, table, columns, predicate in [
    ("ix_groups_name", "groups", ["name"], None),
    ("ix_disciplines_name", "disciplines", ["name"], None),
    ("ix_classrooms_number", "classrooms", ["number"], None),
    ("ix_cameras_name", "cameras", ["name"], None),
    ("ix_schedule_group", "schedule", ["group_id"], None),
    ("ix_schedule_teacher", "schedule", ["teacher_id"], None),
    ("ix_schedule_discipline", "schedule", ["discipline_id"], None),
    ("ix_attendance_calculated", "attendance_records", ["calculated_at"], None),
    ("ix_measurements_due", "measurements", ["planned_at"], "status = 'scheduled'"),
    ("ix_camera_captures_claim", "camera_captures", ["planned_at", "id"], "status = 'pending'"),
    ("ix_camera_captures_lease", "camera_captures", ["lease_until"], "status IN ('claimed', 'recording', 'uploading')"),
    ("ix_recognition_jobs_claim", "recognition_jobs", ["created_at", "id"], "status = 'pending'"),
    ("ix_recognition_jobs_lease", "recognition_jobs", ["lease_until"], "status = 'processing'"),
    ("ix_recognition_jobs_claim_token", "recognition_jobs", ["claim_token"], None),
    ("ix_camera_captures_claim_token", "camera_captures", ["claim_token"], None),
    ("ix_recognition_jobs_upload_id", "recognition_jobs", ["upload_id"], None),
    ("ix_recognition_uploads_created", "recognition_uploads", ["created_at", "id"], None),
]:
    options = {"postgresql_where": text(predicate)} if predicate else {}
    Index(name, *(Base.metadata.tables[table].c[c] for c in columns), **options)
