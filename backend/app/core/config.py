from datetime import date
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Educational Attendance Tracker"
    api_v1_prefix: str = "/api/v1"

    # Понедельник первой учебной недели семестра; первая неделя считается белой.
    # Если в вузе семестр начался с зелёной, сдвиньте дату на неделю назад.
    semester_start: date = date(2026, 2, 9)

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "attendance"
    db_user: str = "attendance"
    db_password: str = "attendance"
    database_url: str | None = None

    # Адрес recognition-сервиса, куда backend отправляет команды start/stop потока
    recognition_url: str = "http://localhost:8001"

    # Каталог с кадрами; общий volume с recognition-сервисом
    media_dir: str = "./media"

    cors_origins: str = "http://localhost:3000,http://localhost:5173"

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
