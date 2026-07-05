from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import AttendanceCalculationStatus


class AttendanceRecord(Base):
    """Итог занятия, собранный из двух замеров."""

    __tablename__ = "attendance_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), unique=True
    )
    expected_count: Mapped[int] = mapped_column(Integer)
    after_start_count: Mapped[int | None] = mapped_column(Integer)
    before_end_count: Mapped[int | None] = mapped_column(Integer)
    detected_average: Mapped[float | None] = mapped_column(Float)
    detected_max: Mapped[int | None] = mapped_column(Integer)
    attendance_rate: Mapped[float | None] = mapped_column(Float)
    calculation_status: Mapped[AttendanceCalculationStatus] = mapped_column(
        Enum(AttendanceCalculationStatus, name="attendance_calculation_status")
    )
    calculated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    session: Mapped["Session"] = relationship(back_populates="attendance")  # noqa: F821
