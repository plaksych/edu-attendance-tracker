"""Работа с MinIO: клиенты, инициализация бакета, lifecycle-политика.

Backend не загружает медиа сам — этим занимаются capture- и recognition-воркеры.
Здесь только выдача presigned URL для frontend и создание бакета при старте.
"""

import logging
from functools import lru_cache

from minio import Minio
from minio.commonconfig import ENABLED, Filter
from minio.lifecycleconfig import Expiration, LifecycleConfig, Rule

from app.core.config import settings

logger = logging.getLogger(__name__)

ORIGINAL_PREFIX = "original/"
ANNOTATED_PREFIX = "annotated/"


@lru_cache
def get_client() -> Minio:
    """Клиент для служебных операций внутри сети."""
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


@lru_cache
def get_presign_client() -> Minio:
    """Клиент для подписи URL: подпись привязана к хосту,
    поэтому используется адрес, доступный из браузера."""
    endpoint = settings.minio_public_endpoint or settings.minio_endpoint
    return Minio(
        endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def ensure_bucket() -> None:
    """Создаёт закрытый бакет и настраивает автоудаление медиа по сроку хранения."""
    client = get_client()
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)
        logger.info("Создан бакет %s", settings.minio_bucket)

    lifecycle = LifecycleConfig(
        [
            Rule(
                ENABLED,
                rule_filter=Filter(prefix=ORIGINAL_PREFIX),
                rule_id="expire-original",
                expiration=Expiration(days=settings.original_retention_days),
            ),
            Rule(
                ENABLED,
                rule_filter=Filter(prefix=ANNOTATED_PREFIX),
                rule_id="expire-annotated",
                expiration=Expiration(days=settings.annotated_retention_days),
            ),
        ]
    )
    client.set_bucket_lifecycle(settings.minio_bucket, lifecycle)
