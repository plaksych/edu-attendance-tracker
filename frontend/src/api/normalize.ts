import type { components } from './generated'
import type { Camera, Classroom, Group, ImportPreview, RecognitionHistory, RecognitionUpload, ScheduleItem, Session, SessionDetail, Teacher } from './types'
export type Wire = components['schemas']

export function provenance(value: string | undefined) {
  return value === 'demo_fixture' || value === 'browser_inference' || value === 'server_inference' ? value : undefined
}
export function group(value: Wire['GroupRead']): Group { return { ...value, faculty: value.faculty ?? null } }
export function teacher(value: Wire['TeacherRead']): Teacher { return { ...value, email: value.email ?? null, department: value.department ?? null } }
export function camera(value: Wire['CameraRead']): Camera { return { ...value, classroom_number: value.classroom_number ?? null, rtsp_url: '' } }
export function classroom(value: Wire['ClassroomRead']): Classroom { return { ...value, capacity: value.capacity ?? null, cameras: value.cameras ?? [] } }
export function schedule(value: Wire['ScheduleRead']): ScheduleItem {
  return { ...value, group: group(value.group), teacher: value.teacher ? teacher(value.teacher) : null, classroom: value.classroom ? classroom(value.classroom) : null }
}
export function session(value: Wire['app__schemas__session__SessionRead']): Session {
  return { ...value, schedule: schedule(value.schedule), attendance: value.attendance ?? null, measurements: (value.measurements ?? []).map(m => ({ ...m, provenance: provenance(m.provenance) })) }
}
export function sessionDetail(value: Wire['SessionDetail']): SessionDetail {
  return { ...session(value), measurements: (value.measurements ?? []).map(m => ({ ...m, provenance: provenance(m.provenance), captures: m.captures.map(c => ({ ...c, result: c.result ?? null })) })) }
}
export function upload(value: Wire['RecognitionUploadRead']): RecognitionUpload {
  return { ...value, provenance: provenance(value.provenance), job: { ...value.job, result: value.job.result ?? null } }
}
export function importPreview(value: Wire['ImportPreviewRead']): ImportPreview {
  return { ...value, rows: value.rows.map(row => ({ ...row, teacher: row.teacher ?? null, classroom: row.classroom ?? null, lesson_type: row.lesson_type ?? null })) }
}
export function recognitionHistory(value: Wire['RecognitionHistoryRead']): RecognitionHistory {
  return { ...value, jobs: value.jobs.map(job => ({ ...job, result: job.result ?? null })) }
}
