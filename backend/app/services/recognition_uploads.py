"""Входные файлы распознавания: проверка, MinIO и временные ссылки."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import settings
from app.core.object_storage import get_client, get_presign_client
from app.models import RecognitionMediaType, RecognitionUpload

SOURCE_UNAVAILABLE = "исходный файл удалён по сроку хранения"
ANNOTATED_UNAVAILABLE = "размеченный кадр ещё не сформирован"

_MEDIA_BY_EXTENSION = {
    ".avi": (RecognitionMediaType.video, "video/x-msvideo"),
    ".jpeg": (RecognitionMediaType.image, "image/jpeg"),
    ".jpg": (RecognitionMediaType.image, "image/jpeg"),
    ".mov": (RecognitionMediaType.video, "video/quicktime"),
    ".mp4": (RecognitionMediaType.video, "video/mp4"),
    ".png": (RecognitionMediaType.image, "image/png"),
    ".webm": (RecognitionMediaType.video, "video/webm"),
    ".webp": (RecognitionMediaType.image, "image/webp"),
}
_MEDIA_BY_CONTENT_TYPE = {
    content_type: media_type
    for _suffix, (media_type, content_type) in _MEDIA_BY_EXTENSION.items()
}


class RecognitionUploadError(ValueError):
    """Ошибка, которую можно показать пользователю endpoint-а загрузки."""


@dataclass(frozen=True)
class UploadDescriptor:
    filename: str
    suffix: str
    media_type: RecognitionMediaType
    content_type: str
    size_bytes: int


def describe_upload(file: UploadFile) -> UploadDescriptor:
    filename = Path(file.filename or "").name
    suffix = Path(filename).suffix.lower()
    extension_info = _MEDIA_BY_EXTENSION.get(suffix)
    if extension_info is None:
        allowed = ", ".join(sorted(_MEDIA_BY_EXTENSION))
        raise RecognitionUploadError(f"Поддерживаются файлы: {allowed}")

    media_type, default_content_type = extension_info
    declared_type = (file.content_type or "").lower()
    declared_media_type = _MEDIA_BY_CONTENT_TYPE.get(declared_type)
    if declared_type and declared_type != "application/octet-stream" and declared_media_type is None:
        raise RecognitionUploadError("Неподдерживаемый Content-Type файла")
    if declared_media_type is not None and declared_media_type != media_type:
        raise RecognitionUploadError("Расширение файла не соответствует его Content-Type")

    file.file.seek(0, os.SEEK_END)
    size_bytes = file.file.tell()
    file.file.seek(0)
    if size_bytes <= 0:
        raise RecognitionUploadError("Нельзя обработать пустой файл")

    max_bytes = settings.recognition_upload_max_size_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise RecognitionUploadError(
            f"Размер файла превышает лимит {settings.recognition_upload_max_size_mb} МБ"
        )

    return UploadDescriptor(
        filename=filename,
        suffix=suffix,
        media_type=media_type,
        content_type=(
            default_content_type
            if declared_type in ("", "application/octet-stream")
            else declared_type
        ),
        size_bytes=size_bytes,
    )


def store_upload(file: UploadFile, descriptor: UploadDescriptor) -> tuple[str, str]:
    object_key = f"original/uploads/{uuid4().hex}{descriptor.suffix}"
    get_client().put_object(
        settings.minio_bucket,
        object_key,
        file.file,
        descriptor.size_bytes,
        content_type=descriptor.content_type,
    )
    return settings.minio_bucket, object_key


def discard_upload(bucket: str, object_key: str) -> None:
    try:
        get_client().remove_object(bucket, object_key)
    except Exception:
        # Ошибка очистки не должна скрывать исходную ошибку сохранения в БД.
        pass


def upload_media_links(upload: RecognitionUpload) -> dict[str, str | int | None]:
    now = datetime.now(timezone.utc)
    expires_at = upload.created_at + timedelta(days=settings.original_retention_days)
    source_url = None
    source_reason = None
    if now >= expires_at:
        source_reason = SOURCE_UNAVAILABLE
    else:
        source_url = get_presign_client().presigned_get_object(
            upload.original_bucket,
            upload.original_object_key,
            expires=timedelta(seconds=settings.presign_expiry_seconds),
        )

    result = upload.job.result if upload.job else None
    annotated_url = None
    annotated_reason = None
    if result is None:
        annotated_reason = ANNOTATED_UNAVAILABLE
    elif result.media_expires_at is not None and now >= result.media_expires_at:
        annotated_reason = "размеченный кадр удалён по сроку хранения"
    else:
        annotated_url = get_presign_client().presigned_get_object(
            result.annotated_bucket,
            result.annotated_object_key,
            expires=timedelta(seconds=settings.presign_expiry_seconds),
        )

    return {
        "source_url": source_url,
        "source_unavailable_reason": source_reason,
        "annotated_url": annotated_url,
        "annotated_unavailable_reason": annotated_reason,
        "expires_in_seconds": settings.presign_expiry_seconds,
    }
