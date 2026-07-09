from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (
    CameraAggregationMode,
    CaptureStatus,
    MeasurementStatus,
    MeasurementType,
)


class Measurement(Base):
    """Один временной срез занятия: замер после начала или перед концом."""

    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[MeasurementType] = mapped_column(
        Enum(MeasurementType, name="measurement_type")
    )
    planned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[MeasurementStatus] = mapped_column(
        Enum(MeasurementStatus, name="measurement_status"),
        default=MeasurementStatus.scheduled,
    )
    final_people_count: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float)
    aggregation_method: Mapped[CameraAggregationMode] = mapped_column(
        Enum(CameraAggregationMode, name="camera_aggregation_mode"),
        default=CameraAggregationMode.single,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("session_id", "type", name="uq_measurements_session_type"),
    )

    session: Mapped["Session"] = relationship(back_populates="measurements")  # noqa: F821
    captures: Mapped[list["CameraCapture"]] = relationship(
        back_populates="measurement", cascade="all, delete-orphan"
    )


class CameraCapture(Base):
    """Задание на запись ролика с одной камеры и результат этой записи."""

    __tablename__ = "camera_captures"

    id: Mapped[int] = mapped_column(primary_key=True)
    measurement_id: Mapped[int] = mapped_column(
        ForeignKey("measurements.id", ondelete="CASCADE"), index=True
    )
    camera_id: Mapped[int] = mapped_column(
        ForeignKey("cameras.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[CaptureStatus] = mapped_column(
        Enum(CaptureStatus, name="capture_status"), default=CaptureStatus.pending
    )
    planned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int] = mapped_column(SmallInteger, default=20)
    worker_id: Mapped[str | None] = mapped_column(String(100))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    capture_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    capture_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    original_bucket: Mapped[str | None] = mapped_column(String(100))
    original_object_key: Mapped[str | None] = mapped_column(String(700))
    content_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("measurement_id", "camera_id", name="uq_camera_captures_slot"),
    )

    measurement: Mapped[Measurement] = relationship(back_populates="captures")
    camera: Mapped["Camera"] = relationship()  # noqa: F821
    recognition_job: Mapped["RecognitionJob | None"] = relationship(  # noqa: F821
        back_populates="camera_capture", uselist=False
    )

    @property
    def result(self):
        """Результат распознавания ролика, если задание уже выполнено."""
        job = self.recognition_job
        return job.result if job is not None else None
