from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.models import (
    AttendanceRecord,
    Classroom,
    Discipline,
    Group,
    Schedule,
    Session,
    SessionStatus,
    Teacher,
)
from app.schemas.stats import (
    BreakdownItem,
    EntityStats,
    GroupTimeline,
    SummaryStats,
    TimelinePoint,
)


def _round(value, digits: int = 4):
    return round(float(value), digits) if value is not None else None


def summary(db: DbSession) -> SummaryStats:
    today = date.today()
    return SummaryStats(
        groups=db.scalar(select(func.count(Group.id))) or 0,
        teachers=db.scalar(select(func.count(Teacher.id))) or 0,
        disciplines=db.scalar(select(func.count(Discipline.id))) or 0,
        classrooms=db.scalar(select(func.count(Classroom.id))) or 0,
        sessions_total=db.scalar(select(func.count(Session.id))) or 0,
        sessions_today=db.scalar(
            select(func.count(Session.id)).where(Session.date == today)
        )
        or 0,
        sessions_finished=db.scalar(
            select(func.count(Session.id)).where(Session.status == SessionStatus.finished)
        )
        or 0,
        avg_attendance_rate=_round(
            db.scalar(select(func.avg(AttendanceRecord.attendance_rate)))
        ),
    )


def _entity_stats(
    db: DbSession,
    entity,
    entity_id: int,
    filter_column,
    breakdown_entity,
    breakdown_join_column,
    name_attr: str,
) -> EntityStats:
    instance = db.get(entity, entity_id)
    if instance is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{entity.__name__} не найден")

    base = (
        select(
            func.count(AttendanceRecord.id),
            func.avg(AttendanceRecord.attendance_rate),
            func.avg(AttendanceRecord.detected_avg),
        )
        .join(Session, AttendanceRecord.session_id == Session.id)
        .join(Schedule, Session.schedule_id == Schedule.id)
        .where(filter_column == entity_id)
    )
    total_sessions, avg_rate, avg_detected = db.execute(base).one()

    breakdown_name = getattr(breakdown_entity, name_attr)
    breakdown_rows = db.execute(
        select(
            breakdown_entity.id,
            breakdown_name,
            func.count(AttendanceRecord.id),
            func.avg(AttendanceRecord.attendance_rate),
            func.avg(AttendanceRecord.detected_avg),
        )
        .join(Schedule, breakdown_join_column == breakdown_entity.id)
        .join(Session, Session.schedule_id == Schedule.id)
        .join(AttendanceRecord, AttendanceRecord.session_id == Session.id)
        .where(filter_column == entity_id)
        .group_by(breakdown_entity.id, breakdown_name)
        .order_by(breakdown_name)
    ).all()

    return EntityStats(
        id=instance.id,
        name=getattr(instance, "name", None) or getattr(instance, "full_name", ""),
        sessions_finished=total_sessions or 0,
        avg_rate=_round(avg_rate),
        avg_detected=_round(avg_detected, 2),
        breakdown=[
            BreakdownItem(
                id=row[0],
                name=row[1],
                sessions=row[2],
                avg_rate=_round(row[3]),
                avg_detected=_round(row[4], 2),
            )
            for row in breakdown_rows
        ],
    )


def teacher_stats(db: DbSession, teacher_id: int) -> EntityStats:
    return _entity_stats(
        db,
        Teacher,
        teacher_id,
        Schedule.teacher_id,
        Group,
        Schedule.group_id,
        "name",
    )


def discipline_stats(db: DbSession, discipline_id: int) -> EntityStats:
    return _entity_stats(
        db,
        Discipline,
        discipline_id,
        Schedule.discipline_id,
        Group,
        Schedule.group_id,
        "name",
    )


def group_stats(db: DbSession, group_id: int) -> EntityStats:
    return _entity_stats(
        db,
        Group,
        group_id,
        Schedule.group_id,
        Discipline,
        Schedule.discipline_id,
        "name",
    )


def group_timeline(
    db: DbSession, group_id: int, date_from: date | None, date_to: date | None
) -> GroupTimeline:
    group = db.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Группа не найдена")

    query = (
        select(
            Session.date,
            func.avg(AttendanceRecord.attendance_rate),
            func.avg(AttendanceRecord.detected_avg),
        )
        .join(AttendanceRecord, AttendanceRecord.session_id == Session.id)
        .join(Schedule, Session.schedule_id == Schedule.id)
        .where(Schedule.group_id == group_id)
        .group_by(Session.date)
        .order_by(Session.date)
    )
    if date_from:
        query = query.where(Session.date >= date_from)
    if date_to:
        query = query.where(Session.date <= date_to)

    points = [
        TimelinePoint(
            date=row[0],
            avg_rate=_round(row[1]),
            detected_avg=_round(row[2], 2),
            expected=group.students_count,
        )
        for row in db.execute(query).all()
    ]
    return GroupTimeline(group_id=group.id, group_name=group.name, points=points)
