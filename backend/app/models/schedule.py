import enum
from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, SmallInteger, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SessionStatus(str, enum.Enum):
    scheduled = "scheduled"
    in_progress = "in_progress"
    finished = "finished"


class WeekType(str, enum.Enum):
    """Чередование недель: пара идёт каждую неделю, только по белым или только по зелёным."""

    every = "every"
    white = "white"
    green = "green"


class Schedule(Base):
    __tablename__ = "schedule"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    # Преподаватель и аудитория могут отсутствовать в исходном расписании
    # (иностранный язык, физкультура и т.п.)
    teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("teachers.id", ondelete="CASCADE"), nullable=True
    )
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id", ondelete="CASCADE"))
    classroom_id: Mapped[int | None] = mapped_column(
        ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=True
    )
    # День недели по ISO: 1 — понедельник, 7 — воскресенье
    weekday: Mapped[int] = mapped_column(SmallInteger)
    starts_at: Mapped[time] = mapped_column(Time)
    ends_at: Mapped[time] = mapped_column(Time)
    week_type: Mapped[WeekType] = mapped_column(
        Enum(WeekType, name="week_type"), default=WeekType.every
    )
    # Вид занятия из расписания: лек. / пр. / лаб.
    lesson_type: Mapped[str | None] = mapped_column(String(20))

    __table_args__ = (
        UniqueConstraint(
            "group_id", "weekday", "starts_at", "week_type", name="uq_schedule_group_slot"
        ),
    )

    group: Mapped["Group"] = relationship(back_populates="schedule_items")  # noqa: F821
    teacher: Mapped[Optional["Teacher"]] = relationship(back_populates="schedule_items")  # noqa: F821
    discipline: Mapped["Discipline"] = relationship(back_populates="schedule_items")  # noqa: F821
    classroom: Mapped[Optional["Classroom"]] = relationship(back_populates="schedule_items")  # noqa: F821
    sessions: Mapped[list["Session"]] = relationship(back_populates="schedule")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedule.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status"), default=SessionStatus.scheduled
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("schedule_id", "date", name="uq_sessions_schedule_date"),
    )

    schedule: Mapped["Schedule"] = relationship(back_populates="sessions")
    snapshots: Mapped[list["DetectionSnapshot"]] = relationship(  # noqa: F821
        back_populates="session", cascade="all, delete-orphan"
    )
    attendance: Mapped[Optional["AttendanceRecord"]] = relationship(  # noqa: F821
        back_populates="session", cascade="all, delete-orphan", uselist=False
    )
