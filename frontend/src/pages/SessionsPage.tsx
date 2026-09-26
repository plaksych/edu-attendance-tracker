import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { Measurement, Session, WeekType } from '../api/types'
import { IconChevronLeft, IconChevronRight } from '../components/icons'
import { RateCell } from '../components/RateCell'
import { Dot, MEASUREMENT_STATUS, Pill, SESSION_STATUS } from '../components/status'
import { fmtClock, fmtTime, shiftDate, today } from '../lib/format'

const REFRESH_INTERVAL_MS = 15000

const ACTIVE_MEASUREMENT = new Set(['scheduled', 'capturing', 'recognizing'])

function MeasureChip({ measurement, label }: { measurement?: Measurement; label: string }) {
  if (!measurement) {
    return (
      <span className="measure-chip">
        <span className="measure-chip__dot dot--gray" />
        {label} —
      </span>
    )
  }
  const info = MEASUREMENT_STATUS[measurement.status]
  return (
    <span className="measure-chip" title={`${info.label}${measurement.error ? `: ${measurement.error}` : ''}`}>
      <Dot info={info} />
      {label} · {fmtClock(measurement.planned_at)}
      {measurement.final_people_count !== null && (
        <span className="measure-chip__count">{measurement.final_people_count} чел.</span>
      )}
    </span>
  )
}

export function SessionsPage() {
  const [params, setParams] = useSearchParams()
  const date = params.get('date') ?? today()
  const groupFilter = params.get('group') ?? ''
  const statusFilter = params.get('status') ?? ''
  const search = params.get('q') ?? ''
  const [sessions, setSessions] = useState<Session[] | null>(null)
  const [week, setWeek] = useState<WeekType | null>(null)
  const [error, setError] = useState<string | null>(null)
  const sequence = useRef(0)

  const filter = (key: string, value: string) => setParams(current => { const next = new URLSearchParams(current); if (value) next.set(key, value); else next.delete(key); return next })
  const setDate = (next: string) => filter('date', next === today() ? '' : next)

  const load = useCallback(() => {
    const current = ++sequence.current
    api
      .getSessions(date)
      .then(data => { if (sequence.current === current) { setSessions(data); setError(null) } })
      .catch((e: Error) => { if (sequence.current === current) setError(e.message) })
  }, [date])

  useEffect(() => {
    setSessions(null)
    setError(null)
    load()
    api
      .getWeekType(date)
      .then((info) => setWeek(info.week_type))
      .catch(() => setWeek(null))
  }, [date, load])

  // Пока идут занятия или замеры, данные обновляются автоматически
  useEffect(() => {
    const active = sessions?.some(
      (s) =>
        s.status === 'in_progress' ||
        s.measurements.some((m) => ACTIVE_MEASUREMENT.has(m.status)),
    )
    if (!active) return
    const timer = setInterval(load, REFRESH_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [sessions, load])

  const isToday = date === today()
  const groups = [...new Map((sessions ?? []).map(s => [s.schedule.group.id, s.schedule.group])).values()]
  const visible = (sessions ?? []).filter(s => (!groupFilter || String(s.schedule.group.id) === groupFilter) && (!statusFilter || s.status === statusFilter) && (!search || `${s.schedule.discipline.name} ${s.schedule.teacher?.full_name ?? ''} ${s.schedule.classroom?.number ?? ''}`.toLocaleLowerCase('ru-RU').includes(search.toLocaleLowerCase('ru-RU'))))

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Занятия</h1>
          <p>Состояние двух замеров и посещаемость по каждому занятию дня</p>
        </div>
        <div className="page-header__actions">
          {week && (
            <span className={`week-chip${week === 'green' ? ' week-chip--green' : ''}`}>
              {week === 'green' ? 'Зелёная неделя' : 'Белая неделя'}
            </span>
          )}
          <button
            className="icon-button"
            type="button"
            aria-label="Предыдущий день"
            title="Предыдущий день"
            onClick={() => setDate(shiftDate(date, -1))}
          >
            <IconChevronLeft />
          </button>
          <input
            aria-label="Дата занятий"
            type="date"
            className="input"
            value={date}
            onChange={(e) => e.target.value && setDate(e.target.value)}
          />
          <button
            className="icon-button"
            type="button"
            aria-label="Следующий день"
            title="Следующий день"
            onClick={() => setDate(shiftDate(date, 1))}
          >
            <IconChevronRight />
          </button>
          {!isToday && (
            <button className="btn btn--ghost" onClick={() => setDate(today())}>
              Сегодня
            </button>
          )}
        </div>
      </header>
      <div className="filter-bar">
        <label className="field">Поиск<input className="input" type="search" value={search} onChange={e => filter('q', e.target.value)} placeholder="Дисциплина, преподаватель, аудитория" /></label>
        <label className="field">Группа<select className="select" value={groupFilter} onChange={e => filter('group', e.target.value)}><option value="">Все группы</option>{groups.map(g => <option value={g.id} key={g.id}>{g.name}</option>)}</select></label>
        <label className="field">Статус<select className="select" value={statusFilter} onChange={e => filter('status', e.target.value)}><option value="">Все статусы</option>{Object.entries(SESSION_STATUS).map(([value, info]) => <option key={value} value={value}>{info.label}</option>)}</select></label>
        {(groupFilter || statusFilter || search) && <button className="btn btn--ghost" onClick={() => setParams({ date })}>Сбросить фильтры</button>}
        {sessions && <span className="metric-note" role="status">Найдено: {visible.length}</span>}
      </div>

      {error && <div className="alert alert--error" role="alert">{error}<button className="btn btn--ghost" onClick={load}>Повторить</button></div>}

      <div className="table-wrap">
        {sessions === null ? (
          <div className="loading" style={{ padding: 24 }}>
            Загрузка…
          </div>
        ) : (
          <table className="table table--hover">
            <thead>
              <tr>
                <th>Время</th>
                <th>Группа</th>
                <th>Дисциплина</th>
                <th>Аудитория</th>
                <th>Статус</th>
                <th>Замеры</th>
                <th>Посещаемость</th>
              </tr>
            </thead>
            <tbody>
              {visible.length === 0 && (
                <tr>
                  <td colSpan={7} className="table__empty">
                    {sessions.length ? 'По выбранным условиям занятий нет' : 'На выбранную дату занятий нет'}
                    <small>{sessions.length ? 'Измените условия поиска или сбросьте фильтры' : 'Занятия появляются после планирования по расписанию'}</small>
                  </td>
                </tr>
              )}
              {visible.map((s) => {
                const byType = new Map(s.measurements.map((m) => [m.type, m]))
                return (
                  <tr key={s.id}>
                    <td className="num">
                      {fmtTime(s.schedule.starts_at)}–{fmtTime(s.schedule.ends_at)}
                    </td>
                    <td>
                      <div className="cell-main">{s.schedule.group.name}</div>
                    </td>
                    <td>
                      <Link className="cell-main text-link" to={`/sessions/${s.id}`} state={{ from: `/sessions?${params}` }}>{s.schedule.discipline.name}</Link>
                      <div className="cell-sub">
                        {s.schedule.teacher?.full_name ?? 'преподаватель не указан'}
                        {s.schedule.lesson_type ? ` · ${s.schedule.lesson_type}` : ''}
                      </div>
                    </td>
                    <td>{s.schedule.classroom?.number ?? '—'}</td>
                    <td>
                      <Pill info={SESSION_STATUS[s.status]} />
                    </td>
                    <td>
                      <div className="measurements">
                        <MeasureChip measurement={byType.get('after_start')} label="1-й" />
                        <MeasureChip measurement={byType.get('before_end')} label="2-й" />
                      </div>
                    </td>
                    <td>
                      <RateCell
                        rate={s.attendance?.attendance_rate ?? null}
                        detail={
                          s.attendance?.detected_average != null
                            ? `~${Math.round(s.attendance.detected_average)} из ${s.attendance.expected_count}`
                            : undefined
                        }
                      />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}
