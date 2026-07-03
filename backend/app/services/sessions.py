from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import joinedload, selectinload

from app.models import (
    AttendanceRecord,
    DetectionSnapshot,
    Schedule,
    Session,
    SessionStatus,
    WeekType,
)
from app.services import recognition_client
from app.services.recognition_client import RecognitionUnavailable
from app.services.weeks import week_type_for_date


def _session_query():
    return select(Session).options(
        joinedload(Session.schedule).joinedload(Schedule.group),
        joinedload(Session.schedule).joinedload(Schedule.teacher),
        joinedload(Session.schedule).joinedload(Schedule.discipline),
        joinedload(Session.schedule).joinedload(Schedule.classroom),
        joinedload(Session.attendance),
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
    sessions = db.scalars(
        _session_query().where(Session.date == target_date).join(Session.schedule)
    ).unique().all()
    return sorted(sessions, key=lambda s: s.schedule.starts_at)


def get_session(db: DbSession, session_id: int, with_snapshots: bool = False) -> Session:
    query = _session_query().where(Session.id == session_id)
    if with_snapshots:
        query = query.options(selectinload(Session.snapshots))
    session = db.scalars(query).unique().one_or_none()
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Занятие не найдено")
    return session


def start_session(db: DbSession, session_id: int) -> Session:
    session = get_session(db, session_id)
    if session.status == SessionStatus.in_progress:
        raise HTTPException(status.HTTP_409_CONFLICT, "Занятие уже идёт")
    if session.status == SessionStatus.finished:
        raise HTTPException(status.HTTP_409_CONFLICT, "Занятие уже завершено")

    classroom = session.schedule.classroom
    if classroom is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "У занятия не указана аудитория"
        )
    if not classroom.camera_url:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"У аудитории {classroom.number} не настроена камера",
        )

    try:
        recognition_client.start_stream(session.id, classroom.camera_url)
    except RecognitionUnavailable:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Recognition-сервис недоступен"
        ) from None

    session.status = SessionStatus.in_progress
    session.started_at = datetime.now(timezone.utc)
    db.commit()
    return session


def finish_session(db: DbSession, session_id: int) -> Session:
    session = get_session(db, session_id)
    if session.status != SessionStatus.in_progress:
        raise HTTPException(status.HTTP_409_CONFLICT, "Занятие не находится в процессе")

    recognition_client.stop_stream(session.id)

    session.status = SessionStatus.finished
    session.finished_at = datetime.now(timezone.utc)
    _build_attendance_record(db, session)
    db.commit()
    # Сбрасываем кэш сессии, чтобы подтянулась только что созданная запись посещаемости
    db.expire_all()
    return get_session(db, session_id)


def _build_attendance_record(db: DbSession, session: Session) -> None:
    counts = db.scalars(
        select(DetectionSnapshot.person_count).where(
            DetectionSnapshot.session_id == session.id
        )
    ).all()
    if not counts:
        return

    expected = session.schedule.group.students_count
    detected_avg = sum(counts) / len(counts)
    rate = round(min(detected_avg / expected, 1.0), 4) if expected > 0 else None

    db.add(
        AttendanceRecord(
            session_id=session.id,
            expected_count=expected,
            detected_avg=round(detected_avg, 2),
            detected_max=max(counts),
            snapshots_count=len(counts),
            attendance_rate=rate,
        )
    )


def add_snapshot(
    db: DbSession,
    session_id: int,
    captured_at: datetime,
    person_count: int,
    confidence: float | None,
    frame_path: str | None,
) -> DetectionSnapshot:
    session = get_session(db, session_id)
    if session.status != SessionStatus.in_progress:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Замеры принимаются только для идущего занятия"
        )
    snapshot = DetectionSnapshot(
        session_id=session_id,
        captured_at=captured_at,
        person_count=person_count,
        confidence=confidence,
        frame_path=frame_path,
    )
    db.add(snapshot)
    db.commit()
    return snapshot
