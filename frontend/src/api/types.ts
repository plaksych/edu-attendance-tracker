export interface Group {
  id: number
  name: string
  course: number
  faculty: string | null
  students_count: number
}

export interface Teacher {
  id: number
  full_name: string
  email: string | null
  department: string | null
}

export interface Discipline {
  id: number
  name: string
}

export type AggregationMode = 'single' | 'maximum' | 'sum' | 'primary_backup'
export type CameraRole = 'primary' | 'secondary' | 'backup'

export interface CameraBrief {
  id: number
  name: string
}

export interface Camera {
  id: number
  name: string
  rtsp_url: string
  capture_group: string
  enabled: boolean
  classroom_number: string | null
  created_at: string
}

export interface ClassroomCameraLink {
  camera: CameraBrief
  role: CameraRole
  priority: number
  zone_code: string | null
  enabled: boolean
}

export interface Classroom {
  id: number
  number: string
  capacity: number | null
  aggregation_mode: AggregationMode
  cameras: ClassroomCameraLink[]
}

export type WeekType = 'every' | 'white' | 'green'

export interface ScheduleItem {
  id: number
  weekday: number
  starts_at: string
  ends_at: string
  week_type: WeekType
  lesson_type: string | null
  group: Group
  teacher: Teacher | null
  discipline: Discipline
  classroom: Classroom | null
}

export interface WeekTypeInfo {
  date: string
  week_type: WeekType
}

export type SessionStatus = 'scheduled' | 'in_progress' | 'finished' | 'cancelled'
export type MeasurementType = 'after_start' | 'before_end'
export type MeasurementStatus =
  | 'scheduled'
  | 'capturing'
  | 'recognizing'
  | 'completed'
  | 'partially_completed'
  | 'failed'
  | 'cancelled'
export type CaptureStatus =
  | 'pending'
  | 'claimed'
  | 'recording'
  | 'uploading'
  | 'completed'
  | 'retry_wait'
  | 'failed'
  | 'cancelled'
export type CalculationStatus = 'complete' | 'partial' | 'failed'

export interface RecognitionResult {
  people_count: number
  detected_median: number
  detected_percentile_75: number
  detected_max: number
  average_confidence: number | null
  count_stddev: number
  sampled_frames: number
  source_frames: number
  source_duration_ms: number
  representative_frame_ms: number
  absolute_error: number | null
  relative_error: number | null
  within_tolerance: boolean | null
  media_expires_at: string | null
}

export type RecognitionStatus =
  | 'pending'
  | 'processing'
  | 'retry_wait'
  | 'completed'
  | 'failed'
  | 'cancelled'

export type RecognitionMediaType = 'image' | 'video'

export interface RecognitionUploadJob {
  id: number
  status: RecognitionStatus
  attempts: number
  model_name: string
  model_version: string
  sample_rate_fps: number
  confidence_threshold: number
  started_at: string | null
  finished_at: string | null
  error: string | null
  result: RecognitionResult | null
}

export interface RecognitionUpload {
  id: number
  filename: string
  media_type: RecognitionMediaType
  content_type: string
  size_bytes: number
  label: string | null
  reference_people_count: number | null
  created_at: string
  job: RecognitionUploadJob
}

export interface RecognitionUploadMedia {
  source_url: string | null
  source_unavailable_reason: string | null
  annotated_url: string | null
  annotated_unavailable_reason: string | null
  expires_in_seconds: number
}

export interface RecognitionEvaluationSummary {
  checked_materials: number
  within_tolerance_count: number
  mean_absolute_error: number | null
  median_absolute_error: number | null
  max_absolute_error: number | null
  mean_relative_error: number | null
}

export interface Capture {
  id: number
  camera: CameraBrief
  status: CaptureStatus
  planned_at: string
  attempts: number
  size_bytes: number | null
  duration_ms: number | null
  error: string | null
  has_video: boolean
  result: RecognitionResult | null
}

export interface Measurement {
  id: number
  type: MeasurementType
  planned_at: string
  status: MeasurementStatus
  final_people_count: number | null
  confidence: number | null
  aggregation_method: AggregationMode
  error: string | null
}

export interface MeasurementDetail extends Measurement {
  captures: Capture[]
}

export interface Attendance {
  expected_count: number
  after_start_count: number | null
  before_end_count: number | null
  detected_average: number | null
  detected_max: number | null
  attendance_rate: number | null
  calculation_status: CalculationStatus
  calculated_at: string | null
}

export interface Session {
  id: number
  date: string
  status: SessionStatus
  started_at: string | null
  finished_at: string | null
  schedule: ScheduleItem
  attendance: Attendance | null
  measurements: Measurement[]
}

export interface SessionDetail extends Session {
  measurements: MeasurementDetail[]
}

export interface CaptureMedia {
  video_url: string | null
  video_unavailable_reason: string | null
  annotated_url: string | null
  annotated_unavailable_reason: string | null
  expires_in_seconds: number
}

export interface SummaryStats {
  groups: number
  teachers: number
  disciplines: number
  classrooms: number
  cameras: number
  sessions_total: number
  sessions_today: number
  sessions_finished: number
  avg_attendance_rate: number | null
  records_complete: number
  records_partial: number
  records_failed: number
}

export interface BreakdownItem {
  id: number
  name: string
  sessions: number
  avg_rate: number | null
  avg_detected: number | null
}

export interface EntityStats {
  id: number
  name: string
  sessions_finished: number
  avg_rate: number | null
  avg_detected: number | null
  records_complete: number
  records_partial: number
  records_failed: number
  breakdown: BreakdownItem[]
}

export interface TimelinePoint {
  date: string
  avg_rate: number | null
  avg_detected: number | null
  expected: number | null
}

export interface GroupTimeline {
  group_id: number
  group_name: string
  points: TimelinePoint[]
}

export interface ImportResult {
  created: number
  skipped: number
  errors: string[]
}
