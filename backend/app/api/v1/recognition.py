import statistics

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession, selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models import RecognitionJob, RecognitionResult, RecognitionUpload
from app.schemas.recognition import (
    RecognitionEvaluationSummary,
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
    label: str | None = Form(
        default=None,
        max_length=160,
        description="Краткое название материала для журнала проверки",
    ),
    reference_people_count: int | None = Form(
        default=None,
        ge=0,
        le=1000,
        description="Число людей, вручную отмеченное на материале",
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
        label=label.strip() if label and label.strip() else None,
        reference_people_count=reference_people_count,
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
    "/evaluation/summary",
    response_model=RecognitionEvaluationSummary,
    summary="Получить качество по материалам с ручной разметкой",
    description=(
        "Считает ошибки только по завершённым загрузкам, в которых при создании "
        "задано эталонное число людей."
    ),
)
def get_evaluation_summary(db: DbSession):
    rows = db.execute(
        select(
            RecognitionResult.absolute_error,
            RecognitionResult.relative_error,
            RecognitionResult.within_tolerance,
        )
        .join(RecognitionJob, RecognitionResult.recognition_job_id == RecognitionJob.id)
        .join(RecognitionUpload, RecognitionJob.upload_id == RecognitionUpload.id)
        .where(
            RecognitionUpload.reference_people_count.is_not(None),
            RecognitionResult.absolute_error.is_not(None),
        )
    ).all()
    absolute_errors = [int(row.absolute_error) for row in rows if row.absolute_error is not None]
    relative_errors = [float(row.relative_error) for row in rows if row.relative_error is not None]
    return RecognitionEvaluationSummary(
        checked_materials=len(absolute_errors),
        within_tolerance_count=sum(bool(row.within_tolerance) for row in rows),
        mean_absolute_error=(statistics.fmean(absolute_errors) if absolute_errors else None),
        median_absolute_error=(statistics.median(absolute_errors) if absolute_errors else None),
        max_absolute_error=max(absolute_errors) if absolute_errors else None,
        mean_relative_error=(statistics.fmean(relative_errors) if relative_errors else None),
    )


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
