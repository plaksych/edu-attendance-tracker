import { describe, expect, it } from 'vitest'
import * as normalize from '../src/api/normalize'
import { staticApi } from '../src/api/staticClient'
import { DEMO_DATE } from '../src/lib/format'
describe('generated wire schema normalization', () => {
  it('normalizes optional catalog fields and redacts camera addresses', () => {
    expect(normalize.group({ id: 1, name: 'group', course: 1, students_count: 0 }).faculty).toBeNull()
    expect(normalize.teacher({ id: 1, full_name: 'teacher' })).toMatchObject({ email: null, department: null })
    expect(normalize.classroom({ id: 1, number: '1', aggregation_mode: 'single' })).toMatchObject({ capacity: null, cameras: [] })
    expect(normalize.camera({ id: 1, name: 'camera', rtsp_url: 'must-not-display', enabled: true, capture_group: 'default', created_at: '2026-01-01T00:00:00Z' })).toMatchObject({ rtsp_url: '', classroom_number: null })
  })
  it('normalizes absent session arrays/nulls without inventing zero attendance', async () => {
    const [fixture] = await staticApi.getSessions(DEMO_DATE)
    const wire = { ...fixture, measurements: undefined, attendance: undefined }
    const result = normalize.session(wire)
    expect(result.measurements).toEqual([])
    expect(result.attendance).toBeNull()
  })
  it('accepts known provenance and does not label unknown values as inference', () => {
    expect(normalize.provenance('server_inference')).toBe('server_inference')
    expect(normalize.provenance('unknown')).toBeUndefined()
  })
  it('normalizes optional preview row fields from the generated schema', () => {
    const preview = normalize.importPreview({ preview_id: 'preview', expires_at: '2026-09-23T12:00:00Z', created: 1, skipped: 0, errors: [], rows: [{ group: 'G1', discipline: 'D1', weekday: 3, starts_at: '09:00:00', ends_at: '10:30:00', week_type: 'every' }] })
    expect(preview.rows[0]).toMatchObject({ teacher: null, classroom: null, lesson_type: null })
  })
  it('preserves nullable correction authors and normalizes unprocessed history jobs', async () => {
    const [fixture] = await staticApi.getRecognitionUploads()
    const history = normalize.recognitionHistory({ jobs: [{ ...fixture.job, result: undefined }], corrections: [{ id: 1, job_id: 1, actor_id: null, people_count: 18, reason: 'Manual reference', created_at: '2026-09-23T12:00:00Z' }] })
    expect(history.jobs[0].result).toBeNull()
    expect(history.corrections[0].actor_id).toBeNull()
  })
})
