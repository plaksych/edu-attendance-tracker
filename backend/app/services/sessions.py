from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import joinedload

from app.models import (
    CalendarException,
    CameraCapture,
    CaptureStatus,
    Measurement,
    MeasurementStatus,
    RecognitionJob,
    RecognitionStatus,
    RecognitionUpload,
    Schedule,
    Session,
    SessionStatus,
    WeekType,
)
from app.services.weeks import week_type_for_date
from app.core.config import settings


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
    if target_date < settings.semester_start or (
        settings.semester_end and target_date > settings.semester_end
    ):
        return
    exception = db.get(CalendarException, target_date)
    if exception and not exception.teaching:
        return
    weekday = (
        exception.weekday
        if exception and exception.weekday
        else target_date.isoweekday()
    )
    week = week_type_for_date(target_date)
    if exception and exception.week_type:
        week = WeekType(exception.week_type)
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
    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    schedules = db.scalars(select(Schedule).where(Schedule.id.in_(missing))).all()
    for schedule in schedules:
        db.execute(
            insert(Session)
            .values(
                schedule_id=schedule.id,
                date=target_date,
                expected_count_snapshot=schedule.group.students_count,
                aggregation_mode_snapshot=(
                    schedule.classroom.aggregation_mode.value
                    if schedule.classroom
                    else "single"
                ),
            )
            .on_conflict_do_nothing(index_elements=["schedule_id", "date"])
        )
    db.commit()


def list_sessions_for_date(db: DbSession, target_date: date) -> list[Session]:
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
    session = db.scalar(
        select(Session).where(Session.id == session_id).with_for_update()
    )
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Занятие не найдено")
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
    captures = db.scalars(
        select(CameraCapture)
        .join(Measurement)
        .where(
            Measurement.session_id == session_id,
            CameraCapture.status.in_(
                (
                    CaptureStatus.pending,
                    CaptureStatus.retry_wait,
                    CaptureStatus.claimed,
                    CaptureStatus.recording,
                    CaptureStatus.uploading,
                )
            ),
        )
        .with_for_update(of=CameraCapture)
        .execution_options(populate_existing=True)
    ).all()
    for capture in captures:
        capture.status = CaptureStatus.cancelled
        capture.claim_token = capture.lease_until = capture.worker_id = None
        capture.updated_at = now
    capture_ids = (
        select(CameraCapture.id)
        .join(Measurement)
        .where(Measurement.session_id == session_id)
    )
    upload_ids = select(RecognitionUpload.id).where(
        RecognitionUpload.session_id == session_id
    )
    jobs = db.scalars(
        select(RecognitionJob)
        .where(
            RecognitionJob.status.in_(
                (
                    RecognitionStatus.pending,
                    RecognitionStatus.retry_wait,
                    RecognitionStatus.processing,
                )
            ),
            RecognitionJob.camera_capture_id.in_(capture_ids)
            | RecognitionJob.upload_id.in_(upload_ids),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    for job in jobs:
        job.status = RecognitionStatus.cancelled
        job.claim_token = job.lease_until = job.worker_id = None
        job.finished_at = job.updated_at = now
    db.commit()
    return get_session(db, session_id)
