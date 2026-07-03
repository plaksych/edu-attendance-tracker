from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.core.database import get_db
from app.models import Classroom, Discipline, Group, Teacher
from app.schemas.catalog import (
    ClassroomCreate,
    ClassroomRead,
    DisciplineCreate,
    DisciplineRead,
    GroupCreate,
    GroupRead,
    TeacherCreate,
    TeacherRead,
)

router = APIRouter(tags=["Справочники"])


def _create(db: DbSession, instance):
    db.add(instance)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Такая запись уже существует") from None
    return instance


@router.get("/groups", response_model=list[GroupRead])
def list_groups(db: DbSession = Depends(get_db)):
    return db.scalars(select(Group).order_by(Group.name)).all()


@router.post("/groups", response_model=GroupRead, status_code=status.HTTP_201_CREATED)
def create_group(payload: GroupCreate, db: DbSession = Depends(get_db)):
    return _create(db, Group(**payload.model_dump()))


@router.get("/teachers", response_model=list[TeacherRead])
def list_teachers(db: DbSession = Depends(get_db)):
    return db.scalars(select(Teacher).order_by(Teacher.full_name)).all()


@router.post("/teachers", response_model=TeacherRead, status_code=status.HTTP_201_CREATED)
def create_teacher(payload: TeacherCreate, db: DbSession = Depends(get_db)):
    return _create(db, Teacher(**payload.model_dump()))


@router.get("/disciplines", response_model=list[DisciplineRead])
def list_disciplines(db: DbSession = Depends(get_db)):
    return db.scalars(select(Discipline).order_by(Discipline.name)).all()


@router.post("/disciplines", response_model=DisciplineRead, status_code=status.HTTP_201_CREATED)
def create_discipline(payload: DisciplineCreate, db: DbSession = Depends(get_db)):
    return _create(db, Discipline(**payload.model_dump()))


@router.get("/classrooms", response_model=list[ClassroomRead])
def list_classrooms(db: DbSession = Depends(get_db)):
    return db.scalars(select(Classroom).order_by(Classroom.number)).all()


@router.post("/classrooms", response_model=ClassroomRead, status_code=status.HTTP_201_CREATED)
def create_classroom(payload: ClassroomCreate, db: DbSession = Depends(get_db)):
    return _create(db, Classroom(**payload.model_dump()))
