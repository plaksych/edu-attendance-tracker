import os
import socket
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_worker_id() -> str:
    return f"{socket.gethostname()}-{os.getpid()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://attendance:attendance@localhost:5432/attendance"

    # Идентификатор воркера в очереди уникален для процесса и контейнера
    worker_id: str = Field(default_factory=_default_worker_id)

    poll_interval_seconds: int = 5
    lease_minutes: int = 30
    heartbeat_interval_seconds: int = 60
    max_attempts: int = 3
    retry_delay_seconds: int = 120

    # Веса модели: файл или имя из зоопарка ultralytics (скачается автоматически)
    model_path: str = "yolov8n.pt"
    inference_image_size: int = 960
    inference_iou_threshold: float = 0.5
    inference_max_detections: int = 300
    max_sampled_frames: int = Field(default=180, ge=1)
    evaluation_tolerance_people: int = Field(default=1, ge=0)

    # Сколько дней доступен размеченный кадр
    annotated_retention_days: int = 90
    jpeg_quality: int = 85

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "attendance-clips"
    minio_secure: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
