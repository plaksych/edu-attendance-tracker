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
import threading
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
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
    RecognitionJob,
    RecognitionStatus,
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
        planned = {
            MeasurementType.after_start: _local_dt(session.date, session.schedule.starts_at)
            + offset,
            MeasurementType.before_end: _local_dt(session.date, session.schedule.ends_at)
            - offset,
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

    Если у аудитории нет активных камер, замер сразу помечается ошибкой.
    """
    measurements = db.scalars(
        select(Measurement)
        .where(
            Measurement.status == MeasurementStatus.scheduled,
            ~Measurement.captures.any(),
        )
        .options(joinedload(Measurement.session).joinedload(Session.schedule))
    ).unique().all()

    created = 0
    for m in measurements:
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
            m.status = MeasurementStatus.failed
            m.error = "в аудитории нет активной камеры"
            m.completed_at = datetime.now(timezone.utc)
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
    """Возвращает в очередь задания, у которых истёк lease или пауза перед повтором."""
    now = datetime.now(timezone.utc)
    max_attempts = settings.queue_max_attempts

    # Записи: зависшие активные задания
    db.execute(
        update(CameraCapture)
        .where(
            CameraCapture.status.in_(
                [CaptureStatus.claimed, CaptureStatus.recording, CaptureStatus.uploading]
            ),
            CameraCapture.lease_until.isnot(None),
            CameraCapture.lease_until < now,
            CameraCapture.attempts < max_attempts,
        )
        .values(
            status=CaptureStatus.pending,
            worker_id=None,
            lease_until=None,
            error="lease истёк, задание возвращено в очередь",
            updated_at=now,
        )
    )
    db.execute(
        update(CameraCapture)
        .where(
            CameraCapture.status.in_(
                [CaptureStatus.claimed, CaptureStatus.recording, CaptureStatus.uploading]
            ),
            CameraCapture.lease_until.isnot(None),
            CameraCapture.lease_until < now,
            CameraCapture.attempts >= max_attempts,
        )
        .values(
            status=CaptureStatus.failed,
            error="lease истёк, попытки исчерпаны",
            updated_at=now,
        )
    )
    # Записи: пауза перед повтором закончилась
    db.execute(
        update(CameraCapture)
        .where(
            CameraCapture.status == CaptureStatus.retry_wait,
            CameraCapture.lease_until.isnot(None),
            CameraCapture.lease_until < now,
        )
        .values(status=CaptureStatus.pending, worker_id=None, lease_until=None, updated_at=now)
    )

    # Распознавание: аналогично
    db.execute(
        update(RecognitionJob)
        .where(
            RecognitionJob.status == RecognitionStatus.processing,
            RecognitionJob.lease_until.isnot(None),
            RecognitionJob.lease_until < now,
            RecognitionJob.attempts < max_attempts,
        )
        .values(
            status=RecognitionStatus.pending,
            worker_id=None,
            lease_until=None,
            error="lease истёк, задание возвращено в очередь",
            updated_at=now,
        )
    )
    db.execute(
        update(RecognitionJob)
        .where(
            RecognitionJob.status == RecognitionStatus.processing,
            RecognitionJob.lease_until.isnot(None),
            RecognitionJob.lease_until < now,
            RecognitionJob.attempts >= max_attempts,
        )
        .values(
            status=RecognitionStatus.failed,
            error="lease истёк, попытки исчерпаны",
            finished_at=now,
            updated_at=now,
        )
    )
    db.execute(
        update(RecognitionJob)
        .where(
            RecognitionJob.status == RecognitionStatus.retry_wait,
            RecognitionJob.lease_until.isnot(None),
            RecognitionJob.lease_until < now,
        )
        .values(status=RecognitionStatus.pending, worker_id=None, lease_until=None, updated_at=now)
    )
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


def run_tick() -> None:
    """Один проход scheduler. Каждый шаг изолирован от сбоев остальных."""
    steps = (
        ("sessions", ensure_sessions_horizon),
        ("measurements", ensure_measurements),
        ("captures", ensure_camera_captures),
        ("lifecycle", update_session_lifecycle),
        ("leases", reap_expired_leases),
        ("stale", fail_stale_pending_captures),
        ("aggregate", aggregation.aggregate_ready_measurements),
        ("finalize", aggregation.finalize_finished_sessions),
    )
    for name, step in steps:
        db = SessionLocal()
        try:
            step(db)
        except Exception:
            db.rollback()
            logger.exception("Scheduler: шаг %s завершился ошибкой", name)
        finally:
            db.close()


class SchedulerThread(threading.Thread):
    def __init__(self) -> None:
        super().__init__(name="measurement-scheduler", daemon=True)
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        logger.info(
            "Measurement Scheduler запущен: горизонт %s дней, интервал %s с",
            settings.schedule_horizon_days,
            settings.scheduler_interval_seconds,
        )
        while not self._stop_event.is_set():
            run_tick()
            self._stop_event.wait(settings.scheduler_interval_seconds)
        logger.info("Measurement Scheduler остановлен")
