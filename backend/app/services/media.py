"""Временные ссылки на медиа в MinIO.

Frontend не имеет прямого доступа к бакету: backend подписывает URL
с ограниченным сроком действия. После истечения срока хранения ссылки
не выдаются — файлы удалены lifecycle-политикой.
"""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session as DbSession, joinedload
from sqlalchemy import select

from app.core.config import settings
from app.core.object_storage import get_presign_client
from app.models import CameraCapture, RecognitionJob

EXPIRED_REASON = "медиа удалено по сроку хранения"


def _presign(bucket: str, key: str) -> str:
    return get_presign_client().presigned_get_object(
        bucket,
        key,
        expires=timedelta(seconds=settings.presign_expiry_seconds),
    )


def capture_media_links(db: DbSession, capture_id: int) -> dict:
    capture = db.scalars(
        select(CameraCapture)
        .where(CameraCapture.id == capture_id)
        .options(
            joinedload(CameraCapture.recognition_job).joinedload(RecognitionJob.result)
        )
    ).unique().one_or_none()
    if capture is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Запись не найдена")

    now = datetime.now(timezone.utc)
    video_url = None
    video_reason = None
    if capture.original_object_key and capture.original_bucket:
        uploaded_at = capture.capture_finished_at or capture.created_at
        expires_at = uploaded_at + timedelta(days=settings.original_retention_days)
        if now >= expires_at:
            video_reason = EXPIRED_REASON
        else:
            video_url = _presign(capture.original_bucket, capture.original_object_key)
    else:
        video_reason = "видео не записано"

    annotated_url = None
    annotated_reason = None
    result = capture.recognition_job.result if capture.recognition_job else None
    if result is None:
        annotated_reason = "кадр ещё не сформирован"
    elif result.media_expires_at is not None and now >= result.media_expires_at:
        annotated_reason = EXPIRED_REASON
    else:
        annotated_url = _presign(result.annotated_bucket, result.annotated_object_key)

    return {
        "video_url": video_url,
        "video_unavailable_reason": video_reason,
        "annotated_url": annotated_url,
        "annotated_unavailable_reason": annotated_reason,
        "expires_in_seconds": settings.presign_expiry_seconds,
    }
