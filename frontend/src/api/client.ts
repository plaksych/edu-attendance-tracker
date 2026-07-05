import type {
  AggregationMode,
  Camera,
  CameraRole,
  CaptureMedia,
  Classroom,
  Discipline,
  EntityStats,
  Group,
  GroupTimeline,
  ImportResult,
  ScheduleItem,
  Session,
  SessionDetail,
  SummaryStats,
  Teacher,
  WeekTypeInfo,
} from './types'
import { staticApi } from './staticClient'

const API_BASE = '/api/v1'
export const isStaticData = import.meta.env.VITE_STATIC_DATA === 'true'

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init)
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // тело не JSON — оставляем statusText
    }
    throw new ApiError(response.status, detail)
  }
  if (response.status === 204) return undefined as T
  return response.json()
}

function json(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

const liveApi = {
  getGroups: () => request<Group[]>('/groups'),
  createGroup: (payload: Omit<Group, 'id'>) => request<Group>('/groups', json('POST', payload)),
  updateGroup: (id: number, payload: Partial<Omit<Group, 'id' | 'name'>>) =>
    request<Group>(`/groups/${id}`, json('PATCH', payload)),

  getTeachers: () => request<Teacher[]>('/teachers'),
  getDisciplines: () => request<Discipline[]>('/disciplines'),

  getClassrooms: () => request<Classroom[]>('/classrooms'),
  createClassroom: (payload: { number: string; capacity: number | null }) =>
    request<Classroom>('/classrooms', json('POST', payload)),
  updateClassroom: (
    id: number,
    payload: { capacity?: number | null; aggregation_mode?: AggregationMode },
  ) => request<Classroom>(`/classrooms/${id}`, json('PATCH', payload)),
  assignClassroomCameras: (
    id: number,
    payload: { camera_id: number; role: CameraRole; priority: number; zone_code?: string | null }[],
  ) => request<Classroom>(`/classrooms/${id}/cameras`, json('PUT', payload)),

  getCameras: () => request<Camera[]>('/cameras'),
  createCamera: (payload: {
    name: string
    rtsp_url: string
    capture_group: string
    enabled: boolean
  }) => request<Camera>('/cameras', json('POST', payload)),
  updateCamera: (
    id: number,
    payload: Partial<{ name: string; rtsp_url: string; capture_group: string; enabled: boolean }>,
  ) => request<Camera>(`/cameras/${id}`, json('PATCH', payload)),
  deleteCamera: (id: number) => request<void>(`/cameras/${id}`, { method: 'DELETE' }),

  getSchedule: (params?: { group_id?: number; weekday?: number }) => {
    const query = new URLSearchParams()
    if (params?.group_id) query.set('group_id', String(params.group_id))
    if (params?.weekday) query.set('weekday', String(params.weekday))
    const suffix = query.size > 0 ? `?${query}` : ''
    return request<ScheduleItem[]>(`/schedule${suffix}`)
  },
  importSchedule: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<ImportResult>('/schedule/import', { method: 'POST', body: form })
  },
  getWeekType: (date: string) => request<WeekTypeInfo>(`/schedule/week-type?date=${date}`),

  getSessions: (date: string) => request<Session[]>(`/sessions?date=${date}`),
  getSession: (id: number) => request<SessionDetail>(`/sessions/${id}`),
  cancelSession: (id: number) => request<Session>(`/sessions/${id}/cancel`, { method: 'POST' }),
  getCaptureMedia: (captureId: number) => request<CaptureMedia>(`/captures/${captureId}/media`),

  getSummary: () => request<SummaryStats>('/stats/summary'),
  getGroupStats: (id: number) => request<EntityStats>(`/stats/groups/${id}`),
  getTeacherStats: (id: number) => request<EntityStats>(`/stats/teachers/${id}`),
  getDisciplineStats: (id: number) => request<EntityStats>(`/stats/disciplines/${id}`),
  getGroupTimeline: (id: number) => request<GroupTimeline>(`/stats/groups/${id}/timeline`),
}

export const api = isStaticData ? staticApi : liveApi
