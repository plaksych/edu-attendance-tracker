from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    course: Mapped[int] = mapped_column(Integer, default=1)
    faculty: Mapped[str | None] = mapped_column(String(200))
    # Численность группы; используется как expected_count при расчёте посещаемости
    students_count: Mapped[int] = mapped_column(Integer, default=0)

    schedule_items: Mapped[list["Schedule"]] = relationship(back_populates="group")  # noqa: F821


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200), index=True)
    email: Mapped[str | None] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (UniqueConstraint("full_name", name="uq_teachers_full_name"),)

    schedule_items: Mapped[list["Schedule"]] = relationship(back_populates="teacher")  # noqa: F821


class Discipline(Base):
    __tablename__ = "disciplines"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300), unique=True, index=True)

    schedule_items: Mapped[list["Schedule"]] = relationship(back_populates="discipline")  # noqa: F821


class Classroom(Base):
    __tablename__ = "classrooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    capacity: Mapped[int | None] = mapped_column(Integer)
    # RTSP-адрес камеры аудитории; если не задан, распознавание для аудитории недоступно
    camera_url: Mapped[str | None] = mapped_column(String(500))

    schedule_items: Mapped[list["Schedule"]] = relationship(back_populates="classroom")  # noqa: F821
