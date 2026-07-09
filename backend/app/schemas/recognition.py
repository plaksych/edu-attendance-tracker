from __future__ import annotations

from datetime import datetime

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
    sample_rate_fps: float = Field(description="Частота выборки кадров у видео", examples=[1.0])
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
    filename: str
    media_type: RecognitionMediaType
    content_type: str
    size_bytes: int
    created_at: datetime
    job: RecognitionUploadJobRead


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
