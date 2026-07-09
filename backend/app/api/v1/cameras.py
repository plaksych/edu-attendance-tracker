import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession, selectinload

from app.core.database import get_db
from app.models import Camera, CameraCapture, CameraRole, Classroom, ClassroomCamera
from app.models.enums import CameraAggregationMode
from app.schemas.cameras import (
    CameraCreate,
    CameraRead,
    CameraUpdate,
    ClassroomCameraAssign,
)
from app.schemas.catalog import ClassroomRead

router = APIRouter(tags=["Камеры"])

_CREDENTIALS_RE = re.compile(r"//([^:/@]+):([^@/]+)@")


def _mask_credentials(url: str) -> str:
    """Пароль в RTSP-адресе не должен попадать во frontend."""
    return _CREDENTIALS_RE.sub(r"//\1:***@", url)


def _camera_read(camera: Camera) -> CameraRead:
    classroom_number = None
    if camera.classroom_links:
        classroom_number = camera.classroom_links[0].classroom.number
    return CameraRead(
        id=camera.id,
        name=camera.name,
        rtsp_url=_mask_credentials(camera.rtsp_url),
        capture_group=camera.capture_group,
        enabled=camera.enabled,
        classroom_number=classroom_number,
        created_at=camera.created_at,
    )


def _cameras_query():
    return select(Camera).options(
        selectinload(Camera.classroom_links).selectinload(ClassroomCamera.classroom)
    )


@router.get(
    "/cameras",
    response_model=list[CameraRead],
    summary="Получить список камер",
    description="Возвращает камеры с замаскированными учётными данными в адресе.",
)
def list_cameras(db: DbSession = Depends(get_db)):
    cameras = db.scalars(_cameras_query().order_by(Camera.name)).unique().all()
    return [_camera_read(c) for c in cameras]


@router.post(
    "/cameras",
    response_model=CameraRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать камеру",
    description="Регистрирует камеру. `capture_group` определяет, какой capture-узел будет её опрашивать.",
    responses={409: {"description": "Камера с таким именем уже существует"}},
)
def create_camera(payload: CameraCreate, db: DbSession = Depends(get_db)):
    camera = Camera(**payload.model_dump())
    db.add(camera)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Камера с таким именем уже существует"
        ) from None
    camera = db.scalars(_cameras_query().where(Camera.id == camera.id)).unique().one()
    return _camera_read(camera)


@router.patch(
    "/cameras/{camera_id}",
    response_model=CameraRead,
    summary="Изменить камеру",
    description="Частичное обновление. Адрес меняется только если поле `rtsp_url` передано.",
)
def update_camera(camera_id: int, payload: CameraUpdate, db: DbSession = Depends(get_db)):
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Камера не найдена")
    for field, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(camera, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Камера с таким именем уже существует"
        ) from None
    camera = db.scalars(_cameras_query().where(Camera.id == camera_id)).unique().one()
    return _camera_read(camera)


@router.delete(
    "/cameras/{camera_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить камеру",
    description=(
        "Удаляет камеру без истории записей. Камеру с завершёнными или текущими "
        "заданиями следует отключить, чтобы сохранить историю."
    ),
    responses={
        404: {"description": "Камера не найдена"},
        409: {"description": "У камеры есть задания записи в истории"},
    },
)
def delete_camera(camera_id: int, db: DbSession = Depends(get_db)):
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Камера не найдена")
    has_captures = db.scalar(
        select(CameraCapture.id).where(CameraCapture.camera_id == camera_id).limit(1)
    )
    if has_captures is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Нельзя удалить камеру с историей записей; отключите её вместо удаления",
        )
    db.delete(camera)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Нельзя удалить камеру с историей записей; отключите её вместо удаления",
        ) from None


@router.put(
    "/classrooms/{classroom_id}/cameras",
    response_model=ClassroomRead,
    summary="Назначить камеры аудитории",
    description=(
        "Полностью заменяет набор камер аудитории. Штатно поддерживается не более "
        "двух камер; для режима primary_backup требуется ровно одна камера с ролью primary."
    ),
    responses={
        409: {"description": "Камера уже привязана к другой аудитории"},
        422: {"description": "Набор камер противоречит режиму объединения"},
    },
)
def assign_classroom_cameras(
    classroom_id: int,
    payload: list[ClassroomCameraAssign],
    db: DbSession = Depends(get_db),
):
    classroom = db.get(Classroom, classroom_id)
    if classroom is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Аудитория не найдена")

    if len(payload) > 2:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Штатно поддерживается не более двух камер на аудиторию",
        )
    camera_ids = [item.camera_id for item in payload]
    if len(set(camera_ids)) != len(camera_ids):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Камеры в наборе повторяются"
        )
    if classroom.aggregation_mode == CameraAggregationMode.primary_backup:
        primary_count = sum(1 for item in payload if item.role == CameraRole.primary)
        if primary_count != 1:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Для режима primary_backup нужна ровно одна камера с ролью primary",
            )

    for camera_id in camera_ids:
        if db.get(Camera, camera_id) is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"Камера {camera_id} не найдена"
            )

    existing = db.scalars(
        select(ClassroomCamera).where(ClassroomCamera.classroom_id == classroom_id)
    ).all()
    for link in existing:
        db.delete(link)
    db.flush()

    for item in payload:
        db.add(
            ClassroomCamera(
                classroom_id=classroom_id,
                camera_id=item.camera_id,
                role=item.role,
                priority=item.priority,
                zone_code=item.zone_code,
            )
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Камера уже привязана к другой аудитории"
        ) from None

    return db.scalars(
        select(Classroom)
        .where(Classroom.id == classroom_id)
        .options(selectinload(Classroom.camera_links).selectinload(ClassroomCamera.camera))
    ).one()
