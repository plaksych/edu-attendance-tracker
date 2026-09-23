import type { AggregationMode, Camera, CameraRole, CaptureMedia, Classroom, Discipline, EntityStats, Group, GroupTimeline, ImportResult, RecognitionEvaluationSummary, RecognitionUpload, RecognitionUploadMedia, ScheduleItem, Session, SessionDetail, SummaryStats, Teacher, WeekTypeInfo } from './types'
import { DEMO_DATE, shiftDate } from '../lib/format'

const clone = <T,>(value: T): T => structuredClone(value)
const groups: Group[] = [24, 32, 18].map((count, index) => ({ id: index + 1, name: `Учебная группа ${index + 1}`, course: index + 1, faculty: 'Учебный факультет', students_count: count }))
const teachers: Teacher[] = groups.map(g => ({ id: g.id, full_name: `Преподаватель ${g.id}`, email: null, department: 'Учебная кафедра' }))
const disciplines: Discipline[] = ['Прикладная математика', 'Информационные системы', 'Основы статистики'].map((name, index) => ({ id: index + 1, name }))
const classrooms: Classroom[] = groups.map(g => ({ id: g.id, number: `Д-${100 + g.id}`, capacity: 40, aggregation_mode: 'single', cameras: [] }))
let cameras: Camera[] = []
const schedule: ScheduleItem[] = Array.from({ length: 15 }, (_, index) => {
  const entity = index % 3
  return { id: index + 1, weekday: Math.floor(index / 3) + 1, starts_at: ['09:00:00', '11:00:00', '14:00:00'][entity], ends_at: ['10:30:00', '12:30:00', '15:30:00'][entity], week_type: 'every', lesson_type: 'практика', group: groups[entity], teacher: teachers[entity], discipline: disciplines[(entity + Math.floor(index / 3)) % 3], classroom: classrooms[entity] }
})
const cancelled = new Set<number>()
function find<T extends { id: number }>(items: T[], id: number): T {
  const item = items.find(value => value.id === id)
  if (!item) throw new Error('Запись не найдена')
  return item
}
function scheduleOn(date: string) {
  const weekday = new Date(`${date}T12:00:00Z`).getUTCDay() || 7
  return schedule.filter(item => item.weekday === weekday)
}
function makeSession(item: ScheduleItem, date: string): SessionDetail {
  const id = Number(date.replace(/-/g, '')) * 100 + item.id
  const variation = (item.id + Number(date.slice(-2))) % 7
  const expected = item.group.students_count
  const after = variation === 0 ? 0 : Math.round(expected * (0.65 + variation * 0.06))
  const partial = variation === 2
  const failed = variation === 3
  const before = partial || failed ? null : Math.max(0, after - 2)
  const isCancelled = cancelled.has(id)
  const counts = [failed || isCancelled ? null : after, isCancelled ? null : before]
  const measured = counts.filter((value): value is number => value !== null)
  const average = measured.length ? measured.reduce((sum, value) => sum + value, 0) / measured.length : null
  return {
    id, date, provenance: 'demo_fixture', schedule: clone(item), status: isCancelled ? 'cancelled' : 'finished',
    started_at: `${date}T${item.starts_at}+03:00`, finished_at: `${date}T${item.ends_at}+03:00`,
    attendance: isCancelled ? null : { expected_count: expected, after_start_count: counts[0], before_end_count: counts[1], detected_average: average, detected_max: measured.length ? Math.max(...measured) : null, attendance_rate: average !== null && expected > 0 ? average / expected : null, calculation_status: failed ? 'failed' : partial ? 'partial' : 'complete', calculated_at: `${date}T16:00:00+03:00` },
    measurements: counts.map((count, index) => ({ id: id * 10 + index, provenance: 'demo_fixture', type: index === 0 ? 'after_start' : 'before_end', planned_at: `${date}T${index === 0 ? item.starts_at : item.ends_at}+03:00`, status: isCancelled ? 'cancelled' : count === null ? 'failed' : 'completed', final_people_count: count, confidence: null, aggregation_method: 'single', error: count === null && !isCancelled ? 'Учебный сценарий: материал отсутствует' : null, captures: [] })),
  }
}
function history() {
  return Array.from({ length: 14 }, (_, i) => shiftDate(DEMO_DATE, i - 13)).flatMap(date => scheduleOn(date).map(item => makeSession(item, date)))
}
function statsFor(sessions: Session[], id: number, name: string): EntityStats {
  const valid = sessions.filter(s => s.attendance?.detected_average !== null && s.attendance?.detected_average !== undefined && s.attendance.expected_count > 0)
  const expected = valid.reduce((sum, s) => sum + s.attendance!.expected_count, 0)
  const count = valid.reduce((sum, s) => sum + s.attendance!.detected_average!, 0)
  return { id, name, sessions_finished: sessions.length, avg_rate: expected ? count / expected : null, avg_detected: valid.length ? count / valid.length : null, records_complete: sessions.filter(s => s.attendance?.calculation_status === 'complete').length, records_partial: sessions.filter(s => s.attendance?.calculation_status === 'partial').length, records_failed: sessions.filter(s => s.attendance?.calculation_status === 'failed').length, breakdown: [] }
}
function entity(id: number, dimension: 'group' | 'teacher' | 'discipline'): EntityStats {
  const sessions = history().filter(s => s.schedule[dimension]?.id === id)
  const name = dimension === 'teacher' ? find(teachers, id).full_name : find(dimension === 'group' ? groups : disciplines, id).name
  const stats = statsFor(sessions, id, name)
  const other = dimension === 'group' ? 'discipline' : 'group'
  stats.breakdown = [...new Set(sessions.map(s => s.schedule[other].id))].map(key => {
    const subset = sessions.filter(s => s.schedule[other].id === key)
    const result = statsFor(subset, key, subset[0].schedule[other].name)
    return { id: key, name: result.name, sessions: subset.length, avg_rate: result.avg_rate, avg_detected: result.avg_detected }
  })
  return stats
}

const uploads: RecognitionUpload[] = [{
  id: 1, provenance: 'demo_fixture', filename: 'synthetic-classroom.png', label: 'Учебная сцена · схема аудитории', media_type: 'image', content_type: 'image/png', size_bytes: 20919, reference_people_count: null, created_at: `${DEMO_DATE}T09:15:00+03:00`,
  job: { id: 1, status: 'completed', attempts: 0, model_name: 'Учебный пример', model_version: 'без инференса', sample_rate_fps: 1, confidence_threshold: 0.35, started_at: null, finished_at: null, error: null,
    result: { provenance: 'demo_fixture', people_count: 18, detected_median: 18, detected_percentile_75: 18, detected_max: 18, average_confidence: null, count_stddev: 0, sampled_frames: 1, source_frames: 1, source_duration_ms: 0, representative_frame_ms: 0, absolute_error: null, relative_error: null, within_tolerance: null, media_expires_at: null },
  },
}]

export const staticApi = {
  async getGroups() { return clone(groups) },
  async createGroup(payload: Omit<Group, 'id'>) { if (groups.some(g => g.name === payload.name)) throw new Error('Название уже занято'); const item = { ...payload, id: Math.max(...groups.map(g => g.id)) + 1 }; groups.push(item); return clone(item) },
  async updateGroup(id: number, payload: Partial<Omit<Group, 'id' | 'name'>>) { Object.assign(find(groups, id), payload); return clone(find(groups, id)) },
  async getTeachers() { return clone(teachers) },
  async getDisciplines() { return clone(disciplines) },
  async getClassrooms() { return clone(classrooms) },
  async createClassroom(payload: { number: string; capacity: number | null }): Promise<Classroom> { const item: Classroom = { ...payload, id: Math.max(...classrooms.map(c => c.id)) + 1, aggregation_mode: 'single', cameras: [] }; classrooms.push(item); return clone(item) },
  async updateClassroom(id: number, payload: { capacity?: number | null; aggregation_mode?: AggregationMode }) { Object.assign(find(classrooms, id), payload); return clone(find(classrooms, id)) },
  async assignClassroomCameras(id: number, payload: { camera_id: number; role: CameraRole; priority: number; zone_code?: string | null }[]) { const room = find(classrooms, id); room.cameras = payload.map(p => ({ camera: { id: p.camera_id, name: find(cameras, p.camera_id).name }, role: p.role, priority: p.priority, zone_code: p.zone_code ?? null, enabled: true })); return clone(room) },
  async getCameras() { return clone(cameras) },
  async createCamera(payload: { name: string; rtsp_url: string; capture_group: string; enabled: boolean }) { const camera = { ...payload, id: Math.max(0, ...cameras.map(c => c.id)) + 1, classroom_number: null, created_at: `${DEMO_DATE}T09:00:00+03:00` }; cameras.push(camera); return clone(camera) },
  async updateCamera(id: number, payload: Partial<{ name: string; rtsp_url: string; capture_group: string; enabled: boolean }>) { Object.assign(find(cameras, id), payload); return clone(find(cameras, id)) },
  async deleteCamera(id: number) { find(cameras, id); cameras = cameras.filter(c => c.id !== id); classrooms.forEach(c => { c.cameras = c.cameras.filter(link => link.camera.id !== id) }) },
  async getSchedule(params?: { group_id?: number; weekday?: number }) { return clone(schedule.filter(s => (!params?.group_id || s.group.id === params.group_id) && (!params?.weekday || s.weekday === params.weekday))) },
  async importSchedule(_file: File): Promise<ImportResult> { throw new Error('Импорт доступен только в рабочем кабинете. Учебные данные не изменены.') },
  async getWeekType(date: string): Promise<WeekTypeInfo> { return { date, week_type: 'white' } },
  async getSessions(date: string): Promise<Session[]> { return scheduleOn(date).map(item => makeSession(item, date)) },
  async getSession(id: number): Promise<SessionDetail> { const day = String(Math.floor(id / 100)); const date = `${day.slice(0, 4)}-${day.slice(4, 6)}-${day.slice(6, 8)}`; const item = find(scheduleOn(date), id % 100); return makeSession(item, date) },
  async cancelSession(id: number): Promise<Session> { await staticApi.getSession(id); cancelled.add(id); return staticApi.getSession(id) },
  async getCaptureMedia(_id: number): Promise<CaptureMedia> { return { video_url: null, annotated_url: null, video_unavailable_reason: 'Учебный пример не содержит записи занятия', annotated_unavailable_reason: 'Учебный пример не содержит записи занятия', expires_in_seconds: 0 } },
  async getRecognitionUploads() { return clone(uploads) },
  async getRecognitionUploadMedia(id: number): Promise<RecognitionUploadMedia> { find(uploads, id); const url = `${import.meta.env.BASE_URL}synthetic-classroom.png`; return { source_url: url, annotated_url: url, source_unavailable_reason: null, annotated_unavailable_reason: null, expires_in_seconds: 0 } },
  async getRecognitionEvaluationSummary(): Promise<RecognitionEvaluationSummary> { return { checked_materials: 0, within_tolerance_count: 0, mean_absolute_error: null, median_absolute_error: null, max_absolute_error: null, mean_relative_error: null } },
  async uploadRecognition(_payload: { file: File; sample_rate_fps: number; confidence_threshold: number; label?: string; reference_people_count?: number }): Promise<RecognitionUpload> { throw new Error('В учебном примере серверная загрузка отключена') },
  async getSummary(): Promise<SummaryStats> { const sessions = history(); const stats = statsFor(sessions, 0, ''); return { groups: groups.length, teachers: teachers.length, disciplines: disciplines.length, classrooms: classrooms.length, cameras: cameras.length, sessions_total: sessions.length, sessions_today: scheduleOn(DEMO_DATE).length, sessions_finished: sessions.length, avg_attendance_rate: stats.avg_rate, records_complete: stats.records_complete, records_partial: stats.records_partial, records_failed: stats.records_failed } },
  async getGroupStats(id: number) { return entity(id, 'group') },
  async getTeacherStats(id: number) { return entity(id, 'teacher') },
  async getDisciplineStats(id: number) { return entity(id, 'discipline') },
  async getGroupTimeline(id: number): Promise<GroupTimeline> { const group = find(groups, id); return { group_id: id, group_name: group.name, points: Array.from({ length: 14 }, (_, i) => { const date = shiftDate(DEMO_DATE, i - 13); const stats = statsFor(history().filter(s => s.date === date && s.schedule.group.id === id), id, group.name); return { date, avg_rate: stats.avg_rate, avg_detected: stats.avg_detected, expected: group.students_count } }) } },
}
