import type {
  EntityStats,
  Group,
  GroupTimeline,
  ImportResult,
  ScheduleItem,
  Session,
  SessionWithSnapshots,
  SummaryStats,
  Teacher,
  WeekTypeInfo,
} from './types'

const API_BASE = '/api/v1'

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

export const api = {
  getGroups: () => request<Group[]>('/groups'),
  getTeachers: () => request<Teacher[]>('/teachers'),

  getSchedule: (params?: { group_id?: number; weekday?: number }) => {
    const query = new URLSearchParams()
    if (params?.group_id) query.set('group_id', String(params.group_id))
    if (params?.weekday) query.set('weekday', String(params.weekday))
    const suffix = query.size > 0 ? `?${query}` : ''
    return request<ScheduleItem[]>(`/schedule${suffix}`)
  },

  getWeekType: (date: string) => request<WeekTypeInfo>(`/schedule/week-type?date=${date}`),

  importSchedule: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<ImportResult>('/schedule/import', { method: 'POST', body: form })
  },

  getSessionsToday: () => request<Session[]>('/sessions/today'),
  getSessions: (date: string) => request<Session[]>(`/sessions?date=${date}`),
  getSession: (id: number) => request<SessionWithSnapshots>(`/sessions/${id}`),
  startSession: (id: number) => request<Session>(`/sessions/${id}/start`, { method: 'POST' }),
  finishSession: (id: number) => request<Session>(`/sessions/${id}/finish`, { method: 'POST' }),

  getSummary: () => request<SummaryStats>('/stats/summary'),
  getGroupStats: (id: number) => request<EntityStats>(`/stats/groups/${id}`),
  getTeacherStats: (id: number) => request<EntityStats>(`/stats/teachers/${id}`),
  getGroupTimeline: (id: number) => request<GroupTimeline>(`/stats/groups/${id}/timeline`),
}
