from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.enums import (
    AttendanceCalculationStatus,
    CameraAggregationMode,
    CaptureStatus,
    MeasurementStatus,
    MeasurementType,
)
from app.models.schedule import SessionStatus
from app.schemas.cameras import CameraBrief
from app.schemas.schedule import ScheduleRead


class RecognitionResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    people_count: int = Field(description="Итоговое количество людей на ролике", examples=[24])
    detected_median: float = Field(description="Медиана по кадрам", examples=[24.0])
    detected_percentile_75: float = Field(description="75-й перцентиль по кадрам", examples=[25.0])
    detected_max: int = Field(description="Максимум по кадрам", examples=[26])
    average_confidence: float | None = Field(
        description="Средняя уверенность детектора", examples=[0.82]
    )
    sampled_frames: int = Field(description="Число проанализированных кадров", examples=[20])
    representative_frame_ms: int = Field(
        description="Позиция репрезентативного кадра в ролике, мс", examples=[9500]
    )
    media_expires_at: datetime | None = Field(
        description="Когда размеченный кадр будет удалён по сроку хранения"
    )


class CaptureRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera: CameraBrief
    status: CaptureStatus
    planned_at: datetime
    attempts: int
    size_bytes: int | None = Field(description="Размер записанного ролика", examples=[2148000])
    duration_ms: int | None = Field(description="Длительность ролика, мс", examples=[20000])
    error: str | None
    original_object_key: str | None = Field(exclude=True)
    result: RecognitionResultRead | None = None

    @computed_field(description="Записано ли исходное видео")
    def has_video(self) -> bool:
        return self.original_object_key is not None


class MeasurementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: MeasurementType = Field(
        description="after_start — через 15 минут после начала, before_end — за 15 минут до конца"
    )
    planned_at: datetime
    status: MeasurementStatus
    final_people_count: int | None = Field(
        description="Итог замера после объединения камер", examples=[24]
    )
    confidence: float | None = Field(description="Уверенность итога", examples=[0.82])
    aggregation_method: CameraAggregationMode
    error: str | None


class MeasurementDetail(MeasurementRead):
    captures: list[CaptureRead]


class AttendanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    expected_count: int = Field(description="Ожидаемая численность группы", examples=[28])
    after_start_count: int | None = Field(
        description="Замер после начала занятия", examples=[24]
    )
    before_end_count: int | None = Field(
        description="Замер перед концом занятия", examples=[22]
    )
    detected_average: float | None = Field(
        description="Среднее по успешным замерам", examples=[23.0]
    )
    detected_max: int | None = Field(description="Максимум по замерам", examples=[24])
    attendance_rate: float | None = Field(
        description="Доля посещаемости от 0 до 1", examples=[0.82]
    )
    calculation_status: AttendanceCalculationStatus = Field(
        description="complete — оба замера, partial — один, failed — ни одного"
    )
    calculated_at: datetime | None


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    status: SessionStatus
    started_at: datetime | None
    finished_at: datetime | None
    schedule: ScheduleRead
    attendance: AttendanceRead | None = None
    measurements: list[MeasurementRead] = Field(default_factory=list)


class SessionDetail(SessionRead):
    measurements: list[MeasurementDetail] = Field(default_factory=list)


class CaptureMediaRead(BaseModel):
    video_url: str | None = Field(
        description="Временная ссылка на исходный ролик; null, если видео недоступно"
    )
    video_unavailable_reason: str | None = Field(
        description="Почему видео недоступно", examples=["медиа удалено по сроку хранения"]
    )
    annotated_url: str | None = Field(
        description="Временная ссылка на размеченный кадр; null, если кадр недоступен"
    )
    annotated_unavailable_reason: str | None
    expires_in_seconds: int = Field(
        description="Срок действия выданных ссылок", examples=[900]
    )
