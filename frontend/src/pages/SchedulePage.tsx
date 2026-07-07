import { useEffect, useRef, useState } from 'react'
import { api, isStaticData } from '../api/client'
import type { Group, ImportResult, ScheduleItem, WeekType } from '../api/types'
import { WeekBadge } from '../components/WeekBadge'
import { fmtTime } from '../lib/format'

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
      const [refreshedItems, refreshedGroups] = await Promise.all([
        api.getSchedule(groupFilter === '' ? undefined : { group_id: groupFilter }),
        api.getGroups(),
      ])
      setItems(refreshedItems)
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
        <div>
          <h1>Расписание</h1>
          <p>Недельная сетка занятий с чередованием белой и зелёной недели</p>
        </div>
        <div className="page-header__actions">
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
          {!isStaticData && (
            <>
              <a className="btn btn--ghost" href="/api/v1/schedule/template" download>
                Шаблон
              </a>
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
              <button className="btn" disabled={uploading} onClick={() => fileInput.current?.click()}>
                {uploading ? 'Загрузка…' : 'Загрузить из Excel'}
              </button>
            </>
          )}
        </div>
      </header>

      {importResult && (
        <>
          <div className="alert alert--success">
            Импорт завершён: добавлено {importResult.created}, пропущено дублей{' '}
            {importResult.skipped}
          </div>
          {importResult.errors.length > 0 && (
            <div className="alert alert--error">
              Часть строк не распознана:
              <ul className="upload-errors">
                {importResult.errors.slice(0, 10).map((err) => (
                  <li key={err}>{err}</li>
                ))}
                {importResult.errors.length > 10 && (
                  <li>… и ещё {importResult.errors.length - 10}</li>
                )}
              </ul>
            </div>
          )}
        </>
      )}

      {error && <div className="alert alert--error">{error}</div>}

      {items === null ? (
        <div className="loading">Загрузка…</div>
      ) : items.length === 0 ? (
        <div className="card empty">
          Расписание пусто
          <small>Загрузите файл Excel — поддерживается институтская сетка и построчный шаблон</small>
        </div>
      ) : (
        WEEKDAYS.map((dayName, index) => {
          const dayItems = byWeekday.get(index + 1)
          if (!dayItems || dayItems.length === 0) return null
          return (
            <section key={dayName} className="section">
              <h2>{dayName}</h2>
              <div className="table-wrap">
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
                        <td className="num">
                          {fmtTime(item.starts_at)}–{fmtTime(item.ends_at)}
                        </td>
                        <td className="cell-main">{item.group.name}</td>
                        <td>
                          {item.discipline.name}
                          {item.lesson_type && (
                            <span style={{ color: 'var(--text-faint)', fontSize: 12.5 }}>
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
              </div>
            </section>
          )
        })
      )}
    </>
  )
}
