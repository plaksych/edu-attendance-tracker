"""Хранилище MinIO: скачивание исходного видео и загрузка размеченных кадров."""

import logging

from minio import Minio

from app.config import settings

logger = logging.getLogger(__name__)


def annotated_object_key(session_id: int, measurement_id: int, camera_id: int) -> str:
    """Ключ размеченного кадра; повторная попытка перезаписывает тот же объект."""
    return (
        f"annotated/sessions/{session_id}/measurements/{measurement_id}"
        f"/cameras/{camera_id}.jpg"
    )


def upload_annotated_object_key(upload_id: int) -> str:
    """Ключ размеченного кадра для файла, загруженного без камеры."""
    return f"annotated/uploads/{upload_id}.jpg"


class ObjectStorage:
    def __init__(self) -> None:
        self._client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    def check_bucket(self) -> None:
        """Bucket создаёт backend; при его отсутствии только предупреждаем."""
        try:
            if not self._client.bucket_exists(settings.minio_bucket):
                logger.warning(
                    "Bucket %s не найден — ожидается, что его создаст backend",
                    settings.minio_bucket,
                )
        except Exception:
            logger.warning(
                "Не удалось проверить bucket %s", settings.minio_bucket, exc_info=True
            )

    def download(self, bucket: str | None, object_key: str, file_path: str) -> None:
        self._client.fget_object(bucket or settings.minio_bucket, object_key, file_path)

    def upload(self, object_key: str, file_path: str, content_type: str) -> None:
        self._client.fput_object(
            settings.minio_bucket, object_key, file_path, content_type=content_type
        )
