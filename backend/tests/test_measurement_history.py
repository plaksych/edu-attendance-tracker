"""Historical camera interpretation, finalized sources and missing-input deadlines."""

from datetime import datetime, timedelta, timezone
import os
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.models import (
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
    RecognitionUpload,
    Session,
    SessionStatus,
)
from app.schemas.session import MeasurementRead
from app.models.measurement import MeasurementResultSource
from app.services import aggregation
from app.services.aggregation import (
    aggregate_ready_measurements,
    finalize_finished_sessions,
)
from app.services.scheduler import ensure_camera_captures
from test_access import login


def test_missing_input_grace_setting_is_configurable_and_bounded(monkeypatch):
    from app.core.config import Settings

    monkeypatch.delenv("MEASUREMENT_INPUT_GRACE_SECONDS", raising=False)
    assert (
        Settings(_env_file=None, environment="test").measurement_input_grace_seconds
        == 3600
    )
    for seconds in (0, 604800):
        monkeypatch.setenv("MEASUREMENT_INPUT_GRACE_SECONDS", str(seconds))
        assert (
            Settings(_env_file=None, environment="test").measurement_input_grace_seconds
            == seconds
        )
    for seconds in (-1, 604801):
        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                environment="test",
                measurement_input_grace_seconds=seconds,
            )


def measurement(db, kind="after_start", **kwargs):
    item = Measurement(
        session_id=1,
        type=kind,
        planned_at=datetime.now(timezone.utc) - timedelta(hours=3),
        **kwargs,
    )
    db.add(item)
    db.flush()
    return item


def result_for(job, count):
    job.status = RecognitionStatus.completed
    job.result = RecognitionResult(
        people_count=count,
        detected_median=count,
        detected_percentile_75=count,
        detected_max=count,
        average_confidence=0.9,
        sampled_frames=1,
        representative_frame_ms=0,
        annotated_bucket="private",
        annotated_object_key=f"result/{count}.jpg",
    )
    return job.result


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("single", 5),
        ("primary_backup", 5),
        ("sum", 24),
        ("maximum", 19),
    ],
)
def test_camera_edits_do_not_reinterpret_snapshotted_capture(world, mode, expected):
    _, factory = world
    with factory() as db:
        session = db.get(Session, 1)
        session.aggregation_mode_snapshot = mode
        item = measurement(db)
        item_id = item.id
        links = []
        for number, role in ((1, CameraRole.primary), (2, CameraRole.backup)):
            camera = Camera(name=f"camera-{number}", rtsp_url="encrypted:test")
            link = ClassroomCamera(
                classroom_id=session.schedule.classroom_id,
                camera=camera,
                role=role,
                priority=number,
                zone_code=f"zone-{number}",
            )
            db.add(link)
            links.append(link)
        db.commit()
        assert ensure_camera_captures(db) == 2
        captures = db.scalars(
            select(CameraCapture).order_by(CameraCapture.camera_id)
        ).all()
        assert [c.role_snapshot for c in captures] == ["primary", "backup"]
        assert [c.priority_snapshot for c in captures] == [1, 2]
        assert [c.zone_code_snapshot for c in captures] == ["zone-1", "zone-2"]
        assert all(c.snapshot_origin == "captured" for c in captures)
        links[0].role, links[0].priority = CameraRole.backup, 99
        links[1].role, links[1].priority = CameraRole.primary, 1
        for link in links:
            link.zone_code = "edited-overlapping-zone"
        for capture, count in zip(captures, (5, 19)):
            capture.status = CaptureStatus.completed
            capture.recognition_job = RecognitionJob(status=RecognitionStatus.completed)
            result_for(capture.recognition_job, count)
        db.commit()
    with factory() as db:
        assert aggregate_ready_measurements(db) == 1
        item = db.get(Measurement, item_id)
        assert item.final_people_count == expected
        assert item.source_reference_status == "recorded"
        assert len(item.source_results) == 2
        counted = [
            source.people_count
            for source in item.source_results
            if source.used_for_count
        ]
        assert sorted(counted) == ([5, 19] if mode == "sum" else [expected])
        assert all(
            source.camera_capture_id is not None for source in item.source_results
        )


def test_retry_keeps_final_count_and_explicit_source_discoverable(world):
    client, factory = world
    with factory() as db:
        item = measurement(db)
        item_id = item.id
        upload = db.get(RecognitionUpload, 1)
        upload.measurement_id = item_id
        original = result_for(upload.job, 5)
        db.commit()
        result_id, old_job_id = original.id, upload.job.id
    with factory() as db:
        assert aggregate_ready_measurements(db) == 1
        assert (
            db.get(Measurement, item_id).source_results[0].recognition_result_id
            == result_id
        )

    headers = {**login(client, "teacher"), "Idempotency-Key": "historical-source-retry"}
    response = client.post("/api/v1/recognition/uploads/1/retry", headers=headers)
    assert response.status_code == 202, response.text
    new_job_id = response.json()["job"]["id"]
    assert new_job_id != old_job_id
    with factory() as db:
        result_for(db.get(RecognitionJob, new_job_id), 19)
        db.commit()
        assert aggregate_ready_measurements(db) == 0
        item = db.get(Measurement, item_id)
        assert item.final_people_count == 5
        assert item.source_results[0].recognition_result_id == result_id
        assert item.source_results[0].recognition_job_id == old_job_id
    body = client.get("/api/v1/sessions/1").json()
    source = body["measurements"][0]["source_results"][0]
    assert source["recognition_result_id"] == result_id
    assert source["recognition_job_id"] == old_job_id
    assert source["upload_id"] == 1
    assert source["people_count"] == 5
    assert source["used_for_count"] is True


@pytest.mark.skipif(
    not os.environ.get("BACKEND_TEST_DSN"), reason="PostgreSQL FK enforcement"
)
def test_finalized_source_cannot_be_deleted(world):
    _, factory = world
    with factory() as db:
        item = measurement(db)
        upload = db.get(RecognitionUpload, 1)
        upload.measurement_id = item.id
        original = result_for(upload.job, 5)
        db.commit()
        result_id = original.id
        assert aggregate_ready_measurements(db) == 1
        with pytest.raises(IntegrityError):
            db.execute(
                delete(RecognitionResult).where(RecognitionResult.id == result_id)
            )
            db.commit()
        db.rollback()
        assert db.get(RecognitionResult, result_id) is not None


@pytest.mark.skipif(
    not os.environ.get("BACKEND_TEST_DSN"), reason="PostgreSQL FK enforcement"
)
@pytest.mark.parametrize("deletion_path", ["sql", "orm"])
def test_measurement_with_finalized_source_cannot_be_deleted(world, deletion_path):
    _, factory = world
    with factory() as db:
        item = measurement(db, status=MeasurementStatus.completed, final_people_count=5)
        # Keep the upload unlinked so only the provenance FK can block deletion.
        upload = db.get(RecognitionUpload, 1)
        assert upload.measurement_id is None
        original = result_for(upload.job, 5)
        item.source_results = [
            MeasurementResultSource(result=original, used_for_count=True)
        ]
        item.source_reference_status = "recorded"
        db.commit()
        item_id, result_id = item.id, original.id
        with pytest.raises(IntegrityError) as exc:
            if deletion_path == "orm":
                db.delete(item)
            else:
                db.execute(delete(Measurement).where(Measurement.id == item_id))
            db.commit()
        assert (
            exc.value.orig.diag.constraint_name
            == "measurement_result_sources_measurement_id_fkey"
        )
        db.rollback()
        assert db.get(Measurement, item_id) is not None
        assert db.get(MeasurementResultSource, (item_id, result_id)) is not None


def fixed_clock(monkeypatch):
    now = datetime(2026, 9, 23, 12, tzinfo=timezone.utc)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz else now.replace(tzinfo=None)

    monkeypatch.setattr(aggregation, "datetime", Clock)
    monkeypatch.setattr(
        aggregation,
        "settings",
        SimpleNamespace(measurement_input_grace_seconds=3600, timezone="Europe/Moscow"),
    )
    return now


@pytest.mark.parametrize(
    "status,seconds,closed",
    [
        (SessionStatus.in_progress, 7200, 0),
        (SessionStatus.finished, 3599, 0),
        (SessionStatus.finished, 3600, 1),
    ],
)
def test_missing_input_expires_only_after_ended_session_grace(
    world, monkeypatch, status, seconds, closed
):
    _, factory = world
    now = fixed_clock(monkeypatch)
    with factory() as db:
        session = db.get(Session, 1)
        session.status = status
        session.finished_at = now - timedelta(seconds=seconds)
        item = measurement(db)
        item.planned_at = now - timedelta(hours=3)
        db.commit()
        assert aggregate_ready_measurements(db) == closed
        db.refresh(item)
        assert item.final_people_count is None
        if closed:
            assert item.status == MeasurementStatus.failed
            assert item.error == "missing_input_deadline"
            assert item.source_reference_status == "missing_input"
            assert item.source_results == []
        else:
            assert item.status == MeasurementStatus.scheduled


@pytest.mark.parametrize("first_count", [None, 7])
def test_missing_source_finalizes_failed_or_partial_not_zero(
    world, monkeypatch, first_count
):
    _, factory = world
    now = fixed_clock(monkeypatch)
    with factory() as db:
        session = db.get(Session, 1)
        session.status = SessionStatus.finished
        session.finished_at = now - timedelta(hours=2)
        first = measurement(db)
        if first_count is not None:
            first.status = MeasurementStatus.completed
            first.final_people_count = first_count
        second = measurement(db, "before_end")
        first.planned_at = second.planned_at = now - timedelta(hours=3)
        db.commit()
        aggregate_ready_measurements(db)
        assert finalize_finished_sessions(db) == 1
        db.refresh(session)
        record = session.attendance
        assert record.before_end_count is None
        assert record.detected_average == first_count
        assert record.calculation_status.value == (
            "failed" if first_count is None else "partial"
        )
        assert first.final_people_count == first_count


@pytest.mark.skipif(
    not os.environ.get("BACKEND_TEST_DSN"), reason="PostgreSQL row locks"
)
def test_aggregation_skips_cancelling_session_and_never_resurrects_stale_measurement(
    world,
):
    _, factory = world
    with factory() as db:
        item = measurement(db)
        upload = db.get(RecognitionUpload, 1)
        upload.measurement_id = item.id
        result_for(upload.job, 5)
        db.commit()
        item_id = item.id
    with factory() as cancelling, factory() as worker:
        stale = worker.get(Measurement, item_id)
        assert stale.status == MeasurementStatus.scheduled
        session = cancelling.scalar(
            select(Session).where(Session.id == 1).with_for_update()
        )
        session.status = SessionStatus.cancelled
        item = cancelling.scalar(
            select(Measurement).where(Measurement.id == item_id).with_for_update()
        )
        item.status = MeasurementStatus.cancelled
        cancelling.flush()
        assert aggregate_ready_measurements(worker) == 0
        cancelling.commit()
        assert aggregate_ready_measurements(worker) == 0
        worker.refresh(stale)
        assert stale.status == MeasurementStatus.cancelled
        assert stale.final_people_count is None
        assert stale.source_results == []


def test_response_defaults_preserve_legacy_payloads():
    payload = MeasurementRead.model_validate(
        dict(
            id=1,
            type="after_start",
            planned_at=datetime.now(timezone.utc),
            status="completed",
            final_people_count=5,
            confidence=None,
            aggregation_method="single",
            error=None,
        )
    )
    assert payload.source_reference_status is None
    assert payload.source_results == []


def test_unknown_legacy_priority_has_deterministic_camera_id_fallback():
    results = {
        2: SimpleNamespace(id=12, people_count=19, average_confidence=0.9),
        1: SimpleNamespace(id=11, people_count=5, average_confidence=0.9),
    }
    captures = {
        key: SimpleNamespace(
            priority_snapshot=None, role_snapshot=None, zone_code_snapshot=None
        )
        for key in results
    }
    assert aggregation._pick_final(CameraAggregationMode.single, results, captures) == (
        5,
        0.9,
        {11},
    )


@pytest.mark.parametrize("zones", [(None, "A"), ("A", "A")])
def test_sum_requires_distinct_frozen_zones(zones):
    results = {
        1: SimpleNamespace(id=11, people_count=5, average_confidence=0.9),
        2: SimpleNamespace(id=12, people_count=19, average_confidence=0.9),
    }
    captures = {
        key: SimpleNamespace(priority_snapshot=key, zone_code_snapshot=zones[key - 1])
        for key in results
    }
    with pytest.raises(ValueError, match="camera_zones_not_distinct"):
        aggregation._pick_final(CameraAggregationMode.sum, results, captures)
