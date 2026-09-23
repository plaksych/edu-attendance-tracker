"""Агрегация результатов распознавания.

Двухступенчатая схема:
1) результаты камер одного замера сводятся в measurement.final_people_count
   по режиму аудитории (single / maximum / sum / primary_backup);
2) два замера занятия сводятся в attendance_records.
"""

import logging
from datetime import datetime, timedelta, timezone
from statistics import mean
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select
from sqlalchemy.orm import Session as DbSession, joinedload

from app.models import (
    AttendanceCalculationStatus,
    AttendanceRecord,
    CameraAggregationMode,
    CameraCapture,
    CameraRole,
    CaptureStatus,
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
from app.models.measurement import MeasurementResultSource

logger = logging.getLogger(__name__)

CAPTURE_TERMINAL = {
    CaptureStatus.completed,
    CaptureStatus.failed,
    CaptureStatus.cancelled,
}
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
MEASUREMENT_COUNTED = {
    MeasurementStatus.completed,
    MeasurementStatus.partially_completed,
}


def _pick_final(
    mode: CameraAggregationMode,
    results: dict[int, RecognitionResult],
    captures: dict[int, CameraCapture],
) -> tuple[int, float | None, set[int]]:
    """Return count, confidence and counted result IDs using frozen configuration."""

    def by_priority(camera_id: int) -> tuple[bool, int, int]:
        priority = captures[camera_id].priority_snapshot
        return priority is None, priority if priority is not None else 0, camera_id

    ordered = sorted(results.items(), key=lambda item: by_priority(item[0]))
    counts = [r.people_count for _, r in ordered]
    confidences = [
        r.average_confidence for _, r in ordered if r.average_confidence is not None
    ]
    overall_confidence = round(mean(confidences), 4) if confidences else None

    if mode == CameraAggregationMode.maximum:
        chosen = max(ordered, key=lambda item: item[1].people_count)[1]
        return chosen.people_count, overall_confidence, {chosen.id}
    if mode == CameraAggregationMode.sum:
        zones = [captures[camera_id].zone_code_snapshot for camera_id in results]
        if any(not zone for zone in zones) or len(set(zones)) != len(zones):
            raise ValueError("camera_zones_not_distinct")
        return (
            sum(counts),
            overall_confidence,
            {result.id for result in results.values()},
        )

    if mode == CameraAggregationMode.primary_backup:
        primary = next(
            (
                r
                for camera_id, r in ordered
                if captures[camera_id].role_snapshot == CameraRole.primary.value
            ),
            None,
        )
        backup = next(
            (
                r
                for camera_id, r in ordered
                if captures[camera_id].role_snapshot != CameraRole.primary.value
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
        return chosen.people_count, chosen.average_confidence, {chosen.id}

    # single: результат камеры с наивысшим приоритетом
    first = ordered[0][1]
    return first.people_count, first.average_confidence, {first.id}


def _record_sources(measurement: Measurement, results, counted: set[int]) -> None:
    measurement.source_results = [
        MeasurementResultSource(result=result, used_for_count=result.id in counted)
        for result in results
    ]
    measurement.source_reference_status = "recorded"


def _missing_input_expired(measurement: Measurement, now: datetime) -> bool:
    """An ended session gets an explicit, configurable late-upload grace period."""
    session = measurement.session
    if session.status != SessionStatus.finished:
        return False
    ended = session.finished_at or datetime.combine(
        session.date, session.schedule.ends_at, tzinfo=ZoneInfo(settings.timezone)
    )
    if ended.tzinfo is None:
        ended = ended.replace(tzinfo=timezone.utc)
    grace = settings.measurement_input_grace_seconds
    return now >= ended + timedelta(seconds=grace)


def aggregate_ready_measurements(db: DbSession) -> int:
    """Закрывает замеры, у которых записи и распознавание завершились.

    Возвращает количество закрытых замеров.
    """
    now = datetime.now(timezone.utc)
    # Match cancellation/upload lock order: session first, measurement second.
    session_ids = db.scalars(
        select(Session.id)
        .where(
            Session.status != SessionStatus.cancelled,
            Session.measurements.any(
                and_(
                    Measurement.status.notin_(MEASUREMENT_TERMINAL),
                    Measurement.planned_at <= now,
                )
            ),
        )
        .order_by(Session.id)
        .with_for_update(of=Session, skip_locked=True)
    ).all()
    if not session_ids:
        db.commit()
        return 0

    # Будущие замеры агрегировать нечего: до planned_at их задания ещё pending
    measurements = (
        db.scalars(
            select(Measurement)
            .where(
                Measurement.status.notin_(MEASUREMENT_TERMINAL),
                Measurement.planned_at <= now,
                Measurement.session_id.in_(session_ids),
            )
            .options(
                joinedload(Measurement.session).joinedload(Session.schedule),
                joinedload(Measurement.captures)
                .joinedload(CameraCapture.recognition_job)
                .joinedload(RecognitionJob.result),
            )
            .with_for_update(of=Measurement, skip_locked=True)
            .execution_options(populate_existing=True)
        )
        .unique()
        .all()
    )

    closed = 0
    for m in measurements:
        captures = m.captures
        if not captures:
            upload = m.upload
            job = upload.job if upload else None
            if job and job.status == RecognitionStatus.completed and job.result:
                m.final_people_count = job.result.people_count
                m.confidence = job.result.average_confidence
                m.status = MeasurementStatus.completed
                m.completed_at = now
                m.error = None
                m.aggregation_method = CameraAggregationMode.single
                _record_sources(m, [job.result], {job.result.id})
                closed += 1
            elif job and job.status in JOB_TERMINAL:
                m.status = MeasurementStatus.failed
                m.completed_at = now
                m.error = "Материал не обработан"
                _record_sources(m, [], set())
                closed += 1
            elif job:
                m.status = MeasurementStatus.recognizing
            elif upload is None and _missing_input_expired(m, now):
                m.status = MeasurementStatus.failed
                m.final_people_count = None
                m.confidence = None
                m.completed_at = now
                m.error = "missing_input_deadline"
                m.source_reference_status = "missing_input"
                closed += 1
            continue

        captures_terminal = all(c.status in CAPTURE_TERMINAL for c in captures)
        jobs_pending = any(
            c.status == CaptureStatus.completed
            and (
                c.recognition_job is None
                or c.recognition_job.status not in JOB_TERMINAL
            )
            for c in captures
        )

        if not captures_terminal:
            in_work = any(
                c.status
                in (
                    CaptureStatus.claimed,
                    CaptureStatus.recording,
                    CaptureStatus.uploading,
                )
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
            _record_sources(m, [], set())
            closed += 1
            continue

        mode = CameraAggregationMode(m.session.aggregation_mode_snapshot)
        m.aggregation_method = mode
        try:
            final_count, confidence, counted = _pick_final(
                mode, results, {capture.camera_id: capture for capture in captures}
            )
        except ValueError as exc:
            m.status = MeasurementStatus.failed
            m.final_people_count = None
            m.confidence = None
            m.error = str(exc)
            m.completed_at = now
            _record_sources(m, results.values(), set())
            closed += 1
            continue

        m.final_people_count = final_count
        m.confidence = confidence
        m.error = "; ".join(errors) if errors else None
        m.status = (
            MeasurementStatus.completed
            if len(results) == len(captures)
            else MeasurementStatus.partially_completed
        )
        m.completed_at = now
        _record_sources(m, results.values(), counted)
        closed += 1

    db.commit()
    return closed


def finalize_finished_sessions(db: DbSession) -> int:
    """Формирует attendance_records для завершённых занятий с закрытыми замерами."""
    sessions = (
        db.scalars(
            select(Session)
            .where(
                Session.status == SessionStatus.finished,
                ~Session.attendance.has(),
            )
            .options(
                joinedload(Session.measurements),
                joinedload(Session.schedule).joinedload(Schedule.group),
            )
            .with_for_update(of=Session, skip_locked=True)
            .execution_options(populate_existing=True)
        )
        .unique()
        .all()
    )

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

        expected = (
            session.expected_count_snapshot
            if session.expected_count_snapshot is not None
            else 0
        )
        detected_average = round(mean(values), 2) if values else None
        rate = None
        if detected_average is not None and expected > 0:
            rate = round(detected_average / expected, 4)

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
