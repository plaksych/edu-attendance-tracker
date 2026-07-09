from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession, joinedload

from app.core.database import get_db
from app.models import Schedule, Session
from app.schemas.schedule import (
    ScheduleCreate,
    ScheduleImportResult,
    ScheduleRead,
    WeekTypeRead,
)
from app.services import schedule_import, timetable_import
from app.services.weeks import current_local_date, week_type_for_date

router = APIRouter(prefix="/schedule", tags=["Расписание"])

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get(
    "",
    response_model=list[ScheduleRead],
    summary="Получить расписание",
    description=(
        "Возвращает элементы расписания с вложенными справочниками. "
        "Можно фильтровать по группе, преподавателю и ISO-дню недели."
    ),
)
def list_schedule(
    group_id: int | None = Query(default=None, description="ID учебной группы"),
    teacher_id: int | None = Query(default=None, description="ID преподавателя"),
    weekday: int | None = Query(default=None, ge=1, le=7, description="ISO-день недели: 1 — понедельник, 7 — воскресенье"),
    db: DbSession = Depends(get_db),
):
    query = select(Schedule).options(
        joinedload(Schedule.group),
        joinedload(Schedule.teacher),
        joinedload(Schedule.discipline),
        joinedload(Schedule.classroom),
    )
    if group_id is not None:
        query = query.where(Schedule.group_id == group_id)
    if teacher_id is not None:
        query = query.where(Schedule.teacher_id == teacher_id)
    if weekday is not None:
        query = query.where(Schedule.weekday == weekday)
    query = query.order_by(Schedule.weekday, Schedule.starts_at)
    return db.scalars(query).unique().all()


@router.post(
    "",
    response_model=ScheduleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать занятие в расписании",
    description="Добавляет одну запись расписания. Слот группы уникален по дню, времени начала и типу недели.",
    responses={
        409: {"description": "Слот уже занят или указаны несуществующие справочники"},
    },
)
def create_schedule_item(payload: ScheduleCreate, db: DbSession = Depends(get_db)):
    item = Schedule(**payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Слот уже занят или указаны несуществующие справочники",
        ) from None
    db.refresh(item)
    return item


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить запись расписания",
    description=(
        "Удаляет запись, у которой ещё нет созданных занятий. Записи с историей "
        "защищены от удаления, чтобы не потерять данные посещаемости."
    ),
    responses={
        404: {"description": "Запись расписания не найдена"},
        409: {"description": "Для записи уже есть занятия в истории"},
    },
)
def delete_schedule_item(item_id: int, db: DbSession = Depends(get_db)):
    item = db.get(Schedule, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Запись расписания не найдена")
    has_sessions = db.scalar(
        select(Session.id).where(Session.schedule_id == item_id).limit(1)
    )
    if has_sessions is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Нельзя удалить запись расписания с созданными занятиями",
        )
    db.delete(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Нельзя удалить запись расписания с созданными занятиями",
        ) from None


@router.get(
    "/template",
    summary="Скачать Excel-шаблон расписания",
    description="Возвращает построчный `.xlsx`-шаблон для загрузки расписания через `/schedule/import`.",
    responses={
        200: {
            "description": "Excel-файл с шаблоном расписания",
            "content": {XLSX_MIME: {}},
        },
    },
)
def download_template():
    return Response(
        content=schedule_import.build_template(),
        media_type=XLSX_MIME,
        headers={"Content-Disposition": 'attachment; filename="schedule_template.xlsx"'},
    )


@router.post(
    "/import",
    response_model=ScheduleImportResult,
    summary="Импортировать расписание из Excel",
    description=(
        "Принимает `.xlsx` и автоматически определяет формат: институтская сетка "
        "или простой построчный шаблон. Создаёт недостающие справочники и записи расписания."
    ),
    responses={
        400: {"description": "Файл не является `.xlsx` или содержит некорректные данные"},
    },
)
def import_schedule(file: UploadFile = File(...), db: DbSession = Depends(get_db)):
    """Импорт расписания из .xlsx.

    Формат определяется автоматически: институтская сетка (группы по колонкам,
    белая/зелёная неделя) или простой построчный шаблон.
    """
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Ожидается файл в формате .xlsx"
        )
    try:
        if timetable_import.looks_like_timetable(file.file):
            return timetable_import.import_timetable(db, file.file)
        return schedule_import.import_schedule(db, file.file)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None


@router.get(
    "/week-type",
    response_model=WeekTypeRead,
    summary="Определить тип учебной недели",
    description="Возвращает белую или зелёную неделю для даты относительно `SEMESTER_START`.",
)
def get_week_type(
    target_date: date | None = Query(default=None, alias="date", description="Дата проверки. Если не указана, используется текущая дата."),
):
    """Белая или зелёная неделя для даты (по умолчанию — сегодня)."""
    resolved = target_date or current_local_date()
    return WeekTypeRead(date=resolved, week_type=week_type_for_date(resolved))
