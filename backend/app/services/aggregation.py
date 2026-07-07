"""Агрегация результатов распознавания.

Двухступенчатая схема:
1) результаты камер одного замера сводятся в measurement.final_people_count
   по режиму аудитории (single / maximum / sum / primary_backup);
2) два замера занятия сводятся в attendance_records.
"""

import logging
from datetime import datetime, timezone
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession, joinedload

from app.models import (
    AttendanceCalculationStatus,
    AttendanceRecord,
    Camera,
    CameraAggregationMode,
    CameraCapture,
    CameraRole,
    CaptureStatus,
    ClassroomCamera,
    Measurement,
    MeasurementStatus,
    RecognitionJob,
    RecognitionResult,
    RecognitionStatus,
    Schedule,
    Session,
    SessionStatus,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

CAPTURE_TERMINAL = {CaptureStatus.completed, CaptureStatus.failed, CaptureStatus.cancelled}
JOB_TERMINAL = {
    RecognitionStatus.completed,
    RecognitionStatus.failed,
    RecognitionStatus.cancelled,
}
MEASUREMENT_TERMINAL = {
    MeasurementStatus.completed,
    MeasurementStatus.partially_completed,
    MeasurementStatus.failed,
    MeasurementStatus.cancelled,
}
MEASUREMENT_COUNTED = {MeasurementStatus.completed, MeasurementStatus.partially_completed}


def _camera_roles(db: DbSession, measurement: Measurement) -> dict[int, ClassroomCamera]:
    classroom_id = measurement.session.schedule.classroom_id
    if classroom_id is None:
        return {}
    links = db.scalars(
        select(ClassroomCamera).where(ClassroomCamera.classroom_id == classroom_id)
    ).all()
    return {link.camera_id: link for link in links}


def _pick_final(
    mode: CameraAggregationMode,
    results: dict[int, RecognitionResult],
    roles: dict[int, ClassroomCamera],
) -> tuple[int, float | None]:
    """Возвращает (final_people_count, confidence) по режиму объединения камер."""

    def by_priority(camera_id: int) -> int:
        link = roles.get(camera_id)
        return link.priority if link else 99

    ordered = sorted(results.items(), key=lambda item: by_priority(item[0]))
    counts = [r.people_count for _, r in ordered]
    confidences = [
        r.average_confidence for _, r in ordered if r.average_confidence is not None
    ]
    overall_confidence = round(mean(confidences), 4) if confidences else None

    if mode == CameraAggregationMode.maximum:
        return max(counts), overall_confidence
    if mode == CameraAggregationMode.sum:
        return sum(counts), overall_confidence

    if mode == CameraAggregationMode.primary_backup:
        primary = next(
            (
                r
                for camera_id, r in ordered
                if roles.get(camera_id) and roles[camera_id].role == CameraRole.primary
            ),
            None,
        )
        backup = next(
            (
                r
                for camera_id, r in ordered
                if roles.get(camera_id) and roles[camera_id].role != CameraRole.primary
            ),
            None,
        )
        chosen = primary
        if primary is None:
            chosen = backup
        elif (
            backup is not None
            and primary.average_confidence is not None
            and primary.average_confidence < settings.backup_confidence_threshold
        ):
            chosen = backup
        chosen = chosen or ordered[0][1]
        return chosen.people_count, chosen.average_confidence

    # single: результат камеры с наивысшим приоритетом
    first = ordered[0][1]
    return first.people_count, first.average_confidence


def aggregate_ready_measurements(db: DbSession) -> int:
    """Закрывает замеры, у которых записи и распознавание завершились.

    Возвращает количество закрытых замеров.
    """
    # Будущие замеры агрегировать нечего: до planned_at их задания ещё pending
    measurements = db.scalars(
        select(Measurement)
        .where(
            Measurement.status.notin_(MEASUREMENT_TERMINAL),
            Measurement.planned_at <= datetime.now(timezone.utc),
        )
        .options(
            joinedload(Measurement.session).joinedload(Session.schedule),
            joinedload(Measurement.captures)
            .joinedload(CameraCapture.recognition_job)
            .joinedload(RecognitionJob.result),
        )
    ).unique().all()

    closed = 0
    now = datetime.now(timezone.utc)

    for m in measurements:
        captures = m.captures
        if not captures:
            continue

        captures_terminal = all(c.status in CAPTURE_TERMINAL for c in captures)
        jobs_pending = any(
            c.status == CaptureStatus.completed
            and (c.recognition_job is None or c.recognition_job.status not in JOB_TERMINAL)
            for c in captures
        )

        if not captures_terminal:
            in_work = any(
                c.status in (CaptureStatus.claimed, CaptureStatus.recording, CaptureStatus.uploading)
                for c in captures
            )
            if in_work and m.status == MeasurementStatus.scheduled:
                m.status = MeasurementStatus.capturing
                m.started_at = m.started_at or now
            continue

        if jobs_pending:
            if m.status != MeasurementStatus.recognizing:
                m.status = MeasurementStatus.recognizing
                m.started_at = m.started_at or now
            continue

        # Всё завершено — собираем результаты камер
        results: dict[int, RecognitionResult] = {}
        errors: list[str] = []
        for c in captures:
            job = c.recognition_job
            if (
                c.status == CaptureStatus.completed
                and job is not None
                and job.status == RecognitionStatus.completed
                and job.result is not None
            ):
                results[c.camera_id] = job.result
            else:
                reason = c.error or (job.error if job else None) or c.status.value
                errors.append(f"камера {c.camera_id}: {reason}")

        if not results:
            m.status = MeasurementStatus.failed
            m.error = "; ".join(errors) or "нет успешных результатов распознавания"
            m.completed_at = now
            closed += 1
            continue

        roles = _camera_roles(db, m)
        mode = m.session.schedule.classroom.aggregation_mode if m.session.schedule.classroom else CameraAggregationMode.single
        final_count, confidence = _pick_final(mode, results, roles)

        m.final_people_count = final_count
        m.confidence = confidence
        m.aggregation_method = mode
        m.error = "; ".join(errors) if errors else None
        m.status = (
            MeasurementStatus.completed
            if len(results) == len(captures)
            else MeasurementStatus.partially_completed
        )
        m.completed_at = now
        closed += 1

    db.commit()
    return closed


def finalize_finished_sessions(db: DbSession) -> int:
    """Формирует attendance_records для завершённых занятий с закрытыми замерами."""
    sessions = db.scalars(
        select(Session)
        .where(
            Session.status == SessionStatus.finished,
            ~Session.attendance.has(),
        )
        .options(
            joinedload(Session.measurements),
            joinedload(Session.schedule).joinedload(Schedule.group),
        )
    ).unique().all()

    created = 0
    for session in sessions:
        measurements = session.measurements
        if not measurements or any(
            m.status not in MEASUREMENT_TERMINAL for m in measurements
        ):
            continue

        by_type = {m.type.value: m for m in measurements}
        after = by_type.get("after_start")
        before = by_type.get("before_end")

        def counted(m) -> int | None:
            if m is not None and m.status in MEASUREMENT_COUNTED:
                return m.final_people_count
            return None

        after_count = counted(after)
        before_count = counted(before)
        values = [v for v in (after_count, before_count) if v is not None]

        if len(values) == 2:
            status = AttendanceCalculationStatus.complete
        elif len(values) == 1:
            status = AttendanceCalculationStatus.partial
        else:
            status = AttendanceCalculationStatus.failed

        expected = session.schedule.group.students_count
        detected_average = round(mean(values), 2) if values else None
        rate = None
        if detected_average is not None and expected > 0:
            rate = round(min(detected_average / expected, 1.0), 4)

        db.add(
            AttendanceRecord(
                session_id=session.id,
                expected_count=expected,
                after_start_count=after_count,
                before_end_count=before_count,
                detected_average=detected_average,
                detected_max=max(values) if values else None,
                attendance_rate=rate,
                calculation_status=status,
            )
        )
        created += 1

    if created:
        db.commit()
    return created
