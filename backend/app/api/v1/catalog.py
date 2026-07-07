from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession, selectinload

from app.core.database import get_db
from app.models import Classroom, ClassroomCamera, Discipline, Group, Teacher
from app.schemas.catalog import (
    ClassroomCreate,
    ClassroomRead,
    ClassroomUpdate,
    DisciplineCreate,
    DisciplineRead,
    GroupCreate,
    GroupRead,
    GroupUpdate,
    TeacherCreate,
    TeacherRead,
)

router = APIRouter(tags=["Справочники"])

CONFLICT_RESPONSE = {
    409: {"description": "Запись с таким уникальным значением уже существует"},
}


def _create(db: DbSession, instance):
    db.add(instance)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Такая запись уже существует") from None
    return instance


def _classrooms_query():
    return select(Classroom).options(
        selectinload(Classroom.camera_links).selectinload(ClassroomCamera.camera)
    )


@router.get(
    "/groups",
    response_model=list[GroupRead],
    summary="Получить список групп",
    description="Возвращает учебные группы, отсортированные по названию.",
)
def list_groups(db: DbSession = Depends(get_db)):
    return db.scalars(select(Group).order_by(Group.name)).all()


@router.post(
    "/groups",
    response_model=GroupRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать группу",
    description="Создаёт учебную группу. `students_count` используется как ожидаемая численность при расчёте посещаемости.",
    responses=CONFLICT_RESPONSE,
)
def create_group(payload: GroupCreate, db: DbSession = Depends(get_db)):
    return _create(db, Group(**payload.model_dump()))


@router.patch(
    "/groups/{group_id}",
    response_model=GroupRead,
    summary="Изменить группу",
    description="Частичное обновление: чаще всего используется для указания численности группы.",
)
def update_group(group_id: int, payload: GroupUpdate, db: DbSession = Depends(get_db)):
    group = db.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Группа не найдена")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(group, field, value)
    db.commit()
    return group


@router.get(
    "/teachers",
    response_model=list[TeacherRead],
    summary="Получить список преподавателей",
    description="Возвращает преподавателей, отсортированных по ФИО.",
)
def list_teachers(db: DbSession = Depends(get_db)):
    return db.scalars(select(Teacher).order_by(Teacher.full_name)).all()


@router.post(
    "/teachers",
    response_model=TeacherRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать преподавателя",
    description="Создаёт преподавателя для дальнейшей привязки к расписанию.",
    responses=CONFLICT_RESPONSE,
)
def create_teacher(payload: TeacherCreate, db: DbSession = Depends(get_db)):
    return _create(db, Teacher(**payload.model_dump()))


@router.get(
    "/disciplines",
    response_model=list[DisciplineRead],
    summary="Получить список дисциплин",
    description="Возвращает дисциплины, отсортированные по названию.",
)
def list_disciplines(db: DbSession = Depends(get_db)):
    return db.scalars(select(Discipline).order_by(Discipline.name)).all()


@router.post(
    "/disciplines",
    response_model=DisciplineRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать дисциплину",
    description="Создаёт дисциплину для использования в расписании и статистике.",
    responses=CONFLICT_RESPONSE,
)
def create_discipline(payload: DisciplineCreate, db: DbSession = Depends(get_db)):
    return _create(db, Discipline(**payload.model_dump()))


@router.get(
    "/classrooms",
    response_model=list[ClassroomRead],
    summary="Получить список аудиторий",
    description="Возвращает аудитории с режимом объединения камер и привязанными камерами.",
)
def list_classrooms(db: DbSession = Depends(get_db)):
    return db.scalars(_classrooms_query().order_by(Classroom.number)).all()


@router.post(
    "/classrooms",
    response_model=ClassroomRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать аудиторию",
    description="Создаёт аудиторию. Камеры привязываются отдельно через `PUT /classrooms/{id}/cameras`.",
    responses=CONFLICT_RESPONSE,
)
def create_classroom(payload: ClassroomCreate, db: DbSession = Depends(get_db)):
    classroom = _create(db, Classroom(**payload.model_dump()))
    return db.scalars(
        _classrooms_query().where(Classroom.id == classroom.id)
    ).one()


@router.patch(
    "/classrooms/{classroom_id}",
    response_model=ClassroomRead,
    summary="Изменить аудиторию",
    description="Частичное обновление вместимости и режима объединения камер.",
)
def update_classroom(
    classroom_id: int, payload: ClassroomUpdate, db: DbSession = Depends(get_db)
):
    classroom = db.get(Classroom, classroom_id)
    if classroom is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Аудитория не найдена")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(classroom, field, value)
    db.commit()
    return db.scalars(_classrooms_query().where(Classroom.id == classroom_id)).one()
