from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Куда отправлять результаты распознавания
    backend_url: str = "http://localhost:8000"

    # Интервал между замерами, сек. На CPU с yolov8n комфортно от 20 сек
    snapshot_interval: int = 30

    # Веса модели: файл или имя из зоопарка ultralytics (скачается автоматически)
    model_path: str = "yolov8n.pt"

    # Порог уверенности для класса person
    confidence_threshold: float = 0.35

    # Каталог для кадров; общий volume с backend
    snapshot_dir: str = "./media"

    # Сколько секунд ждать переподключения к потоку после обрыва
    reconnect_delay: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
