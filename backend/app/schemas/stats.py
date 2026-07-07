from __future__ import annotations

from datetime import date as Date

from pydantic import BaseModel, Field


class SummaryStats(BaseModel):
    groups: int = Field(description="Количество групп", examples=[12])
    teachers: int = Field(description="Количество преподавателей", examples=[24])
    disciplines: int = Field(description="Количество дисциплин", examples=[18])
    classrooms: int = Field(description="Количество аудиторий", examples=[10])
    cameras: int = Field(description="Количество камер", examples=[14])
    sessions_total: int = Field(description="Всего сформированных занятий", examples=[120])
    sessions_today: int = Field(description="Занятий на текущую дату", examples=[8])
    sessions_finished: int = Field(description="Завершённых занятий", examples=[56])
    avg_attendance_rate: float | None = Field(
        description="Средняя посещаемость по завершённым занятиям",
        examples=[0.81],
    )
    records_complete: int = Field(
        description="Занятий с двумя успешными замерами", examples=[48]
    )
    records_partial: int = Field(
        description="Занятий с одним успешным замером", examples=[6]
    )
    records_failed: int = Field(
        description="Занятий без успешных замеров", examples=[2]
    )


class BreakdownItem(BaseModel):
    """Строка разбивки: посещаемость в разрезе группы/дисциплины/преподавателя."""

    id: int = Field(description="ID сущности в разбивке", examples=[1])
    name: str = Field(description="Название сущности в разбивке", examples=["Базы данных"])
    sessions: int = Field(description="Количество завершённых занятий", examples=[14])
    avg_rate: float | None = Field(description="Средняя посещаемость", examples=[0.83])
    avg_detected: float | None = Field(
        description="Среднее число найденных людей",
        examples=[23.4],
    )


class EntityStats(BaseModel):
    id: int = Field(description="ID выбранной сущности", examples=[1])
    name: str = Field(description="Название выбранной сущности", examples=["ИВТ-21"])
    sessions_finished: int = Field(description="Количество завершённых занятий", examples=[32])
    avg_rate: float | None = Field(description="Средняя посещаемость", examples=[0.79])
    avg_detected: float | None = Field(
        description="Среднее число найденных людей",
        examples=[22.1],
    )
    records_complete: int = Field(
        description="Занятий с двумя успешными замерами", examples=[28]
    )
    records_partial: int = Field(
        description="Занятий с одним успешным замером", examples=[3]
    )
    records_failed: int = Field(
        description="Занятий без успешных замеров", examples=[1]
    )
    breakdown: list[BreakdownItem] = Field(description="Разбивка по связанным сущностям")


class TimelinePoint(BaseModel):
    date: Date = Field(description="Дата занятий", examples=["2026-07-04"])
    avg_rate: float | None = Field(description="Средняя посещаемость за дату", examples=[0.86])
    avg_detected: float | None = Field(
        description="Среднее число найденных людей за дату",
        examples=[24.2],
    )
    expected: int | None = Field(description="Ожидаемая численность группы", examples=[28])


class GroupTimeline(BaseModel):
    group_id: int = Field(description="ID группы", examples=[1])
    group_name: str = Field(description="Название группы", examples=["ИВТ-21"])
    points: list[TimelinePoint] = Field(description="Точки временного ряда")
