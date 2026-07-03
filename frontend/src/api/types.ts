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

export interface Classroom {
  id: number
  number: string
  capacity: number | null
  camera_url: string | null
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

export type SessionStatus = 'scheduled' | 'in_progress' | 'finished'

export interface Attendance {
  expected_count: number
  detected_avg: number
  detected_max: number
  snapshots_count: number
  attendance_rate: number | null
}

export interface Session {
  id: number
  date: string
  status: SessionStatus
  started_at: string | null
  finished_at: string | null
  schedule: ScheduleItem
  attendance: Attendance | null
}

export interface Snapshot {
  id: number
  captured_at: string
  person_count: number
  confidence: number | null
  frame_path: string | null
}

export interface SessionWithSnapshots extends Session {
  snapshots: Snapshot[]
}

export interface SummaryStats {
  groups: number
  teachers: number
  disciplines: number
  classrooms: number
  sessions_total: number
  sessions_today: number
  sessions_finished: number
  avg_attendance_rate: number | null
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
  breakdown: BreakdownItem[]
}

export interface TimelinePoint {
  date: string
  avg_rate: number | null
  detected_avg: number | null
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
