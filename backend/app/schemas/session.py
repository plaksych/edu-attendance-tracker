from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.schedule import SessionStatus
from app.schemas.schedule import ScheduleRead


class SnapshotCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "captured_at": "2026-07-04T09:15:00Z",
                "person_count": 24,
                "confidence": 0.82,
                "frame_path": "12/20260704_091500.jpg",
            }
        }
    )

    captured_at: datetime = Field(description="Время снятия кадра")
    person_count: int = Field(ge=0, description="Количество найденных людей", examples=[24])
    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Средняя уверенность детектора по найденным людям",
        examples=[0.82],
    )
    frame_path: str | None = Field(
        default=None,
        description="Путь к кадру относительно media-каталога backend",
        examples=["12/20260704_091500.jpg"],
    )


class SnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    captured_at: datetime
    person_count: int
    confidence: float | None
    frame_path: str | None


class AttendanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    expected_count: int = Field(description="Ожидаемая численность группы", examples=[28])
    detected_avg: float = Field(description="Среднее число людей по замерам", examples=[24.5])
    detected_max: int = Field(description="Максимальное число людей на одном кадре", examples=[27])
    snapshots_count: int = Field(description="Количество принятых замеров", examples=[6])
    attendance_rate: float | None = Field(
        description="Доля посещаемости от 0 до 1",
        examples=[0.875],
    )


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    status: SessionStatus
    started_at: datetime | None
    finished_at: datetime | None
    schedule: ScheduleRead
    attendance: AttendanceRead | None = None


class SessionWithSnapshots(SessionRead):
    snapshots: list[SnapshotRead]
