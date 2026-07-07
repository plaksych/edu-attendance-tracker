import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { Group, ImportResult, ScheduleItem, WeekType } from '../api/types'
import { WeekBadge } from '../components/WeekBadge'

const WEEKDAYS = [
  'Понедельник',
  'Вторник',
  'Среда',
  'Четверг',
  'Пятница',
  'Суббота',
  'Воскресенье',
]

export function SchedulePage() {
  const [items, setItems] = useState<ScheduleItem[] | null>(null)
  const [groups, setGroups] = useState<Group[]>([])
  const [groupFilter, setGroupFilter] = useState<number | ''>('')
  const [weekFilter, setWeekFilter] = useState<'all' | WeekType>('all')
  const [error, setError] = useState<string | null>(null)
  const [importResult, setImportResult] = useState<ImportResult | null>(null)
  const [uploading, setUploading] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    api
      .getGroups()
      .then(setGroups)
      .catch((e: Error) => setError(e.message))
  }, [])

  useEffect(() => {
    setItems(null)
    api
      .getSchedule(groupFilter === '' ? undefined : { group_id: groupFilter })
      .then(setItems)
      .catch((e: Error) => setError(e.message))
  }, [groupFilter])

  const handleUpload = async (file: File) => {
    setUploading(true)
    setError(null)
    setImportResult(null)
    try {
      const result = await api.importSchedule(file)
      setImportResult(result)
      const refreshed = await api.getSchedule(
        groupFilter === '' ? undefined : { group_id: groupFilter },
      )
      setItems(refreshed)
      const refreshedGroups = await api.getGroups()
      setGroups(refreshedGroups)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setUploading(false)
      if (fileInput.current) fileInput.current.value = ''
    }
  }

  const visible = (items ?? []).filter(
    (item) =>
      weekFilter === 'all' || item.week_type === 'every' || item.week_type === weekFilter,
  )
  const byWeekday = new Map<number, ScheduleItem[]>()
  for (const item of visible) {
    const list = byWeekday.get(item.weekday) ?? []
    list.push(item)
    byWeekday.set(item.weekday, list)
  }

  return (
    <>
      <header className="page-header">
        <h1>Расписание</h1>
        <p>Недельная сетка занятий; загрузка из Excel</p>
      </header>

      <div className="card section">
        <div className="upload">
          <input
            ref={fileInput}
            type="file"
            accept=".xlsx"
            style={{ display: 'none' }}
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) handleUpload(file)
            }}
          />
          <button
            className="btn"
            disabled={uploading}
            onClick={() => fileInput.current?.click()}
          >
            {uploading ? 'Загрузка…' : 'Загрузить из Excel'}
          </button>
          <a className="btn btn--secondary" href="/api/v1/schedule/template" download>
            Скачать шаблон
          </a>
          <select
            className="select"
            value={groupFilter}
            onChange={(e) =>
              setGroupFilter(e.target.value === '' ? '' : Number(e.target.value))
            }
          >
            <option value="">Все группы</option>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </select>
          <select
            className="select"
            value={weekFilter}
            onChange={(e) => setWeekFilter(e.target.value as 'all' | WeekType)}
          >
            <option value="all">Обе недели</option>
            <option value="white">Белая неделя</option>
            <option value="green">Зелёная неделя</option>
          </select>
        </div>

        {importResult && (
          <div style={{ marginTop: 14 }}>
            <div className="alert alert--success" style={{ marginBottom: 0 }}>
              Импорт завершён: добавлено {importResult.created}, пропущено дублей{' '}
              {importResult.skipped}
            </div>
            {importResult.errors.length > 0 && (
              <ul className="upload__errors">
                {importResult.errors.map((err) => (
                  <li key={err}>{err}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {error && <div className="alert alert--error">{error}</div>}

      {items === null ? (
        <div className="loading">Загрузка…</div>
      ) : items.length === 0 ? (
        <div className="card">
          <div className="table__empty" style={{ padding: 28 }}>
            Расписание пусто — загрузите Excel-файл или добавьте занятия через API
          </div>
        </div>
      ) : (
        WEEKDAYS.map((dayName, index) => {
          const dayItems = byWeekday.get(index + 1)
          if (!dayItems || dayItems.length === 0) return null
          return (
            <section key={dayName} className="section card">
              <h2>{dayName}</h2>
              <table className="table">
                <thead>
                  <tr>
                    <th>Время</th>
                    <th>Группа</th>
                    <th>Дисциплина</th>
                    <th>Неделя</th>
                    <th>Преподаватель</th>
                    <th>Аудитория</th>
                  </tr>
                </thead>
                <tbody>
                  {dayItems.map((item) => (
                    <tr key={item.id}>
                      <td>
                        {item.starts_at.slice(0, 5)}–{item.ends_at.slice(0, 5)}
                      </td>
                      <td>{item.group.name}</td>
                      <td>
                        {item.discipline.name}
                        {item.lesson_type && (
                          <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                            {' '}
                            ({item.lesson_type})
                          </span>
                        )}
                      </td>
                      <td>
                        <WeekBadge week={item.week_type} />
                      </td>
                      <td>{item.teacher?.full_name ?? '—'}</td>
                      <td>{item.classroom?.number ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )
        })
      )}
    </>
  )
}
