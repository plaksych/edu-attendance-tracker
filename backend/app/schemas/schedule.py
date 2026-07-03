from datetime import date, time

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.schedule import WeekType
from app.schemas.catalog import ClassroomRead, DisciplineRead, GroupRead, TeacherRead


class ScheduleCreate(BaseModel):
    group_id: int
    teacher_id: int | None = None
    discipline_id: int
    classroom_id: int | None = None
    weekday: int = Field(ge=1, le=7, description="ISO: 1 — понедельник, 7 — воскресенье")
    starts_at: time
    ends_at: time
    week_type: WeekType = WeekType.every
    lesson_type: str | None = None

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
    created: int
    skipped: int
    errors: list[str]


class WeekTypeRead(BaseModel):
    date: date
    week_type: WeekType
