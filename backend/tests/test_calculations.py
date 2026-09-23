from datetime import datetime, timezone

import pytest

from test_access import world
from app.models import (AttendanceRecord, Group, Measurement, Session, SessionStatus)
from app.services.aggregation import finalize_finished_sessions
from app.services.stats import summary


def test_weighted_ratio_uses_expected_counts_not_mean_of_percentages(world):
    _, factory = world
    with factory() as db:
        db.add_all([
            AttendanceRecord(session_id=1, expected_count=10, detected_average=10,
                attendance_rate=1, calculation_status="complete"),
            AttendanceRecord(session_id=2, expected_count=100, detected_average=0,
                attendance_rate=0, calculation_status="complete"),
        ])
        db.commit()
        assert summary(db).avg_attendance_rate == pytest.approx(0.0909)


def test_snapshot_survives_group_change_and_overcapacity_remains_visible(world):
    _, factory = world
    with factory() as db:
        session = db.get(Session,1)
        session.status = SessionStatus.finished
        session.schedule.group.students_count = 100
        db.add_all([Measurement(session_id=1,type=kind,planned_at=datetime.now(timezone.utc),
            status="completed",final_people_count=25,aggregation_method="single")
            for kind in ("after_start", "before_end")])
        db.commit()
        assert finalize_finished_sessions(db) == 1
        db.refresh(session)
        assert session.attendance.expected_count == 20
        assert session.attendance.attendance_rate == 1.25


def test_zero_detection_is_not_missing_measurement(world):
    _, factory = world
    with factory() as db:
        session = db.get(Session,1)
        session.status = SessionStatus.finished
        db.add(Measurement(session_id=1,type="after_start",planned_at=datetime.now(timezone.utc),
            status="completed",final_people_count=0,aggregation_method="single"))
        db.add(Measurement(session_id=1,type="before_end",planned_at=datetime.now(timezone.utc),
            status="failed",aggregation_method="single"))
        db.commit()
        finalize_finished_sessions(db)
        db.refresh(session)
        assert session.attendance.detected_average == 0
        assert session.attendance.calculation_status.value == "partial"
