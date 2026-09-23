import { json, request, requestResponse } from './http'
import type { Role } from '../auth/permissions'
import type { ImportResult } from './types'
import { importPreview, recognitionHistory, upload, type Wire } from './normalize'

export interface Capabilities {
  profile: string; formats: string[]; max_size_bytes: number; max_pixels: number
  max_duration_seconds: number; max_video_dimension: number
  sample_rate_fps: { min: number; max: number }; confidence: { min: number; max: number }
}
export interface ManagedUser { id: number; username: string; role: Role; enabled: boolean }
export interface AuditEvent { id: number; actor_id: number | null; action: string; object_type: string; object_id: string | null; reason: string | null; request_id: string | null; created_at: string }
export interface SystemStatus { database: string; storage: string; recognition_queue: Record<string, number>; last_job_heartbeat: string | null; timezone: string; environment: string; camera_enabled: boolean; backup_status: string }
export const managementApi = {
  system: (): Promise<SystemStatus> => request<Wire['SystemRead']>('/admin/system'),
  exportStats: async (params: { date_from: string; date_to: string; group_id: string }) => (await requestResponse(`/stats/export.csv?${new URLSearchParams(params)}`)).blob(),
  previewSchedule: (file: File) => { const body = new FormData(); body.append('file', file); return request<Wire['ImportPreviewRead']>('/schedule/import/preview', { method: 'POST', body }).then(importPreview) },
  confirmSchedule: (id: string) => request<ImportResult>(`/schedule/import/${encodeURIComponent(id)}/confirm`, { method: 'POST' }),
  history: (id: number) => request<Wire['RecognitionHistoryRead']>(`/recognition/uploads/${id}/history`).then(recognitionHistory),
  correct: (id: number, body: { people_count: number; reason: string }) => request<Wire['CorrectionCreated']>(`/recognition/uploads/${id}/corrections`, json('POST', body)),
  capabilities: (): Promise<Capabilities> => request<Wire['RecognitionCapabilities']>('/recognition/capabilities'),
  retry: (id: number, key: string) => request<Wire['RecognitionUploadRead']>(`/recognition/uploads/${id}/retry`, { method: 'POST', headers: { 'Idempotency-Key': key } }).then(upload),
  users: (offset = 0) => request<ManagedUser[]>(`/admin/users?limit=25&offset=${offset}`),
  createUser: (body: { username: string; password: string; role: Role }) => request<ManagedUser>('/admin/users', json('POST', body)),
  updateUser: (id: number, body: { reason: string; enabled?: boolean; role?: Role; password?: string; group_ids?: number[] }) => request<ManagedUser>(`/admin/users/${id}`, json('PATCH', body)),
  audit: (offset = 0) => request<AuditEvent[]>(`/admin/audit?limit=25&offset=${offset}`),
}
