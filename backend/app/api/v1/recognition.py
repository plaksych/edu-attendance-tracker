from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession, selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models import RecognitionJob, RecognitionUpload
from app.schemas.recognition import (
    RecognitionUploadMediaRead,
    RecognitionUploadRead,
)
from app.services import recognition_uploads

router = APIRouter(prefix="/recognition", tags=["Распознавание"])


def _uploads_query():
    return select(RecognitionUpload).options(
        selectinload(RecognitionUpload.job).selectinload(RecognitionJob.result)
    )


def _get_upload(upload_id: int, db: DbSession) -> RecognitionUpload:
    upload = db.scalars(
        _uploads_query().where(RecognitionUpload.id == upload_id)
    ).one_or_none()
    if upload is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Файл распознавания не найден")
    return upload


@router.post(
    "/uploads",
    response_model=RecognitionUploadRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Загрузить видео или изображение для распознавания",
    description=(
        "Сохраняет файл в MinIO и создаёт задание для recognition-worker. "
        "Поддерживаются MP4, MOV, AVI, WebM, JPG, PNG и WebP. "
        "Видеофайл анализируется по выборке кадров, изображение — одним кадром."
    ),
    responses={413: {"description": "Размер файла превышает лимит"}},
)
def create_upload(
    file: UploadFile = File(..., description="Видео или изображение"),
    sample_rate_fps: float = Form(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Кадров в секунду для видео; для изображения не используется",
    ),
    confidence_threshold: float = Form(
        default=0.35,
        ge=0.05,
        le=0.95,
        description="Минимальная уверенность детектора",
    ),
    db: DbSession = Depends(get_db),
):
    try:
        descriptor = recognition_uploads.describe_upload(file)
    except recognition_uploads.RecognitionUploadError as exc:
        code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE if "лимит" in str(exc) else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(code, str(exc)) from None

    try:
        bucket, object_key = recognition_uploads.store_upload(file, descriptor)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Не удалось сохранить файл в объектном хранилище",
        ) from exc

    upload = RecognitionUpload(
        filename=descriptor.filename,
        media_type=descriptor.media_type,
        original_bucket=bucket,
        original_object_key=object_key,
        content_type=descriptor.content_type,
        size_bytes=descriptor.size_bytes,
    )
    upload.job = RecognitionJob(
        model_name=settings.recognition_model_name,
        model_version=settings.recognition_model_version,
        sample_rate_fps=sample_rate_fps,
        confidence_threshold=confidence_threshold,
    )
    db.add(upload)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        recognition_uploads.discard_upload(bucket, object_key)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Не удалось создать задание распознавания",
        ) from exc
    return _get_upload(upload.id, db)


@router.get(
    "/uploads",
    response_model=list[RecognitionUploadRead],
    summary="Получить очередь загруженных файлов",
    description="Возвращает последние задания распознавания, включая состояние и результат.",
)
def list_uploads(limit: int = 50, db: DbSession = Depends(get_db)):
    safe_limit = min(max(limit, 1), 100)
    return db.scalars(
        _uploads_query().order_by(RecognitionUpload.id.desc()).limit(safe_limit)
    ).all()


@router.get(
    "/uploads/{upload_id}",
    response_model=RecognitionUploadRead,
    summary="Получить состояние задания распознавания",
)
def get_upload(upload_id: int, db: DbSession = Depends(get_db)):
    return _get_upload(upload_id, db)


@router.get(
    "/uploads/{upload_id}/media",
    response_model=RecognitionUploadMediaRead,
    summary="Получить временные ссылки на файл и размеченный кадр",
)
def get_upload_media(upload_id: int, db: DbSession = Depends(get_db)):
    return recognition_uploads.upload_media_links(_get_upload(upload_id, db))
