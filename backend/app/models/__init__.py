from app.models.attendance import AttendanceRecord
from app.models.cameras import Camera, ClassroomCamera
from app.models.catalog import Classroom, Discipline, Group, Teacher
from app.models.enums import (
    AttendanceCalculationStatus,
    CameraAggregationMode,
    CameraRole,
    CaptureStatus,
    MeasurementStatus,
    MeasurementType,
    RecognitionMediaType,
    RecognitionStatus,
)
from app.models.measurement import CameraCapture, Measurement
from app.models.recognition import RecognitionJob, RecognitionResult, RecognitionUpload
from app.models.schedule import (
    CalendarException,
    Schedule,
    Session,
    SessionStatus,
    WeekType,
)
from app.models.security import (
    AccessGrant,
    AuditEvent,
    LoginAttempt,
    LoginSession,
    User,
)
from app.models.requests import IdempotencyRecord, ImportPreview, RecognitionCorrection
from app.models import physical_schema  # noqa: F401 - Register preserved physical schema.

__all__ = [
    "AccessGrant",
    "AuditEvent",
    "CalendarException",
    "IdempotencyRecord",
    "ImportPreview",
    "LoginAttempt",
    "LoginSession",
    "RecognitionCorrection",
    "User",
    "AttendanceCalculationStatus",
    "AttendanceRecord",
    "Camera",
    "CameraAggregationMode",
    "CameraCapture",
    "CameraRole",
    "CaptureStatus",
    "Classroom",
    "ClassroomCamera",
    "Discipline",
    "Group",
    "Measurement",
    "MeasurementStatus",
    "MeasurementType",
    "RecognitionJob",
    "RecognitionMediaType",
    "RecognitionResult",
    "RecognitionStatus",
    "RecognitionUpload",
    "Schedule",
    "Session",
    "SessionStatus",
    "Teacher",
    "WeekType",
]
