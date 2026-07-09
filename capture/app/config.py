"""Настройки Capture Manager."""

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

    # Группа камер, которую обслуживает этот экземпляр воркера
    capture_group: str = "default"
    worker_id: str = Field(default_factory=_default_worker_id)

    poll_interval_seconds: int = 5
    claim_lookahead_seconds: int = 10
    claim_batch_size: int = 50
    lease_seconds: int = 300
    heartbeat_interval_seconds: int = 60
    max_attempts: int = 3
    retry_delay_seconds: int = 60
    ffmpeg_extra_timeout_seconds: int = 30

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "attendance-clips"
    minio_secure: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
