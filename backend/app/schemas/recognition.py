from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RecognitionMediaType, RecognitionStatus
from app.schemas.session import RecognitionResultRead


class RecognitionUploadJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: RecognitionStatus
    attempts: int
    model_name: str
    model_version: str
    sample_rate_fps: float = Field(
        description="Частота выборки кадров у видео", examples=[1.0]
    )
    confidence_threshold: float = Field(
        description="Минимальная уверенность детектора", examples=[0.35]
    )
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    result: RecognitionResultRead | None = None


class RecognitionUploadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int | None = None
    measurement_id: int | None = None
    provenance: str = "server_inference"
    filename: str
    media_type: RecognitionMediaType
    content_type: str
    size_bytes: int
    label: str | None = Field(description="Краткое название проверочного материала")
    reference_people_count: int | None = Field(
        description="Ручной эталон для расчёта ошибки", examples=[8]
    )
    created_at: datetime
    job: RecognitionUploadJobRead


class RecognitionEvaluationSummary(BaseModel):
    checked_materials: int = Field(description="Число материалов с ручным эталоном")
    within_tolerance_count: int = Field(
        description="Число результатов в допустимой ошибке"
    )
    mean_absolute_error: float | None = Field(description="Средняя абсолютная ошибка")
    median_absolute_error: float | None = Field(
        description="Медианная абсолютная ошибка"
    )
    max_absolute_error: int | None = Field(description="Максимальная абсолютная ошибка")
    mean_relative_error: float | None = Field(
        description="Средняя относительная ошибка"
    )


class RecognitionUploadMediaRead(BaseModel):
    source_url: str | None = Field(
        description="Временная ссылка на загруженный исходный файл"
    )
    source_unavailable_reason: str | None
    annotated_url: str | None = Field(
        description="Временная ссылка на размеченный кадр"
    )
    annotated_unavailable_reason: str | None
    expires_in_seconds: int = Field(
        description="Срок действия выданных ссылок", examples=[900]
    )


class ParameterRange(BaseModel):
    min: float
    max: float


class RecognitionCapabilities(BaseModel):
    profile: Literal["server_inference"]
    formats: list[str]
    max_size_bytes: int
    max_pixels: int
    max_duration_seconds: float
    max_video_dimension: int
    sample_rate_fps: ParameterRange
    confidence: ParameterRange


class CorrectionCreated(BaseModel):
    id: int
    job_id: int
    people_count: int


class CorrectionRead(CorrectionCreated):
    actor_id: int | None
    reason: str
    created_at: datetime


class RecognitionHistoryRead(BaseModel):
    jobs: list[RecognitionUploadJobRead]
    corrections: list[CorrectionRead]
