import type {
  AggregationMode,
  Camera,
  CameraRole,
  Capture,
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
  WeekType,
  WeekTypeInfo,
} from './types'

interface DemoData {
  source: string
  semester_start: string
  import_result: ImportResult
  groups: Group[]
  teachers: Teacher[]
  disciplines: Discipline[]
  classrooms: Classroom[]
  cameras: Camera[]
  schedule: ScheduleItem[]
}

interface ScheduleFilter {
  group_id?: number
  weekday?: number
}

const DATA_URL = `${import.meta.env.BASE_URL}demo-data.json`
const OFFSET_MINUTES = 15

let statePromise: Promise<DemoData> | null = null
let state: DemoData | null = null
const cancelledSessions = new Set<number>()

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

async function loadData(): Promise<DemoData> {
  if (state) return state
  if (!statePromise) {
    statePromise = fetchDemoJson(DATA_URL).catch((error) => {
      if (DATA_URL === '/demo-data.json') throw error
      return fetchDemoJson('/demo-data.json')
    })
  }
  state = await statePromise
  return state
}

async function fetchDemoJson(url: string): Promise<DemoData> {
  return fetch(url).then((response) => {
    if (!response.ok) throw new Error('Не удалось загрузить demo-data.json')
    const contentType = response.headers.get('content-type') ?? ''
    if (!contentType.includes('application/json')) {
      throw new Error('demo-data.json недоступен по ожидаемому пути')
    }
    return response.json() as Promise<DemoData>
  })
}

function nextId(items: { id: number }[]): number {
  return Math.max(0, ...items.map((item) => item.id)) + 1
}

function assertFound<T>(value: T | undefined | null, message: string): T {
  if (value === undefined || value === null) throw new Error(message)
  return value
}

function weekTypeForDate(data: DemoData, iso: string): WeekType {
  const start = new Date(`${data.semester_start}T12:00:00`)
  const current = new Date(`${iso}T12:00:00`)
  const days = Math.floor((current.getTime() - start.getTime()) / 86_400_000)
  const week = Math.floor(days / 7)
  return week % 2 === 0 ? 'white' : 'green'
}

function weekday(iso: string): number {
  const day = new Date(`${iso}T12:00:00`).getDay()
  return day === 0 ? 7 : day
}

function localDateTime(iso: string, time: string, minutes: number): string {
  const date = new Date(`${iso}T${time}`)
  date.setMinutes(date.getMinutes() + minutes)
  const yyyy = date.getFullYear()
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  const hh = String(date.getHours()).padStart(2, '0')
  const min = String(date.getMinutes()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}T${hh}:${min}:00`
}

function sessionId(date: string, scheduleId: number): number {
  return Number(date.replace(/-/g, '')) * 10_000 + scheduleId
}

function splitSessionId(id: number): { date: string; scheduleId: number } {
  const day = Math.floor(id / 10_000)
  const scheduleId = id % 10_000
  const text = String(day)
  return {
    date: `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6, 8)}`,
    scheduleId,
  }
}

function seed(date: string, scheduleId: number): number {
  return (
    scheduleId * 17 +
    [...date].reduce((sum, char) => sum + char.charCodeAt(0), 0)
  )
}

function countsFor(schedule: ScheduleItem, date: string) {
  const expected = schedule.group.students_count
  const base = seed(date, schedule.id)
  const after = Math.max(0, Math.min(expected, Math.round(expected * (0.72 + (base % 16) / 100))))
  const before = Math.max(0, Math.min(expected, after - 2 + (base % 5)))
  const average = Number(((after + before) / 2).toFixed(2))
  return { expected, after, before, average, max: Math.max(after, before) }
}

function capturesFor(schedule: ScheduleItem, date: string, measurementId: number, count: number): Capture[] {
  const links = schedule.classroom?.cameras ?? []
  return links.map((link, index) => ({
    id: measurementId * 10 + index + 1,
    camera: link.camera,
    status: 'completed',
    planned_at: localDateTime(date, schedule.starts_at, OFFSET_MINUTES),
    attempts: 1,
    size_bytes: 2_200_000 + index * 180_000,
    duration_ms: 20_000,
    error: null,
    has_video: true,
    result: {
      people_count: count,
      detected_median: count,
      detected_percentile_75: count + (index % 2),
      detected_max: count + 1,
      average_confidence: 0.82,
      sampled_frames: 20,
      representative_frame_ms: 9_500,
      media_expires_at: null,
    },
  }))
}

function buildSession(
  schedule: ScheduleItem,
  date: string,
  detail = false,
): Session | SessionDetail {
  const id = sessionId(date, schedule.id)
  const cancelled = cancelledSessions.has(id)
  const counts = countsFor(schedule, date)
  const rate = counts.expected > 0 ? Number(Math.min(counts.average / counts.expected, 1).toFixed(4)) : null
  const firstId = id * 10 + 1
  const secondId = id * 10 + 2
  const aggregation = schedule.classroom?.aggregation_mode ?? 'single'
  const first = {
    id: firstId,
    type: 'after_start' as const,
    planned_at: localDateTime(date, schedule.starts_at, OFFSET_MINUTES),
    status: cancelled ? ('cancelled' as const) : ('completed' as const),
    final_people_count: cancelled ? null : counts.after,
    confidence: cancelled ? null : 0.82,
    aggregation_method: aggregation,
    error: null,
    ...(detail ? { captures: cancelled ? [] : capturesFor(schedule, date, firstId, counts.after) } : {}),
  }
  const second = {
    id: secondId,
    type: 'before_end' as const,
    planned_at: localDateTime(date, schedule.ends_at, -OFFSET_MINUTES),
    status: cancelled ? ('cancelled' as const) : ('completed' as const),
    final_people_count: cancelled ? null : counts.before,
    confidence: cancelled ? null : 0.81,
    aggregation_method: aggregation,
    error: null,
    ...(detail ? { captures: cancelled ? [] : capturesFor(schedule, date, secondId, counts.before) } : {}),
  }
  return {
    id,
    date,
    status: cancelled ? 'cancelled' : 'finished',
    started_at: localDateTime(date, schedule.starts_at, 0),
    finished_at: localDateTime(date, schedule.ends_at, 0),
    schedule,
    attendance: cancelled
      ? null
      : {
          expected_count: counts.expected,
          after_start_count: counts.after,
          before_end_count: counts.before,
          detected_average: counts.average,
          detected_max: counts.max,
          attendance_rate: rate,
          calculation_status: 'complete',
          calculated_at: localDateTime(date, schedule.ends_at, 5),
        },
    measurements: [first, second],
  }
}

function scheduleForDate(data: DemoData, date: string): ScheduleItem[] {
  const day = weekday(date)
  const week = weekTypeForDate(data, date)
  return data.schedule.filter(
    (item) =>
      item.weekday === day && (item.week_type === 'every' || item.week_type === week),
  )
}

function rateFor(item: ScheduleItem): number {
  const counts = countsFor(item, '2026-02-09')
  return counts.expected > 0 ? Math.min(counts.average / counts.expected, 1) : 0
}

function entityStats(
  items: ScheduleItem[],
  id: number,
  name: string,
  breakdown: Map<number, { name: string; items: ScheduleItem[] }>,
): EntityStats {
  const rates = items.map(rateFor)
  const avgRate = rates.length
    ? Number((rates.reduce((sum, value) => sum + value, 0) / rates.length).toFixed(4))
    : null
  const avgDetected = items.length
    ? Number(
        (
          items.reduce((sum, item) => sum + countsFor(item, '2026-02-09').average, 0) /
          items.length
        ).toFixed(2),
      )
    : null
  return {
    id,
    name,
    sessions_finished: items.length,
    avg_rate: avgRate,
    avg_detected: avgDetected,
    records_complete: items.length,
    records_partial: 0,
    records_failed: 0,
    breakdown: [...breakdown.entries()]
      .map(([breakdownId, row]) => {
        const rowRates = row.items.map(rateFor)
        return {
          id: breakdownId,
          name: row.name,
          sessions: row.items.length,
          avg_rate: rowRates.length
            ? Number((rowRates.reduce((sum, value) => sum + value, 0) / rowRates.length).toFixed(4))
            : null,
          avg_detected: row.items.length
            ? Number(
                (
                  row.items.reduce((sum, item) => sum + countsFor(item, '2026-02-09').average, 0) /
                  row.items.length
                ).toFixed(2),
              )
            : null,
        }
      })
      .sort((a, b) => a.name.localeCompare(b.name, 'ru')),
  }
}

export const staticApi = {
  async getGroups(): Promise<Group[]> {
    return clone((await loadData()).groups)
  },
  async createGroup(payload: Omit<Group, 'id'>): Promise<Group> {
    const data = await loadData()
    if (data.groups.some((group) => group.name === payload.name)) {
      throw new Error('Группа с таким названием уже существует')
    }
    const group = { ...payload, id: nextId(data.groups) }
    data.groups.push(group)
    return clone(group)
  },
  async updateGroup(id: number, payload: Partial<Omit<Group, 'id' | 'name'>>): Promise<Group> {
    const data = await loadData()
    const group = assertFound(data.groups.find((item) => item.id === id), 'Группа не найдена')
    Object.assign(group, payload)
    return clone(group)
  },

  async getTeachers(): Promise<Teacher[]> {
    return clone((await loadData()).teachers)
  },
  async getDisciplines(): Promise<Discipline[]> {
    return clone((await loadData()).disciplines)
  },

  async getClassrooms(): Promise<Classroom[]> {
    return clone((await loadData()).classrooms)
  },
  async createClassroom(payload: { number: string; capacity: number | null }): Promise<Classroom> {
    const data = await loadData()
    const classroom: Classroom = {
      id: nextId(data.classrooms),
      number: payload.number,
      capacity: payload.capacity,
      aggregation_mode: 'single',
      cameras: [],
    }
    data.classrooms.push(classroom)
    return clone(classroom)
  },
  async updateClassroom(
    id: number,
    payload: { capacity?: number | null; aggregation_mode?: AggregationMode },
  ): Promise<Classroom> {
    const data = await loadData()
    const classroom = assertFound(
      data.classrooms.find((item) => item.id === id),
      'Аудитория не найдена',
    )
    Object.assign(classroom, payload)
    return clone(classroom)
  },
  async assignClassroomCameras(
    id: number,
    payload: { camera_id: number; role: CameraRole; priority: number; zone_code?: string | null }[],
  ): Promise<Classroom> {
    const data = await loadData()
    const classroom = assertFound(
      data.classrooms.find((item) => item.id === id),
      'Аудитория не найдена',
    )
    classroom.cameras = payload.map((row) => {
      const camera = assertFound(data.cameras.find((item) => item.id === row.camera_id), 'Камера не найдена')
      camera.classroom_number = classroom.number
      return {
        camera: { id: camera.id, name: camera.name },
        role: row.role,
        priority: row.priority,
        zone_code: row.zone_code ?? null,
        enabled: camera.enabled,
      }
    })
    return clone(classroom)
  },

  async getCameras(): Promise<Camera[]> {
    return clone((await loadData()).cameras)
  },
  async createCamera(payload: {
    name: string
    rtsp_url: string
    capture_group: string
    enabled: boolean
  }): Promise<Camera> {
    const data = await loadData()
    const camera: Camera = {
      id: nextId(data.cameras),
      classroom_number: null,
      created_at: new Date().toISOString(),
      ...payload,
    }
    data.cameras.push(camera)
    return clone(camera)
  },
  async updateCamera(
    id: number,
    payload: Partial<{ name: string; rtsp_url: string; capture_group: string; enabled: boolean }>,
  ): Promise<Camera> {
    const data = await loadData()
    const camera = assertFound(data.cameras.find((item) => item.id === id), 'Камера не найдена')
    Object.assign(camera, payload)
    for (const classroom of data.classrooms) {
      for (const link of classroom.cameras) {
        if (link.camera.id === id) {
          link.camera.name = camera.name
          link.enabled = camera.enabled
        }
      }
    }
    return clone(camera)
  },
  async deleteCamera(id: number): Promise<void> {
    const data = await loadData()
    data.cameras = data.cameras.filter((item) => item.id !== id)
    for (const classroom of data.classrooms) {
      classroom.cameras = classroom.cameras.filter((link) => link.camera.id !== id)
    }
  },

  async getSchedule(params?: ScheduleFilter): Promise<ScheduleItem[]> {
    const data = await loadData()
    let items = data.schedule
    if (params?.group_id) items = items.filter((item) => item.group.id === params.group_id)
    if (params?.weekday) items = items.filter((item) => item.weekday === params.weekday)
    return clone(items)
  },
  async importSchedule(_file: File): Promise<ImportResult> {
    return clone((await loadData()).import_result)
  },
  async getWeekType(date: string): Promise<WeekTypeInfo> {
    return { date, week_type: weekTypeForDate(await loadData(), date) }
  },

  async getSessions(date: string): Promise<Session[]> {
    const data = await loadData()
    return clone(scheduleForDate(data, date).map((item) => buildSession(item, date) as Session))
  },
  async getSession(id: number): Promise<SessionDetail> {
    const data = await loadData()
    const decoded = splitSessionId(id)
    const item = assertFound(
      data.schedule.find((schedule) => schedule.id === decoded.scheduleId),
      'Занятие не найдено',
    )
    return clone(buildSession(item, decoded.date, true) as SessionDetail)
  },
  async cancelSession(id: number): Promise<Session> {
    cancelledSessions.add(id)
    const detail = await staticApi.getSession(id)
    return clone(detail)
  },
  async getCaptureMedia(_captureId: number): Promise<CaptureMedia> {
    return {
      video_url: null,
      video_unavailable_reason: 'Медиа недоступно в статическом режиме',
      annotated_url: null,
      annotated_unavailable_reason: 'Медиа недоступно в статическом режиме',
      expires_in_seconds: 0,
    }
  },

  async getSummary(): Promise<SummaryStats> {
    const data = await loadData()
    const rates = data.schedule.map(rateFor)
    return {
      groups: data.groups.length,
      teachers: data.teachers.length,
      disciplines: data.disciplines.length,
      classrooms: data.classrooms.length,
      cameras: data.cameras.length,
      sessions_total: data.schedule.length,
      sessions_today: scheduleForDate(data, new Date().toISOString().slice(0, 10)).length,
      sessions_finished: data.schedule.length,
      avg_attendance_rate: rates.length
        ? Number((rates.reduce((sum, value) => sum + value, 0) / rates.length).toFixed(4))
        : null,
      records_complete: data.schedule.length,
      records_partial: 0,
      records_failed: 0,
    }
  },
  async getGroupStats(id: number): Promise<EntityStats> {
    const data = await loadData()
    const group = assertFound(data.groups.find((item) => item.id === id), 'Группа не найдена')
    const items = data.schedule.filter((item) => item.group.id === id)
    const breakdown = new Map<number, { name: string; items: ScheduleItem[] }>()
    for (const item of items) {
      const row = breakdown.get(item.discipline.id) ?? { name: item.discipline.name, items: [] }
      row.items.push(item)
      breakdown.set(item.discipline.id, row)
    }
    return entityStats(items, group.id, group.name, breakdown)
  },
  async getTeacherStats(id: number): Promise<EntityStats> {
    const data = await loadData()
    const teacher = assertFound(data.teachers.find((item) => item.id === id), 'Преподаватель не найден')
    const items = data.schedule.filter((item) => item.teacher?.id === id)
    const breakdown = new Map<number, { name: string; items: ScheduleItem[] }>()
    for (const item of items) {
      const row = breakdown.get(item.group.id) ?? { name: item.group.name, items: [] }
      row.items.push(item)
      breakdown.set(item.group.id, row)
    }
    return entityStats(items, teacher.id, teacher.full_name, breakdown)
  },
  async getDisciplineStats(id: number): Promise<EntityStats> {
    const data = await loadData()
    const discipline = assertFound(data.disciplines.find((item) => item.id === id), 'Дисциплина не найдена')
    const items = data.schedule.filter((item) => item.discipline.id === id)
    const breakdown = new Map<number, { name: string; items: ScheduleItem[] }>()
    for (const item of items) {
      const row = breakdown.get(item.group.id) ?? { name: item.group.name, items: [] }
      row.items.push(item)
      breakdown.set(item.group.id, row)
    }
    return entityStats(items, discipline.id, discipline.name, breakdown)
  },
  async getGroupTimeline(id: number): Promise<GroupTimeline> {
    const data = await loadData()
    const group = assertFound(data.groups.find((item) => item.id === id), 'Группа не найдена')
    const points = []
    const start = new Date(`${data.semester_start}T12:00:00`)
    for (let offset = 0; offset < 14; offset += 1) {
      const date = new Date(start)
      date.setDate(start.getDate() + offset)
      const iso = date.toISOString().slice(0, 10)
      const items = scheduleForDate(data, iso).filter((item) => item.group.id === id)
      if (items.length === 0) continue
      const rates = items.map(rateFor)
      points.push({
        date: iso,
        avg_rate: Number((rates.reduce((sum, value) => sum + value, 0) / rates.length).toFixed(4)),
        avg_detected: Number(
          (
            items.reduce((sum, item) => sum + countsFor(item, iso).average, 0) / items.length
          ).toFixed(2),
        ),
        expected: group.students_count,
      })
    }
    return { group_id: group.id, group_name: group.name, points }
  },
}
