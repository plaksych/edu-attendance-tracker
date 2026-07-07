from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.schedule import SessionStatus
from app.schemas.schedule import ScheduleRead


class SnapshotCreate(BaseModel):
    captured_at: datetime
    person_count: int = Field(ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)
    frame_path: str | None = None


class SnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    captured_at: datetime
    person_count: int
    confidence: float | None
    frame_path: str | None


class AttendanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    expected_count: int
    detected_avg: float
    detected_max: int
    snapshots_count: int
    attendance_rate: float | None


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
