import statistics
import hashlib
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session as DbSession, selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models import RecognitionJob, RecognitionResult, RecognitionUpload, Session, Measurement, RecognitionStatus
from app.models.requests import RecognitionCorrection
from app.models.security import User
from app.core.security import require_roles, audit
from app.services.idempotency import reserve
from app.schemas.recognition import (
    RecognitionEvaluationSummary,
    RecognitionUploadMediaRead,
    RecognitionUploadRead,
)
from app.services import recognition_uploads

router = APIRouter(prefix="/recognition", tags=["Распознавание"])


def _uploads_query():
    return select(RecognitionUpload).options(
        selectinload(RecognitionUpload.jobs).selectinload(RecognitionJob.result)
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
    request: Request,
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
    session_id: int | None = Form(default=None),
    measurement_id: int | None = Form(default=None),
    db: DbSession = Depends(get_db),
):
    if session_id is not None and db.get(Session, session_id) is None:
        raise HTTPException(404, "Занятие не найдено")
    if measurement_id is not None:
        measurement = db.scalar(select(Measurement).where(Measurement.id==measurement_id).with_for_update())
        if not measurement or measurement.session_id != session_id:
            raise HTTPException(422, "Замер не относится к указанному занятию")
        if measurement.captures:
            raise HTTPException(409, "Замер уже связан с записью камеры")
    try:
        descriptor = recognition_uploads.describe_upload(file)
    except recognition_uploads.RecognitionUploadError as exc:
        code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE if "лимит" in str(exc) else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(code, str(exc)) from None

    digest = hashlib.file_digest(file.file, "sha256").hexdigest()
    file.file.seek(0)
    fingerprint = hashlib.sha256(json.dumps([digest, descriptor.filename, sample_rate_fps,
        confidence_threshold, label, reference_people_count, session_id, measurement_id],
        ensure_ascii=True).encode()).hexdigest()
    record = reserve(db, request.state.user.id, "recognition/uploads",
                     request.headers.get("Idempotency-Key"), fingerprint)
    if record.resource_id is not None:
        return _get_upload(record.resource_id, db)
    db.scalar(select(User).where(User.id==request.state.user.id).with_for_update())
    pending = db.scalar(select(func.count(RecognitionJob.id)).join(RecognitionUpload)
        .where(RecognitionUpload.owner_id==request.state.user.id,
               RecognitionJob.status.in_([RecognitionStatus.pending, RecognitionStatus.processing, RecognitionStatus.retry_wait])))
    if pending >= settings.recognition_pending_per_user:
        raise HTTPException(429, "Дождитесь обработки ранее загруженных материалов", headers={"Retry-After":"30"})
    if measurement_id is not None and measurement.upload:
        raise HTTPException(409, "Замер уже связан с материалом; используйте повторную обработку")

    try:
        bucket, object_key = recognition_uploads.store_upload(file, descriptor)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Не удалось сохранить файл в объектном хранилище",
        ) from exc

    upload = RecognitionUpload(
        owner_id=request.state.user.id,
        session_id=session_id,
        measurement_id=measurement_id,
        content_sha256=digest,
        filename=descriptor.filename,
        media_type=descriptor.media_type,
        original_bucket=bucket,
        original_object_key=object_key,
        content_type=descriptor.content_type,
        size_bytes=descriptor.size_bytes,
        label=label.strip() if label and label.strip() else None,
        reference_people_count=reference_people_count,
    )
    upload.jobs = [RecognitionJob(
        model_name=settings.recognition_model_name,
        model_version=settings.recognition_model_version,
        sample_rate_fps=sample_rate_fps,
        confidence_threshold=confidence_threshold,
    )]
    db.add(upload)
    try:
        db.flush()
        record.resource_id = upload.id
        db.commit()
    except Exception as exc:
        db.rollback()
        # Commit may have reached PostgreSQL even when acknowledgement was lost.
        # Leave the immutable object for lifecycle/orphan reconciliation, never delete here.
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
def get_evaluation_summary(db: DbSession = Depends(get_db)):
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
def list_uploads(limit: int = 50, offset: int = 0, db: DbSession = Depends(get_db)):
    safe_limit = min(max(limit, 1), 100)
    return db.scalars(
        _uploads_query().order_by(RecognitionUpload.id.desc()).limit(safe_limit).offset(max(0, offset))
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


@router.get("/capabilities")
def capabilities():
    return {"profile": "server_inference", "formats": ["jpg", "jpeg", "png", "webp", "mp4", "mov", "avi", "webm"],
        "max_size_bytes": settings.recognition_upload_max_size_mb * 1024 * 1024,
        "max_pixels": settings.upload_max_pixels, "max_duration_seconds": settings.upload_max_duration_seconds,
        "max_video_dimension": settings.upload_max_video_dimension,
        "sample_rate_fps": {"min": 0.1, "max": 10}, "confidence": {"min": 0.05, "max": 0.95}}


@router.post("/uploads/{upload_id}/retry", response_model=RecognitionUploadRead, status_code=202)
def retry(upload_id: int, request: Request, db: DbSession = Depends(get_db)):
    upload = db.scalar(select(RecognitionUpload).where(RecognitionUpload.id==upload_id).with_for_update())
    if not upload:
        raise HTTPException(404, "Материал не найден")
    old = upload.job
    record = reserve(db, request.state.user.id, f"recognition/{upload_id}/retry",
                     request.headers.get("Idempotency-Key"), hashlib.sha256(str(upload_id).encode()).hexdigest())
    if record.resource_id is not None:
        return _get_upload(upload_id, db)
    if old.status not in {RecognitionStatus.completed, RecognitionStatus.failed, RecognitionStatus.cancelled}:
        raise HTTPException(409, "Обработка ещё не завершена")
    job = RecognitionJob(model_name=old.model_name, model_version=old.model_version,
                         sample_rate_fps=old.sample_rate_fps, confidence_threshold=old.confidence_threshold)
    upload.jobs.append(job)
    db.flush()
    record.resource_id = job.id
    db.commit()
    return _get_upload(upload_id, db)


@router.get("/uploads/{upload_id}/history")
def history(upload_id: int, db: DbSession = Depends(get_db)):
    from app.schemas.recognition import RecognitionUploadJobRead
    upload = _get_upload(upload_id, db)
    ids = [j.id for j in upload.jobs]
    corrections = db.scalars(select(RecognitionCorrection).where(RecognitionCorrection.job_id.in_(ids)))
    return {"jobs": [RecognitionUploadJobRead.model_validate(j) for j in upload.jobs],
        "corrections": [{k:getattr(c,k) for k in ("id","job_id","actor_id","people_count","reason","created_at")} for c in corrections]}


class CorrectionInput(BaseModel):
    people_count: int = Field(ge=0, le=10000)
    reason: str = Field(min_length=3, max_length=500)


@router.post("/uploads/{upload_id}/corrections", status_code=201,
             dependencies=[Depends(require_roles("admin", "operator"))])
def correct(upload_id: int, payload: CorrectionInput, request: Request, db: DbSession = Depends(get_db)):
    upload = _get_upload(upload_id, db)
    if not upload.job or not upload.job.result:
        raise HTTPException(409, "Нет результата для корректировки")
    correction = RecognitionCorrection(job_id=upload.job.id, actor_id=request.state.user.id,
                                      people_count=payload.people_count, reason=payload.reason)
    db.add(correction)
    audit(db, request, "manual_correction", "recognition_job", upload.job.id, payload.reason)
    db.commit()
    return {"id": correction.id, "job_id": correction.job_id, "people_count": correction.people_count}
