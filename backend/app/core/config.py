from datetime import date
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Educational Attendance Tracker"
    api_v1_prefix: str = "/api/v1"

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

    # --- MinIO ---
    minio_endpoint: str = "localhost:9000"
    # Адрес MinIO, доступный из браузера; на нём подписываются presigned URL.
    # Если не задан, используется minio_endpoint.
    minio_public_endpoint: str | None = None
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "attendance-clips"
    minio_secure: bool = False
    presign_expiry_seconds: int = 900

    # Сроки хранения медиа; должны совпадать с lifecycle policy бакета
    original_retention_days: int = 30
    annotated_retention_days: int = 90
    recognition_upload_max_size_mb: int = 512
    recognition_model_name: str = "yolov8n"
    recognition_model_version: str = "8"

    # --- Measurement Scheduler ---
    scheduler_enabled: bool = True
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

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
