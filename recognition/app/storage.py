"""Хранилище MinIO: скачивание исходного видео и загрузка размеченных кадров."""

import logging
import time

import urllib3

from minio import Minio

from app.config import settings

logger = logging.getLogger(__name__)


class ObjectStorage:
    def __init__(self) -> None:
        self._client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
            http_client=urllib3.PoolManager(
                timeout=urllib3.Timeout(connect=5, read=15), retries=False
            ),
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
        response = self._client.get_object(bucket or settings.minio_bucket, object_key)
        total = 0
        deadline = time.monotonic() + min(60, settings.job_timeout_seconds)
        try:
            with open(file_path, "xb") as destination:
                for chunk in response.stream(1024 * 1024):
                    total += len(chunk)
                    if (
                        total > settings.max_file_size_mb * 1024 * 1024
                        or time.monotonic() > deadline
                    ):
                        raise ValueError("source_download_limit")
                    destination.write(chunk)
        finally:
            response.close()
            response.release_conn()

    def upload(self, object_key: str, file_path: str, content_type: str) -> None:
        self._client.fput_object(
            settings.minio_bucket, object_key, file_path, content_type=content_type
        )
