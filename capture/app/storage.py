"""Хранилище MinIO: проверка bucket и загрузка роликов."""

import logging
import os
from uuid import UUID

from minio import Minio
import urllib3

from app.config import Settings

logger = logging.getLogger(__name__)


def original_object_key(capture_id: int, attempt: int, claim_token: str) -> str:
    """Only this attempt may write this key; DB publication selects the winner."""
    token = str(UUID(claim_token))
    if capture_id < 1 or attempt < 1:
        raise ValueError("Invalid capture or attempt")
    return f"original/captures/{capture_id}/attempts/{attempt}/{token}.mp4"


class Storage:
    """Обёртка над клиентом MinIO."""

    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.minio_bucket
        self._client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
            http_client=urllib3.PoolManager(
                timeout=urllib3.Timeout(connect=5, read=15), retries=False
            ),
        )

    @property
    def bucket(self) -> str:
        return self._bucket

    def check_bucket(self) -> None:
        """Проверяет наличие bucket; создаёт его backend, а не воркер."""
        try:
            if not self._client.bucket_exists(self._bucket):
                logger.warning(
                    "Bucket %s не найден; его должен создать backend", self._bucket
                )
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
