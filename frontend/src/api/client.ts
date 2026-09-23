import type {
  AggregationMode,
  CameraRole,
  CaptureMedia,
  Discipline,
  EntityStats,
  Group,
  GroupTimeline,
  ImportResult,
  RecognitionEvaluationSummary,
  RecognitionUploadMedia,
  SummaryStats,
  WeekTypeInfo,
} from './types'
import { request, json } from './http'
import * as normalize from './normalize'
import type { Wire } from './normalize'
export { ApiError } from './http'
export const isStaticData = import.meta.env.VITE_STATIC_DATA === 'true'

const liveApi = {
  getGroups: () => request<Wire['GroupRead'][]>('/groups').then(items => items.map(normalize.group)),
  createGroup: (payload: Omit<Group, 'id'>) => request<Wire['GroupRead']>('/groups', json('POST', payload)).then(normalize.group),
  updateGroup: (id: number, payload: Partial<Omit<Group, 'id' | 'name'>>) =>
    request<Wire['GroupRead']>(`/groups/${id}`, json('PATCH', payload)).then(normalize.group),

  getTeachers: () => request<Wire['TeacherRead'][]>('/teachers').then(items => items.map(normalize.teacher)),
  getDisciplines: () => request<Discipline[]>('/disciplines'),

  getClassrooms: () => request<Wire['ClassroomRead'][]>('/classrooms').then(items => items.map(normalize.classroom)),
  createClassroom: (payload: { number: string; capacity: number | null }) =>
    request<Wire['ClassroomRead']>('/classrooms', json('POST', payload)).then(normalize.classroom),
  updateClassroom: (
    id: number,
    payload: { capacity?: number | null; aggregation_mode?: AggregationMode },
  ) => request<Wire['ClassroomRead']>(`/classrooms/${id}`, json('PATCH', payload)).then(normalize.classroom),
  assignClassroomCameras: (
    id: number,
    payload: { camera_id: number; role: CameraRole; priority: number; zone_code?: string | null }[],
  ) => request<Wire['ClassroomRead']>(`/classrooms/${id}/cameras`, json('PUT', payload)).then(normalize.classroom),

  getCameras: () => request<Wire['CameraRead'][]>('/cameras').then(items => items.map(normalize.camera)),
  createCamera: (payload: {
    name: string
    rtsp_url: string
    capture_group: string
    enabled: boolean
  }) => request<Wire['CameraRead']>('/cameras', json('POST', payload)).then(normalize.camera),
  updateCamera: (
    id: number,
    payload: Partial<{ name: string; rtsp_url: string; capture_group: string; enabled: boolean }>,
  ) => request<Wire['CameraRead']>(`/cameras/${id}`, json('PATCH', payload)).then(normalize.camera),
  deleteCamera: (id: number) => request<void>(`/cameras/${id}`, { method: 'DELETE' }),

  getSchedule: (params?: { group_id?: number; weekday?: number }) => {
    const query = new URLSearchParams()
    if (params?.group_id) query.set('group_id', String(params.group_id))
    if (params?.weekday) query.set('weekday', String(params.weekday))
    const suffix = query.size > 0 ? `?${query}` : ''
    return request<Wire['ScheduleRead'][]>(`/schedule${suffix}`).then(items => items.map(normalize.schedule))
  },
  importSchedule: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<ImportResult>('/schedule/import', { method: 'POST', body: form })
  },
  getWeekType: (date: string) => request<WeekTypeInfo>(`/schedule/week-type?date=${date}`),

  getSessions: (date: string) => request<Wire['app__schemas__session__SessionRead'][]>(`/sessions?date=${date}`).then(items => items.map(normalize.session)),
  getSession: (id: number) => request<Wire['SessionDetail']>(`/sessions/${id}`).then(normalize.sessionDetail),
  cancelSession: (id: number) => request<Wire['app__schemas__session__SessionRead']>(`/sessions/${id}/cancel`, { method: 'POST' }).then(normalize.session),
  getCaptureMedia: (captureId: number) => request<CaptureMedia>(`/captures/${captureId}/media`),

  getRecognitionUploads: () => request<Wire['RecognitionUploadRead'][]>('/recognition/uploads').then(items => items.map(normalize.upload)),
  getRecognitionUploadMedia: (uploadId: number) =>
    request<RecognitionUploadMedia>(`/recognition/uploads/${uploadId}/media`),
  getRecognitionEvaluationSummary: () =>
    request<RecognitionEvaluationSummary>('/recognition/evaluation/summary'),
  uploadRecognition: (payload: {
    idempotency_key: string
    session_id?: number
    measurement_id?: number
    file: File
    sample_rate_fps: number
    confidence_threshold: number
    label?: string
    reference_people_count?: number
  }) => {
    const form = new FormData()
    form.append('file', payload.file)
    form.append('sample_rate_fps', String(payload.sample_rate_fps))
    form.append('confidence_threshold', String(payload.confidence_threshold))
    if (payload.session_id !== undefined) form.append('session_id', String(payload.session_id))
    if (payload.measurement_id !== undefined) form.append('measurement_id', String(payload.measurement_id))
    if (payload.label) form.append('label', payload.label)
    if (payload.reference_people_count !== undefined) {
      form.append('reference_people_count', String(payload.reference_people_count))
    }
    return request<Wire['RecognitionUploadRead']>('/recognition/uploads', { method: 'POST', headers: { 'Idempotency-Key': payload.idempotency_key }, body: form }).then(normalize.upload)
  },

  getSummary: () => request<SummaryStats>('/stats/summary'),
  getGroupStats: (id: number) => request<EntityStats>(`/stats/groups/${id}`),
  getTeacherStats: (id: number) => request<EntityStats>(`/stats/teachers/${id}`),
  getDisciplineStats: (id: number) => request<EntityStats>(`/stats/disciplines/${id}`),
  getGroupTimeline: (id: number, range?: { date_from: string; date_to: string }) => request<GroupTimeline>(`/stats/groups/${id}/timeline${range ? `?${new URLSearchParams(range)}` : ''}`),
}

// Build-time branch keeps fixtures and their adapter out of the live bundle.
export const api: typeof liveApi = isStaticData ? new Proxy(liveApi, {
  get(_target, key: keyof typeof liveApi) {
    return async (...args: unknown[]) => {
      const { staticApi } = await import('./staticClient')
      const method = staticApi[key] as (...values: unknown[]) => unknown
      return method(...args)
    }
  },
}) : liveApi
