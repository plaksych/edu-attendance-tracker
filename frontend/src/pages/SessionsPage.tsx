import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Session, WeekType } from '../api/types'
import { RateBadge } from '../components/RateBadge'
import { StatusBadge } from '../components/StatusBadge'

const REFRESH_INTERVAL_MS = 15000

function today(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

export function SessionsPage() {
  const [date, setDate] = useState(today())
  const [sessions, setSessions] = useState<Session[] | null>(null)
  const [week, setWeek] = useState<WeekType | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pendingId, setPendingId] = useState<number | null>(null)

  const load = useCallback(() => {
    api
      .getSessions(date)
      .then(setSessions)
      .catch((e: Error) => setError(e.message))
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

  // Пока есть идущие занятия, периодически подтягиваем свежие данные
  useEffect(() => {
    if (!sessions?.some((s) => s.status === 'in_progress')) return
    const timer = setInterval(load, REFRESH_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [sessions, load])

  const act = async (id: number, action: 'start' | 'finish') => {
    setPendingId(id)
    setError(null)
    try {
      if (action === 'start') await api.startSession(id)
      else await api.finishSession(id)
      load()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setPendingId(null)
    }
  }

  const isToday = date === today()

  return (
    <>
      <header className="page-header">
        <h1>Занятия</h1>
        <p>Запуск и остановка распознавания по занятиям дня</p>
      </header>

      <div className="section__controls">
        <input
          type="date"
          className="input"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />
        {!isToday && (
          <button className="btn btn--secondary" onClick={() => setDate(today())}>
            Сегодня
          </button>
        )}
        {week && (
          <span className={`week-chip${week === 'green' ? ' week-chip--green' : ''}`}>
            {week === 'green' ? 'Зелёная неделя' : 'Белая неделя'}
          </span>
        )}
      </div>

      {error && <div className="alert alert--error">{error}</div>}

      <div className="card">
        {sessions === null ? (
          <div className="loading">Загрузка…</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Время</th>
                <th>Группа</th>
                <th>Дисциплина</th>
                <th>Преподаватель</th>
                <th>Аудитория</th>
                <th>Статус</th>
                <th>Посещаемость</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {sessions.length === 0 && (
                <tr>
                  <td colSpan={8} className="table__empty">
                    На выбранную дату занятий нет
                  </td>
                </tr>
              )}
              {sessions.map((s) => (
                <tr key={s.id}>
                  <td>
                    {s.schedule.starts_at.slice(0, 5)}–{s.schedule.ends_at.slice(0, 5)}
                  </td>
                  <td>{s.schedule.group.name}</td>
                  <td>
                    {s.schedule.discipline.name}
                    {s.schedule.lesson_type && (
                      <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                        {' '}
                        ({s.schedule.lesson_type})
                      </span>
                    )}
                  </td>
                  <td>{s.schedule.teacher?.full_name ?? '—'}</td>
                  <td>{s.schedule.classroom?.number ?? '—'}</td>
                  <td>
                    <StatusBadge status={s.status} />
                  </td>
                  <td>
                    {s.attendance ? (
                      <>
                        <RateBadge rate={s.attendance.attendance_rate} />{' '}
                        <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                          (~{Math.round(s.attendance.detected_avg)} из{' '}
                          {s.attendance.expected_count})
                        </span>
                      </>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td>
                    {isToday && s.status === 'scheduled' && (
                      <button
                        className="btn"
                        disabled={pendingId === s.id}
                        onClick={() => act(s.id, 'start')}
                      >
                        Начать
                      </button>
                    )}
                    {s.status === 'in_progress' && (
                      <button
                        className="btn btn--danger"
                        disabled={pendingId === s.id}
                        onClick={() => act(s.id, 'finish')}
                      >
                        Завершить
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}
