from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import joinedload

from app.models import (
    CameraCapture,
    CaptureStatus,
    Measurement,
    MeasurementStatus,
    RecognitionJob,
    RecognitionStatus,
    Schedule,
    Session,
    SessionStatus,
    WeekType,
)
from app.services.weeks import week_type_for_date


def _base_query():
    return select(Session).options(
        joinedload(Session.schedule).joinedload(Schedule.group),
        joinedload(Session.schedule).joinedload(Schedule.teacher),
        joinedload(Session.schedule).joinedload(Schedule.discipline),
        joinedload(Session.schedule).joinedload(Schedule.classroom),
        joinedload(Session.attendance),
        joinedload(Session.measurements),
    )


def ensure_sessions_for_date(db: DbSession, target_date: date) -> None:
    """Создаёт записи занятий на дату по расписанию, если их ещё нет.

    Учитывает чередование недель: берутся пары «каждую неделю»
    плюс пары белой или зелёной недели — по чётности недели даты.
    """
    weekday = target_date.isoweekday()
    week = week_type_for_date(target_date)
    schedule_ids = set(
        db.scalars(
            select(Schedule.id).where(
                Schedule.weekday == weekday,
                Schedule.week_type.in_([WeekType.every, week]),
            )
        ).all()
    )
    existing = set(
        db.scalars(select(Session.schedule_id).where(Session.date == target_date)).all()
    )
    missing = schedule_ids - existing
    if not missing:
        return
    db.add_all(Session(schedule_id=sid, date=target_date) for sid in missing)
    db.commit()


def list_sessions_for_date(db: DbSession, target_date: date) -> list[Session]:
    ensure_sessions_for_date(db, target_date)
    sessions = (
        db.scalars(_base_query().where(Session.date == target_date)).unique().all()
    )
    return sorted(sessions, key=lambda s: (s.schedule.starts_at, s.schedule.group.name))


def get_session(db: DbSession, session_id: int, with_captures: bool = False) -> Session:
    query = _base_query().where(Session.id == session_id)
    if with_captures:
        query = query.options(
            joinedload(Session.measurements)
            .joinedload(Measurement.captures)
            .joinedload(CameraCapture.camera),
            joinedload(Session.measurements)
            .joinedload(Measurement.captures)
            .joinedload(CameraCapture.recognition_job)
            .joinedload(RecognitionJob.result),
        )
    session = db.scalars(query).unique().one_or_none()
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Занятие не найдено")
    return session


def cancel_session(db: DbSession, session_id: int) -> Session:
    """Отменяет занятие вместе с незавершёнными замерами и заданиями."""
    session = get_session(db, session_id, with_captures=True)
    if session.status == SessionStatus.finished:
        raise HTTPException(status.HTTP_409_CONFLICT, "Занятие уже завершено")
    if session.status == SessionStatus.cancelled:
        raise HTTPException(status.HTTP_409_CONFLICT, "Занятие уже отменено")

    now = datetime.now(timezone.utc)
    session.status = SessionStatus.cancelled
    for m in session.measurements:
        if m.status in (
            MeasurementStatus.completed,
            MeasurementStatus.partially_completed,
            MeasurementStatus.failed,
        ):
            continue
        m.status = MeasurementStatus.cancelled
        m.completed_at = now
        for capture in m.captures:
            if capture.status in (
                CaptureStatus.pending,
                CaptureStatus.retry_wait,
                CaptureStatus.claimed,
            ):
                capture.status = CaptureStatus.cancelled
                capture.updated_at = now
            job = capture.recognition_job
            if job is not None and job.status in (
                RecognitionStatus.pending,
                RecognitionStatus.retry_wait,
            ):
                job.status = RecognitionStatus.cancelled
                job.updated_at = now
    db.commit()
    return get_session(db, session_id)
