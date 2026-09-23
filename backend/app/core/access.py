"""Apply object scope to ORM reads, including joins, aggregates and lazy loaders."""

from sqlalchemy import event, or_, select
from sqlalchemy.orm import Session as DbSession, with_loader_criteria

from app.models import (
    AttendanceRecord,
    CameraCapture,
    Camera,
    ClassroomCamera,
    Classroom,
    Discipline,
    Group,
    Measurement,
    RecognitionJob,
    RecognitionResult,
    RecognitionUpload,
    Schedule,
    Session,
    Teacher,
)
from app.models.security import AuditEvent


@event.listens_for(DbSession, "before_flush")
def record_mutations(db, flush_context, instances):
    request = db.info.get("audit_request")
    if request is None:
        return
    for action, objects in (
        ("create", db.new),
        ("update", db.dirty),
        ("delete", db.deleted),
    ):
        for obj in list(objects):
            if obj.__class__.__module__.endswith(".security"):
                continue
            if action == "update" and not db.is_modified(
                obj, include_collections=False
            ):
                continue
            db.add(
                AuditEvent(
                    actor_id=request.state.user.id,
                    action=action,
                    object_type=obj.__tablename__,
                    object_id=str(getattr(obj, "id", "new")),
                    request_id=request.state.request_id,
                )
            )


@event.listens_for(DbSession, "do_orm_execute")
def restrict_teacher_reads(state):
    groups = state.session.info.get("allowed_groups")
    if groups is None or not state.is_select:
        return
    # Core subqueries deliberately avoid recursively applying ORM criteria.
    schedule = Schedule.__table__
    sessions = Session.__table__
    measurements = Measurement.__table__
    captures = CameraCapture.__table__
    uploads = RecognitionUpload.__table__
    jobs = RecognitionJob.__table__
    schedule_ids = select(schedule.c.id).where(schedule.c.group_id.in_(groups))
    classroom_ids = select(schedule.c.classroom_id).where(
        schedule.c.group_id.in_(groups)
    )
    camera_links = ClassroomCamera.__table__
    session_ids = select(sessions.c.id).where(sessions.c.schedule_id.in_(schedule_ids))
    measurement_ids = select(measurements.c.id).where(
        measurements.c.session_id.in_(session_ids)
    )
    capture_ids = select(captures.c.id).where(
        captures.c.measurement_id.in_(measurement_ids)
    )
    upload_scope = or_(
        uploads.c.owner_id == state.session.info["user_id"],
        uploads.c.session_id.in_(session_ids),
    )
    upload_ids = select(uploads.c.id).where(upload_scope)
    job_scope = or_(
        jobs.c.camera_capture_id.in_(capture_ids), jobs.c.upload_id.in_(upload_ids)
    )
    criteria = [
        (Group, Group.id.in_(groups)),
        (Schedule, Schedule.group_id.in_(groups)),
        (Session, Session.id.in_(session_ids)),
        (Measurement, Measurement.id.in_(measurement_ids)),
        (CameraCapture, CameraCapture.id.in_(capture_ids)),
        (
            Camera,
            Camera.id.in_(
                select(camera_links.c.camera_id).where(
                    camera_links.c.classroom_id.in_(classroom_ids)
                )
            ),
        ),
        (RecognitionUpload, RecognitionUpload.id.in_(upload_ids)),
        (RecognitionJob, RecognitionJob.id.in_(select(jobs.c.id).where(job_scope))),
        (
            RecognitionResult,
            RecognitionResult.recognition_job_id.in_(
                select(jobs.c.id).where(job_scope)
            ),
        ),
        (AttendanceRecord, AttendanceRecord.session_id.in_(session_ids)),
        (
            Teacher,
            Teacher.id.in_(
                select(schedule.c.teacher_id).where(schedule.c.group_id.in_(groups))
            ),
        ),
        (
            Classroom,
            Classroom.id.in_(
                select(schedule.c.classroom_id).where(schedule.c.group_id.in_(groups))
            ),
        ),
        (
            Discipline,
            Discipline.id.in_(
                select(schedule.c.discipline_id).where(schedule.c.group_id.in_(groups))
            ),
        ),
    ]
    state.statement = state.statement.options(
        *[
            with_loader_criteria(model, criterion, include_aliases=True)
            for model, criterion in criteria
        ]
    )
