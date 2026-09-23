from datetime import date
from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import model_validator
from sqlalchemy.engine import URL
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Educational Attendance Tracker"
    api_v1_prefix: str = "/api/v1"
    environment: Literal["development", "test", "demo", "production"] = "development"
    session_cookie_name: str = "attendance_session"
    session_secure: bool = True
    session_ttl_seconds: int = 28800
    trusted_hosts: str = "localhost,127.0.0.1,testserver"
    login_limit: int = 8
    login_window_seconds: int = 900
    camera_encryption_key: str = ""
    camera_allowed_cidrs: str = ""

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "attendance"
    db_user: str = "attendance"
    db_password: str = "attendance"
    database_url: str | None = None

    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Часовой пояс расписания: время пар в БД хранится как локальное
    timezone: str = "Europe/Moscow"

    # Понедельник первой учебной недели семестра; первая неделя считается белой.
    # Если в вузе семестр начался с зелёной, сдвиньте дату на неделю назад.
    semester_start: date = date(2026, 2, 9)
    semester_end: date | None = None

    # --- MinIO ---
    minio_endpoint: str = "localhost:9000"
    # Адрес MinIO, доступный из браузера; на нём подписываются presigned URL.
    # Если не задан, используется minio_endpoint.
    minio_public_endpoint: str | None = None
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "attendance-clips"
    minio_secure: bool = False
    minio_public_secure: bool = True
    presign_expiry_seconds: int = 120

    # Сроки хранения медиа; должны совпадать с lifecycle policy бакета
    original_retention_days: int = 30
    annotated_retention_days: int = 90
    recognition_upload_max_size_mb: int = 100
    recognition_pending_per_user: int = 20
    upload_max_pixels: int = 16000000
    upload_max_duration_seconds: int = 120
    upload_max_video_dimension: int = 3840
    upload_probe_timeout_seconds: int = 10
    recognition_model_name: str = "yolov8n"
    recognition_model_version: str = "8"

    # --- Measurement Scheduler ---
    scheduler_enabled: bool = False
    scheduler_interval_seconds: int = 30
    # На сколько дней вперёд создаются занятия и замеры
    schedule_horizon_days: int = 14
    # Отступ замеров от границ занятия: после начала и до конца
    measurement_offset_minutes: int = 15
    capture_duration_seconds: int = 20
    # Через сколько минут после planned_at незабранное задание записи считается потерянным
    capture_pending_timeout_minutes: int = 10
    # Максимум попыток для заданий записи и распознавания (согласовано с воркерами)
    queue_max_attempts: int = 3
    # Порог уверенности, ниже которого в режиме primary_backup берётся резервная камера
    backup_confidence_threshold: float = 0.3

    @model_validator(mode="after")
    def production_boundaries(self):
        ZoneInfo(self.timezone)
        if self.semester_end is not None and self.semester_end < self.semester_start:
            raise ValueError("Semester end must not precede its start")
        if self.environment == "production":
            if self.semester_end is None:
                raise ValueError("Production requires an explicit SEMESTER_END")
            if not self.session_secure or not self.minio_public_secure:
                raise ValueError("Production requires Secure cookies and HTTPS media URLs")
            if self.db_password == "attendance" and not self.database_url:
                raise ValueError("Production database credentials must be configured")
            if self.minio_access_key == "minioadmin" or self.minio_secret_key == "minioadmin":
                raise ValueError("Runtime must use a scoped storage account")
            if "*" in self.trusted_hosts or "*" in self.cors_origins:
                raise ValueError("Explicit production hosts and origins are required")
        return self

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        return URL.create("postgresql+psycopg2", username=self.db_user,
                          password=self.db_password, host=self.db_host,
                          port=self.db_port, database=self.db_name).render_as_string(hide_password=False)

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
