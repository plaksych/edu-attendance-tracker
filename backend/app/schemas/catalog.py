from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CameraAggregationMode
from app.schemas.cameras import ClassroomCameraRead


class GroupBase(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=50,
        description="Название учебной группы",
        examples=["ИВТ-21"],
    )
    course: int = Field(
        default=1,
        ge=1,
        le=6,
        description="Курс обучения",
        examples=[2],
    )
    faculty: str | None = Field(
        default=None,
        description="Факультет или институт",
        examples=["Институт компьютерных наук"],
    )
    students_count: int = Field(
        default=0,
        ge=0,
        description="Численность группы для расчёта процента посещаемости",
        examples=[28],
    )


class GroupCreate(GroupBase):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "ИВТ-21",
                "course": 2,
                "faculty": "Институт компьютерных наук",
                "students_count": 28,
            }
        }
    )


class GroupUpdate(BaseModel):
    course: int | None = Field(default=None, ge=1, le=6)
    faculty: str | None = None
    students_count: int | None = Field(
        default=None,
        ge=0,
        description="Численность группы; влияет на расчёт attendance_rate",
    )


class GroupRead(GroupBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class TeacherBase(BaseModel):
    full_name: str = Field(
        min_length=1,
        max_length=200,
        description="ФИО преподавателя",
        examples=["Иванов Иван Иванович"],
    )
    email: str | None = Field(
        default=None,
        description="Контактный email преподавателя",
        examples=["ivanov@example.edu"],
    )
    department: str | None = Field(
        default=None,
        description="Кафедра или подразделение",
        examples=["Кафедра информационных систем"],
    )


class TeacherCreate(TeacherBase):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "full_name": "Иванов Иван Иванович",
                "email": "ivanov@example.edu",
                "department": "Кафедра информационных систем",
            }
        }
    )


class TeacherRead(TeacherBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class DisciplineBase(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=300,
        description="Название дисциплины",
        examples=["Базы данных"],
    )


class DisciplineCreate(DisciplineBase):
    model_config = ConfigDict(json_schema_extra={"example": {"name": "Базы данных"}})


class DisciplineRead(DisciplineBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class ClassroomBase(BaseModel):
    number: str = Field(
        min_length=1,
        max_length=50,
        description="Номер или название аудитории",
        examples=["302"],
    )
    capacity: int | None = Field(
        default=None,
        ge=1,
        description="Вместимость аудитории",
        examples=[40],
    )
    aggregation_mode: CameraAggregationMode = Field(
        default=CameraAggregationMode.single,
        description=(
            "Как объединять результаты камер: single — одна камера, "
            "maximum — пересекающиеся зоны, sum — непересекающиеся зоны, "
            "primary_backup — основная и резервная"
        ),
    )


class ClassroomCreate(ClassroomBase):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"number": "302", "capacity": 40, "aggregation_mode": "single"}
        }
    )


class ClassroomUpdate(BaseModel):
    capacity: int | None = Field(default=None, ge=1)
    aggregation_mode: CameraAggregationMode | None = None


class ClassroomRead(ClassroomBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    cameras: list[ClassroomCameraRead] = Field(
        default_factory=list,
        validation_alias="camera_links",
        description="Камеры аудитории с ролями и приоритетами",
    )
