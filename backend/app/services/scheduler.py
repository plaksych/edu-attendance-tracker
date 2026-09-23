"""Measurement Scheduler: фоновый цикл backend-процесса.

Каждый тик:
- создаёт занятия по расписанию на горизонт вперёд;
- создаёт по два замера на занятие (after_start / before_end);
- создаёт задания записи для камер аудитории;
- ведёт жизненный цикл занятий по времени;
- возвращает в очередь задания с истёкшим lease;
- закрывает замеры и формирует итог посещаемости.

Все операции идемпотентны: уникальные ограничения БД защищают от дублей
при перезапуске или параллельном запуске тика.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select, update, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session as DbSession, joinedload

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import (
    CameraCapture,
    CaptureStatus,
    ClassroomCamera,
    Camera,
    Measurement,
    MeasurementStatus,
    MeasurementType,
    Schedule,
    Session,
    SessionStatus,
)
from app.services import aggregation
from app.services.sessions import ensure_sessions_for_date

logger = logging.getLogger(__name__)


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def _local_dt(day: date, moment) -> datetime:
    return datetime.combine(day, moment, tzinfo=_tz())


def measurement_times(starts: datetime, ends: datetime, offset: timedelta) -> tuple[datetime, datetime]:
    """Keep both observations inside the session, including short sessions."""
    duration = ends - starts
    if duration <= timedelta(0):
        raise ValueError("Session duration must be positive")
    if offset <= timedelta(0) or offset * 2 >= duration:
        offset = duration / 3
    return starts + offset, ends - offset


def ensure_sessions_horizon(db: DbSession) -> None:
    today = datetime.now(_tz()).date()
    for offset in range(settings.schedule_horizon_days):
        ensure_sessions_for_date(db, today + timedelta(days=offset))


def ensure_measurements(db: DbSession) -> int:
    """Создаёт недостающие замеры для занятий горизонта."""
    today = datetime.now(_tz()).date()
    horizon_end = today + timedelta(days=settings.schedule_horizon_days)

    sessions = db.scalars(
        select(Session)
        .where(
            Session.date >= today,
            Session.date < horizon_end,
            Session.status.in_([SessionStatus.scheduled, SessionStatus.in_progress]),
        )
        .options(joinedload(Session.schedule), joinedload(Session.measurements))
    ).unique().all()

    offset = timedelta(minutes=settings.measurement_offset_minutes)
    created = 0
    for session in sessions:
        existing = {m.type for m in session.measurements}
        after_start, before_end = measurement_times(
            _local_dt(session.date, session.schedule.starts_at),
            _local_dt(session.date, session.schedule.ends_at), offset,
        )
        planned = {
            MeasurementType.after_start: after_start,
            MeasurementType.before_end: before_end,
        }
        for m_type, planned_at in planned.items():
            if m_type in existing:
                continue
            db.execute(
                pg_insert(Measurement)
                .values(
                    session_id=session.id,
                    type=m_type,
                    planned_at=planned_at,
                    status=MeasurementStatus.scheduled,
                )
                .on_conflict_do_nothing(constraint="uq_measurements_session_type")
            )
            created += 1
    db.commit()
    return created


def ensure_camera_captures(db: DbSession) -> int:
    """Создаёт задания записи для запланированных замеров.

    No-camera measurements remain available for manually uploaded materials.
    """
    measurements = db.scalars(
        select(Measurement)
        .where(
            Measurement.status == MeasurementStatus.scheduled,
            ~Measurement.captures.any(),
            ~Measurement.upload.has(),
        )
        .options(joinedload(Measurement.session).joinedload(Session.schedule))
        .with_for_update(of=Measurement, skip_locked=True)
    ).unique().all()

    created = 0
    for m in measurements:
        if m.upload is not None:
            continue
        classroom_id = m.session.schedule.classroom_id
        links: list[ClassroomCamera] = []
        if classroom_id is not None:
            links = db.scalars(
                select(ClassroomCamera)
                .join(Camera, Camera.id == ClassroomCamera.camera_id)
                .where(
                    ClassroomCamera.classroom_id == classroom_id,
                    Camera.enabled.is_(True),
                )
                .order_by(ClassroomCamera.priority)
            ).all()

        if not links:
            continue

        for link in links:
            db.execute(
                pg_insert(CameraCapture)
                .values(
                    measurement_id=m.id,
                    camera_id=link.camera_id,
                    planned_at=m.planned_at,
                    duration_seconds=settings.capture_duration_seconds,
                    status=CaptureStatus.pending,
                )
                .on_conflict_do_nothing(constraint="uq_camera_captures_slot")
            )
            created += 1
    db.commit()
    return created


def update_session_lifecycle(db: DbSession) -> None:
    """Переводит занятия по времени: scheduled → in_progress → finished."""
    now = datetime.now(_tz())
    today = now.date()

    sessions = db.scalars(
        select(Session)
        .where(
            Session.date <= today,
            Session.status.in_([SessionStatus.scheduled, SessionStatus.in_progress]),
        )
        .options(joinedload(Session.schedule))
    ).unique().all()

    for session in sessions:
        starts = _local_dt(session.date, session.schedule.starts_at)
        ends = _local_dt(session.date, session.schedule.ends_at)
        if now >= ends:
            session.status = SessionStatus.finished
            session.started_at = session.started_at or starts
            session.finished_at = ends
        elif now >= starts and session.status == SessionStatus.scheduled:
            session.status = SessionStatus.in_progress
            session.started_at = starts
    db.commit()


def reap_expired_leases(db: DbSession) -> None:
    """Bounded recovery independent of schedules and optional camera workers."""
    for table, active in (
        ("camera_captures", "'claimed', 'recording', 'uploading'"),
        ("recognition_jobs", "'processing'"),
    ):
        # Status enum types differ, so update each transition separately.
        db.execute(text(f"""
            UPDATE {table} SET status = 'failed', worker_id = NULL,
                claim_token = NULL, lease_until = NULL, error = 'attempts_exhausted',
                updated_at = now()
                {", finished_at = now()" if table == "recognition_jobs" else ""}
            WHERE attempts >= :max_attempts AND (
                status IN ('pending', 'retry_wait') OR
                (status IN ({active}) AND (lease_until IS NULL OR lease_until <= now())))
        """), {"max_attempts": settings.queue_max_attempts})
        db.execute(text(f"""
            UPDATE {table} SET status = 'retry_wait', worker_id = NULL,
                claim_token = NULL,
                lease_until = now() + make_interval(secs =>
                    least(900.0, 30.0 * power(2, least(greatest(attempts - 1, 0), 5)))
                    * (0.5 + random() * 0.5)),
                error = 'lease_expired', updated_at = now()
            WHERE status IN ({active}) AND (lease_until IS NULL OR lease_until <= now())
                AND attempts < :max_attempts
        """), {"max_attempts": settings.queue_max_attempts})
        db.execute(text(f"""
            UPDATE {table} SET status = 'pending', worker_id = NULL,
                claim_token = NULL, lease_until = NULL, updated_at = now()
            WHERE status = 'retry_wait' AND lease_until <= now()
                AND attempts < :max_attempts
        """), {"max_attempts": settings.queue_max_attempts})
    db.commit()


def fail_stale_pending_captures(db: DbSession) -> None:
    """Помечает ошибкой записи, которые никто не забрал вовремя."""
    deadline = datetime.now(timezone.utc) - timedelta(
        minutes=settings.capture_pending_timeout_minutes
    )
    db.execute(
        update(CameraCapture)
        .where(
            CameraCapture.status == CaptureStatus.pending,
            CameraCapture.planned_at < deadline,
        )
        .values(
            status=CaptureStatus.failed,
            error="задание не было получено capture-узлом",
            updated_at=datetime.now(timezone.utc),
        )
    )
    db.commit()


def run_tick(connection=None) -> None:
    """Один проход scheduler. Каждый шаг изолирован от сбоев остальных."""
    steps = (
        ("sessions", ensure_sessions_horizon),
        ("measurements", ensure_measurements),
        ("captures", ensure_camera_captures),
        ("lifecycle", update_session_lifecycle),
        ("aggregate", aggregation.aggregate_ready_measurements),
        ("finalize", aggregation.finalize_finished_sessions),
    )
    for name, step in steps:
        db = DbSession(bind=connection) if connection is not None else SessionLocal()
        try:
            step(db)
        except Exception:
            db.rollback()
            logger.exception("Scheduler: шаг %s завершился ошибкой", name)
            raise
        finally:
            db.close()
