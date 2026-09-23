import { useEffect, useRef, useState } from 'react'
import { api, isStaticData } from '../api/client'
import type { Group, ImportPreview, ImportResult, ScheduleItem, WeekType } from '../api/types'
import { managementApi } from '../api/management'
import { Modal } from '../components/Modal'
import { WeekBadge } from '../components/WeekBadge'
import { fmtTime } from '../lib/format'
import { useSession } from '../auth/SessionProvider'
import { mayOperate } from '../auth/permissions'

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
  const { user } = useSession()
  const [items, setItems] = useState<ScheduleItem[] | null>(null)
  const [groups, setGroups] = useState<Group[]>([])
  const [groupFilter, setGroupFilter] = useState<number | ''>('')
  const [weekFilter, setWeekFilter] = useState<'all' | WeekType>('all')
  const [error, setError] = useState<string | null>(null)
  const [importResult, setImportResult] = useState<ImportResult | null>(null)
  const [uploading, setUploading] = useState(false)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [confirmError, setConfirmError] = useState<string | null>(null)
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
      setPreview(await managementApi.previewSchedule(file))
      setConfirmError(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setUploading(false)
      if (fileInput.current) fileInput.current.value = ''
    }
  }

  const confirmImport = async () => {
    if (!preview || uploading) return
    setUploading(true); setConfirmError(null)
    try {
      setImportResult(await managementApi.confirmSchedule(preview.preview_id))
      setPreview(null)
      const [nextItems, nextGroups] = await Promise.all([api.getSchedule(groupFilter === '' ? undefined : { group_id: groupFilter }), api.getGroups()])
      setItems(nextItems); setGroups(nextGroups)
    } catch (e) { setConfirmError((e as Error).message) }
    finally { setUploading(false) }
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
            aria-label="Группа"
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
            aria-label="Неделя"
            className="select"
            value={weekFilter}
            onChange={(e) => setWeekFilter(e.target.value as 'all' | WeekType)}
          >
            <option value="all">Обе недели</option>
            <option value="white">Белая неделя</option>
            <option value="green">Зелёная неделя</option>
          </select>
          {!isStaticData && user && mayOperate(user.role) && (
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
      {preview && <Modal title="Предпросмотр импорта" wide onClose={() => { if (!uploading) setPreview(null) }}>
        <p>Будет добавлено: {preview.created}. Дубликатов: {preview.skipped}. Расписание пока не изменено.</p>
        <p className="metric-note">Подтверждение доступно до {new Date(preview.expires_at).toLocaleString('ru-RU')}.</p>
        {preview.errors.length > 0 && <div className="alert alert--error" role="alert"><p>Исправьте ошибки в исходном файле. Импорт не применён.</p><ul>{preview.errors.map((message, i) => <li key={i}>{message}</li>)}</ul></div>}
        <div className="table-wrap" tabIndex={0} role="region" aria-label="Строки импорта"><table className="table"><thead><tr><th>Группа</th><th>Дисциплина</th><th>Преподаватель</th><th>Аудитория</th><th>День</th><th>Время</th></tr></thead><tbody>{preview.rows.map((row, i) => <tr key={i}><td>{row.group}</td><td>{row.discipline}</td><td>{row.teacher ?? '—'}</td><td>{row.classroom ?? '—'}</td><td>{WEEKDAYS[row.weekday - 1]}</td><td>{fmtTime(row.starts_at)} — {fmtTime(row.ends_at)}</td></tr>)}</tbody></table></div>
        {confirmError && <p className="alert alert--error" role="alert">{confirmError}</p>}
        <div className="modal__actions"><button className="btn btn--ghost" disabled={uploading} onClick={() => setPreview(null)}>Отмена</button><button className="btn" disabled={uploading || preview.errors.length > 0 || new Date(preview.expires_at).getTime() <= Date.now()} onClick={() => void confirmImport()}>{uploading ? 'Применение…' : 'Подтвердить импорт'}</button></div>
      </Modal>}

      {error && <div className="alert alert--error" role="alert">{error}</div>}
      {items && items.length > 0 && visible.length === 0 && <div className="empty">По выбранным условиям занятий нет<button className="btn btn--ghost" onClick={() => { setGroupFilter(''); setWeekFilter('all') }}>Сбросить фильтры</button></div>}

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
