"""Хранилище MinIO: проверка bucket и загрузка роликов."""

import logging
import os

from minio import Minio

from app.config import Settings

logger = logging.getLogger(__name__)


def original_object_key(session_id: int, measurement_id: int, camera_id: int) -> str:
    """Ключ исходного ролика; стабилен, повторная попытка перезаписывает объект."""
    return (
        f"original/sessions/{session_id}/measurements/{measurement_id}"
        f"/cameras/{camera_id}.mp4"
    )


class Storage:
    """Обёртка над клиентом MinIO."""

    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.minio_bucket
        self._client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    @property
    def bucket(self) -> str:
        return self._bucket

    def check_bucket(self) -> None:
        """Проверяет наличие bucket; создаёт его backend, а не воркер."""
        try:
            if not self._client.bucket_exists(self._bucket):
                logger.warning("Bucket %s не найден; его должен создать backend", self._bucket)
        except Exception as exc:  # noqa: BLE001 — недоступность MinIO не должна ронять старт
            logger.warning("Не удалось проверить bucket %s: %s", self._bucket, exc)

    def upload_video(self, local_path: str, object_key: str) -> int:
        """Загружает ролик как video/mp4 и возвращает его размер в байтах."""
        size_bytes = os.path.getsize(local_path)
        self._client.fput_object(
            self._bucket,
            object_key,
            local_path,
            content_type="video/mp4",
        )
        return size_bytes
