import { describe, expect, it } from 'vitest'
import { staticApi } from '../src/api/staticClient'
import { homeForRole, mayVisit } from '../src/auth/permissions'
import { csvCell, makeCsv } from '../src/lib/export'
import { DEMO_DATE } from '../src/lib/format'

describe('deterministic fixture adapter', () => {
  it('has synthetic identities and stable sessions with explicit provenance', async () => {
    expect((await staticApi.getTeachers()).every(t => /^Преподаватель \d$/.test(t.full_name) && t.email === null)).toBe(true)
    const first = await staticApi.getSessions(DEMO_DATE)
    expect(first).toEqual(await staticApi.getSessions(DEMO_DATE))
    expect(first.length).toBe(3)
    expect(first.every(s => s.provenance === 'demo_fixture')).toBe(true)
    expect(await staticApi.getSession(first[0].id)).toEqual(first[0])
  })
  it('returns copies and preserves missing days as null', async () => {
    const groups = await staticApi.getGroups()
    groups[0].name = 'changed'
    expect((await staticApi.getGroups())[0].name).not.toBe('changed')
    const timeline = await staticApi.getGroupTimeline(1)
    expect(timeline.points).toHaveLength(14)
    expect(timeline.points.some(p => p.avg_rate === null)).toBe(true)
    const all = await Promise.all([1, 2, 3].map(id => staticApi.getGroupTimeline(id)))
    expect(all.some(t => t.points.some(p => p.avg_rate === 0))).toBe(true)
  })
  it('does not simulate import success or model quality', async () => {
    await expect(staticApi.importSchedule({} as File)).rejects.toThrow('не изменены')
    const quality = await staticApi.getRecognitionEvaluationSummary()
    expect(quality.checked_materials).toBe(0)
    expect(quality.mean_absolute_error).toBeNull()
    const [upload] = await staticApi.getRecognitionUploads()
    expect(upload.job.attempts).toBe(0)
    expect(upload.job.result?.average_confidence).toBeNull()
  })
})
describe('roles', () => {
  it('allows analyst aggregates/catalog/schedule, never sessions/media/admin', () => {
    for (const path of ['/analytics', '/catalog', '/schedule']) expect(mayVisit('analyst', path)).toBe(true)
    for (const path of ['/sessions/12', '/recognition', '/admin/users', '/cameras']) expect(mayVisit('analyst', path)).toBe(false)
  })
  it('gives roles purposeful home routes and blocks teacher admin', () => {
    expect(homeForRole.teacher).toBe('/sessions')
    expect(homeForRole.operator).toBe('/recognition')
    expect(mayVisit('teacher', '/admin/audit')).toBe(false)
  })
})
describe('CSV exports', () => {
  it('escapes cells, preserves nulls, and neutralizes formula injection', () => {
    expect(csvCell(' =1+1')).toBe('"\' =1+1"')
    expect(csvCell('@SUM(A1)')).toBe('"\'@SUM(A1)"')
    expect(csvCell('a"b')).toBe('"a""b"')
    expect(makeCsv([[null, 0]])).toBe('\uFEFF"";"0"')
  })
})
