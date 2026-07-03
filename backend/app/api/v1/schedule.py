from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession, joinedload

from app.core.database import get_db
from app.models import Schedule
from app.schemas.schedule import (
    ScheduleCreate,
    ScheduleImportResult,
    ScheduleRead,
    WeekTypeRead,
)
from app.services import schedule_import, timetable_import
from app.services.weeks import week_type_for_date

router = APIRouter(prefix="/schedule", tags=["Расписание"])

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("", response_model=list[ScheduleRead])
def list_schedule(
    group_id: int | None = Query(default=None),
    teacher_id: int | None = Query(default=None),
    weekday: int | None = Query(default=None, ge=1, le=7),
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


@router.post("", response_model=ScheduleRead, status_code=status.HTTP_201_CREATED)
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


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule_item(item_id: int, db: DbSession = Depends(get_db)):
    item = db.get(Schedule, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Запись расписания не найдена")
    db.delete(item)
    db.commit()


@router.get("/template")
def download_template():
    return Response(
        content=schedule_import.build_template(),
        media_type=XLSX_MIME,
        headers={"Content-Disposition": 'attachment; filename="schedule_template.xlsx"'},
    )


@router.post("/import", response_model=ScheduleImportResult)
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


@router.get("/week-type", response_model=WeekTypeRead)
def get_week_type(target_date: date | None = Query(default=None, alias="date")):
    """Белая или зелёная неделя для даты (по умолчанию — сегодня)."""
    resolved = target_date or date.today()
    return WeekTypeRead(date=resolved, week_type=week_type_for_date(resolved))
