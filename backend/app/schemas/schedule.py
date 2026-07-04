from __future__ import annotations

from datetime import date as Date, time

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.schedule import WeekType
from app.schemas.catalog import ClassroomRead, DisciplineRead, GroupRead, TeacherRead


class ScheduleCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "group_id": 1,
                "teacher_id": 1,
                "discipline_id": 1,
                "classroom_id": 1,
                "weekday": 1,
                "starts_at": "09:00:00",
                "ends_at": "10:30:00",
                "week_type": "every",
                "lesson_type": "лек.",
            }
        }
    )

    group_id: int = Field(description="ID учебной группы", examples=[1])
    teacher_id: int | None = Field(
        default=None,
        description="ID преподавателя. Может отсутствовать в исходном расписании.",
        examples=[1],
    )
    discipline_id: int = Field(description="ID дисциплины", examples=[1])
    classroom_id: int | None = Field(
        default=None,
        description="ID аудитории. Если аудитория не указана, запуск камеры невозможен.",
        examples=[1],
    )
    weekday: int = Field(
        ge=1,
        le=7,
        description="ISO-день недели: 1 — понедельник, 7 — воскресенье",
        examples=[1],
    )
    starts_at: time = Field(description="Время начала занятия", examples=["09:00:00"])
    ends_at: time = Field(description="Время окончания занятия", examples=["10:30:00"])
    week_type: WeekType = Field(
        default=WeekType.every,
        description="Тип недели: каждую неделю, белая или зелёная",
    )
    lesson_type: str | None = Field(
        default=None,
        description="Тип занятия из расписания: лек., пр., лаб.",
        examples=["лек."],
    )

    @model_validator(mode="after")
    def check_time_range(self) -> "ScheduleCreate":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at должно быть позже starts_at")
        return self


class ScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    weekday: int
    starts_at: time
    ends_at: time
    week_type: WeekType
    lesson_type: str | None
    group: GroupRead
    teacher: TeacherRead | None
    discipline: DisciplineRead
    classroom: ClassroomRead | None


class ScheduleImportResult(BaseModel):
    created: int = Field(description="Количество созданных записей расписания", examples=[42])
    skipped: int = Field(description="Количество пропущенных дублей", examples=[3])
    errors: list[str] = Field(
        description="Ошибки по строкам или ячейкам, которые не удалось импортировать",
        examples=[["Строка 8: не указана дисциплина"]],
    )


class WeekTypeRead(BaseModel):
    date: Date = Field(description="Дата проверки", examples=["2026-02-09"])
    week_type: WeekType = Field(description="Тип учебной недели")
