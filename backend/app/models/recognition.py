from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import RecognitionMediaType, RecognitionStatus


class RecognitionUpload(Base):
    """Входной файл для распознавания без камеры и расписания."""

    __tablename__ = "recognition_uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[RecognitionMediaType] = mapped_column(
        Enum(RecognitionMediaType, name="recognition_media_type")
    )
    original_bucket: Mapped[str] = mapped_column(String(100))
    original_object_key: Mapped[str] = mapped_column(String(700), unique=True)
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    job: Mapped["RecognitionJob | None"] = relationship(
        back_populates="upload", uselist=False, cascade="all, delete-orphan"
    )


class RecognitionJob(Base):
    """Задание распознавания записи камеры или загруженного файла."""

    __tablename__ = "recognition_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    camera_capture_id: Mapped[int | None] = mapped_column(
        ForeignKey("camera_captures.id", ondelete="CASCADE"), unique=True, nullable=True
    )
    upload_id: Mapped[int | None] = mapped_column(
        ForeignKey("recognition_uploads.id", ondelete="CASCADE"), unique=True, nullable=True
    )
    status: Mapped[RecognitionStatus] = mapped_column(
        Enum(RecognitionStatus, name="recognition_status"),
        default=RecognitionStatus.pending,
    )
    worker_id: Mapped[str | None] = mapped_column(String(100))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    model_name: Mapped[str] = mapped_column(String(100), default="yolov8n")
    model_version: Mapped[str] = mapped_column(String(100), default="8")
    sample_rate_fps: Mapped[float] = mapped_column(Float, default=1.0)
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.35)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "(camera_capture_id IS NOT NULL AND upload_id IS NULL) "
            "OR (camera_capture_id IS NULL AND upload_id IS NOT NULL)",
            name="ck_recognition_jobs_single_source",
        ),
    )

    camera_capture: Mapped["CameraCapture | None"] = relationship(  # noqa: F821
        back_populates="recognition_job"
    )
    upload: Mapped["RecognitionUpload | None"] = relationship(back_populates="job")
    result: Mapped["RecognitionResult | None"] = relationship(
        back_populates="job", uselist=False
    )


class RecognitionResult(Base):
    """Итог обработки одного ролика: агрегаты по кадрам и ключ размеченного кадра."""

    __tablename__ = "recognition_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    recognition_job_id: Mapped[int] = mapped_column(
        ForeignKey("recognition_jobs.id", ondelete="CASCADE"), unique=True
    )
    people_count: Mapped[int] = mapped_column(Integer)
    detected_median: Mapped[float] = mapped_column(Float)
    detected_percentile_75: Mapped[float] = mapped_column(Float)
    detected_max: Mapped[int] = mapped_column(Integer)
    average_confidence: Mapped[float | None] = mapped_column(Float)
    sampled_frames: Mapped[int] = mapped_column(Integer)
    representative_frame_ms: Mapped[int] = mapped_column(Integer)
    annotated_bucket: Mapped[str] = mapped_column(String(100))
    annotated_object_key: Mapped[str] = mapped_column(String(700))
    media_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    job: Mapped[RecognitionJob] = relationship(back_populates="result")
