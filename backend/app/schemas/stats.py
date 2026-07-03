from datetime import date

from pydantic import BaseModel


class SummaryStats(BaseModel):
    groups: int
    teachers: int
    disciplines: int
    classrooms: int
    sessions_total: int
    sessions_today: int
    sessions_finished: int
    avg_attendance_rate: float | None


class BreakdownItem(BaseModel):
    """Строка разбивки: посещаемость в разрезе группы/дисциплины/преподавателя."""

    id: int
    name: str
    sessions: int
    avg_rate: float | None
    avg_detected: float | None


class EntityStats(BaseModel):
    id: int
    name: str
    sessions_finished: int
    avg_rate: float | None
    avg_detected: float | None
    breakdown: list[BreakdownItem]


class TimelinePoint(BaseModel):
    date: date
    avg_rate: float | None
    detected_avg: float | None
    expected: int | None


class GroupTimeline(BaseModel):
    group_id: int
    group_name: str
    points: list[TimelinePoint]
