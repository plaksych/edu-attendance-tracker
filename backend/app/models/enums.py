import enum


class CameraAggregationMode(str, enum.Enum):
    """Как объединять результаты камер одной аудитории.

    single         — одна камера;
    maximum        — зоны обзора пересекаются, берётся максимум;
    sum            — зоны не пересекаются, результаты суммируются;
    primary_backup — основная камера, резервная используется при сбое.
    """

    single = "single"
    maximum = "maximum"
    sum = "sum"
    primary_backup = "primary_backup"


class CameraRole(str, enum.Enum):
    primary = "primary"
    secondary = "secondary"
    backup = "backup"


class MeasurementType(str, enum.Enum):
    """after_start — через 15 минут после начала; before_end — за 15 минут до конца."""

    after_start = "after_start"
    before_end = "before_end"


class MeasurementStatus(str, enum.Enum):
    scheduled = "scheduled"
    capturing = "capturing"
    recognizing = "recognizing"
    completed = "completed"
    partially_completed = "partially_completed"
    failed = "failed"
    cancelled = "cancelled"


class CaptureStatus(str, enum.Enum):
    pending = "pending"
    claimed = "claimed"
    recording = "recording"
    uploading = "uploading"
    completed = "completed"
    retry_wait = "retry_wait"
    failed = "failed"
    cancelled = "cancelled"


class RecognitionStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    retry_wait = "retry_wait"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class RecognitionMediaType(str, enum.Enum):
    """Тип входного файла для самостоятельного задания распознавания."""

    image = "image"
    video = "video"


class AttendanceCalculationStatus(str, enum.Enum):
    """complete — оба замера успешны; partial — один; failed — ни одного."""

    complete = "complete"
    partial = "partial"
    failed = "failed"
