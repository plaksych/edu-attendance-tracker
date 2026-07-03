from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DetectionSnapshot(Base):
    """Сырой замер от recognition-сервиса: сколько человек видно на кадре."""

    __tablename__ = "detection_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    person_count: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float)
    # Путь к кадру относительно media-каталога, например "42/20260703_101500.jpg"
    frame_path: Mapped[str | None] = mapped_column(String(500))

    session: Mapped["Session"] = relationship(back_populates="snapshots")  # noqa: F821


class AttendanceRecord(Base):
    """Агрегированная посещаемость по завершённому занятию."""

    __tablename__ = "attendance_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), unique=True
    )
    expected_count: Mapped[int] = mapped_column(Integer)
    detected_avg: Mapped[float] = mapped_column(Float)
    detected_max: Mapped[int] = mapped_column(Integer)
    snapshots_count: Mapped[int] = mapped_column(Integer)
    # Доля присутствовавших от численности группы, 0..1
    attendance_rate: Mapped[float | None] = mapped_column(Float)

    session: Mapped["Session"] = relationship(back_populates="attendance")  # noqa: F821
