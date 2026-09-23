from datetime import date

from fastapi import APIRouter, Depends, Query, Response, HTTPException
import csv
from io import StringIO
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.database import get_db
from app.core.config import settings
from app.models import AttendanceRecord, Session, Schedule, Group, Discipline
from app.schemas.stats import EntityStats, GroupTimeline, SummaryStats
from app.services import stats as stats_service

router = APIRouter(prefix="/stats", tags=["Статистика"])


def csv_cell(value):
    text = "" if value is None else str(value)
    return (
        "'" + text
        if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r"))
        else text
    )


@router.get(
    "/export.csv",
    summary="Выгрузить агрегаты занятий без медиа и персональных результатов",
)
def export_attendance(
    date_from: date,
    date_to: date,
    group_id: int | None = None,
    db: DbSession = Depends(get_db),
):
    if date_to < date_from or (date_to - date_from).days > 366:
        raise HTTPException(422, "Период должен составлять не более 366 дней")
    query = (
        select(
            Session.date,
            Group.name,
            Discipline.name,
            AttendanceRecord.expected_count,
            AttendanceRecord.detected_average,
            AttendanceRecord.attendance_rate,
            AttendanceRecord.calculation_status,
        )
        .join(AttendanceRecord, AttendanceRecord.session_id == Session.id)
        .join(Schedule, Schedule.id == Session.schedule_id)
        .join(Group, Group.id == Schedule.group_id)
        .join(Discipline, Discipline.id == Schedule.discipline_id)
        .where(Session.date >= date_from, Session.date <= date_to)
        .order_by(Session.date, Group.name)
        .limit(10001)
    )
    if group_id is not None:
        query = query.where(Group.id == group_id)
    rows = db.execute(query).all()
    if len(rows) > 10000:
        raise HTTPException(422, "Сузьте период: в выгрузке не более 10000 занятий")
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "date",
            "group",
            "discipline",
            "expected",
            "detected",
            "rate",
            "status",
            "timezone",
            "provenance",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                csv_cell(row[0]),
                csv_cell(row[1]),
                csv_cell(row[2]),
                row[3],
                row[4],
                row[5],
                row[6].value,
                settings.timezone,
                "server_inference",
            ]
        )
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="attendance.csv"'},
    )


@router.get(
    "/summary",
    response_model=SummaryStats,
    summary="Получить сводку для дашборда",
    description="Возвращает общие счётчики и среднюю посещаемость по завершённым занятиям.",
)
def get_summary(db: DbSession = Depends(get_db)):
    return stats_service.summary(db)


@router.get(
    "/teachers/{teacher_id}",
    response_model=EntityStats,
    summary="Получить статистику преподавателя",
    description="Возвращает агрегаты преподавателя и разбивку по группам.",
)
def get_teacher_stats(teacher_id: int, db: DbSession = Depends(get_db)):
    return stats_service.teacher_stats(db, teacher_id)


@router.get(
    "/disciplines/{discipline_id}",
    response_model=EntityStats,
    summary="Получить статистику дисциплины",
    description="Возвращает агрегаты дисциплины и разбивку по группам.",
)
def get_discipline_stats(discipline_id: int, db: DbSession = Depends(get_db)):
    return stats_service.discipline_stats(db, discipline_id)


@router.get(
    "/groups/{group_id}",
    response_model=EntityStats,
    summary="Получить статистику группы",
    description="Возвращает агрегаты группы и разбивку по дисциплинам.",
)
def get_group_stats(group_id: int, db: DbSession = Depends(get_db)):
    return stats_service.group_stats(db, group_id)


@router.get(
    "/groups/{group_id}/timeline",
    response_model=GroupTimeline,
    summary="Получить динамику посещаемости группы",
    description="Возвращает точки динамики по датам. Фильтры `date_from` и `date_to` ограничивают период.",
)
def get_group_timeline(
    group_id: int,
    date_from: date | None = Query(default=None, description="Начальная дата периода"),
    date_to: date | None = Query(default=None, description="Конечная дата периода"),
    db: DbSession = Depends(get_db),
):
    return stats_service.group_timeline(db, group_id, date_from, date_to)
