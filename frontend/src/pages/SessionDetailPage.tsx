import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { Capture, CaptureMedia, MeasurementDetail, SessionDetail } from '../api/types'
import { IconExternal } from '../components/icons'
import { RateCell } from '../components/RateCell'
import { WeekBadge } from '../components/WeekBadge'
import {
  CALCULATION_STATUS,
  CAPTURE_STATUS,
  MEASUREMENT_STATUS,
  Pill,
  SESSION_STATUS,
} from '../components/status'
import { fmtBytes, fmtClock, fmtDateHuman, fmtTime } from '../lib/format'

const REFRESH_INTERVAL_MS = 10000

const MEASUREMENT_TITLES: Record<string, { title: string; note: string }> = {
  after_start: { title: 'Первый замер', note: 'через 15 минут после начала' },
  before_end: { title: 'Второй замер', note: 'за 15 минут до окончания' },
}

const ACTIVE_MEASUREMENT = new Set(['scheduled', 'capturing', 'recognizing'])

function CaptureBlock({ capture }: { capture: Capture }) {
  const [media, setMedia] = useState<CaptureMedia | null>(null)
  const requested = useRef(false)

  useEffect(() => {
    if (capture.result && !requested.current) {
      requested.current = true
      api
        .getCaptureMedia(capture.id)
        .then(setMedia)
        .catch(() => setMedia(null))
    }
  }, [capture.result, capture.id])

  const openVideo = async () => {
    // Ссылка временная, поэтому запрашивается свежая на момент клика
    const links = await api.getCaptureMedia(capture.id)
    if (links.video_url) window.open(links.video_url, '_blank', 'noopener')
  }

  const result = capture.result
  return (
    <div className="capture">
      <div className="capture__head">
        <span className="capture__camera">{capture.camera.name}</span>
        <span style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}>
          {capture.attempts > 1 && (
            <span className="frame-note">попытка {capture.attempts}</span>
          )}
          <Pill info={CAPTURE_STATUS[capture.status]} />
        </span>
      </div>

      {capture.error && capture.status !== 'completed' && (
        <div className="capture__error">{capture.error}</div>
      )}

      {result && (
        <>
          <dl className="capture__metrics">
            <div>
              <dt>Людей</dt>
              <dd>{result.people_count}</dd>
            </div>
            <div>
              <dt>Медиана</dt>
              <dd>{result.detected_median}</dd>
            </div>
            <div>
              <dt>P75</dt>
              <dd>{result.detected_percentile_75}</dd>
            </div>
            <div>
              <dt>Максимум</dt>
              <dd>{result.detected_max}</dd>
            </div>
            <div>
              <dt>Уверенность</dt>
              <dd>
                {result.average_confidence !== null
                  ? `${Math.round(result.average_confidence * 100)}%`
                  : '—'}
              </dd>
            </div>
            <div>
              <dt>Кадров</dt>
              <dd>{result.sampled_frames}</dd>
            </div>
          </dl>

          <div className="capture__media">
            {media?.annotated_url ? (
              <a href={media.annotated_url} target="_blank" rel="noopener noreferrer">
                <img
                  className="frame-preview"
                  src={media.annotated_url}
                  alt={`Размеченный кадр, камера ${capture.camera.name}`}
                />
              </a>
            ) : (
              media?.annotated_unavailable_reason && (
                <span className="frame-note">{media.annotated_unavailable_reason}</span>
              )
            )}
          </div>

          <div style={{ display: 'flex', gap: 10, marginTop: 10, alignItems: 'center' }}>
            {capture.has_video && media?.video_url !== undefined && media?.video_url !== null ? (
              <button className="btn btn--ghost btn--sm" onClick={openVideo}>
                Смотреть видео <IconExternal />
              </button>
            ) : (
              media?.video_unavailable_reason && (
                <span className="frame-note">{media.video_unavailable_reason}</span>
              )
            )}
            <span className="frame-note">
              ролик {fmtBytes(capture.size_bytes)}
              {capture.duration_ms ? ` · ${Math.round(capture.duration_ms / 1000)} c` : ''}
            </span>
          </div>
        </>
      )}
    </div>
  )
}

function MeasurementCard({ measurement }: { measurement: MeasurementDetail }) {
  const titles = MEASUREMENT_TITLES[measurement.type]
  return (
    <div className="card">
      <div className="measurement-card__head">
        <span className="measurement-card__title">{titles.title}</span>
        <Pill info={MEASUREMENT_STATUS[measurement.status]} />
      </div>
      <div className="measurement-card__planned">
        {titles.note} · план {fmtClock(measurement.planned_at)}
      </div>

      {measurement.final_people_count !== null && (
        <div className="measurement-card__total">
          <span className="measurement-card__count">{measurement.final_people_count}</span>
          <span className="measurement-card__unit">
            человек
            {measurement.confidence !== null &&
              ` · уверенность ${Math.round(measurement.confidence * 100)}%`}
          </span>
        </div>
      )}

      {measurement.error && measurement.status === 'failed' && (
        <div className="capture__error">{measurement.error}</div>
      )}

      {measurement.captures.map((capture) => (
        <CaptureBlock key={capture.id} capture={capture} />
      ))}
      {measurement.captures.length === 0 && (
        <div className="frame-note" style={{ marginTop: 8 }}>
          Задания записи ещё не созданы
        </div>
      )}
    </div>
  )
}

export function SessionDetailPage() {
  const { id } = useParams()
  const sessionId = Number(id)
  const [session, setSession] = useState<SessionDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cancelling, setCancelling] = useState(false)

  const load = useCallback(() => {
    api
      .getSession(sessionId)
      .then(setSession)
      .catch((e: Error) => setError(e.message))
  }, [sessionId])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    const active =
      session &&
      session.status !== 'cancelled' &&
      (session.status === 'in_progress' ||
        session.measurements.some((m) => ACTIVE_MEASUREMENT.has(m.status)))
    if (!active) return
    const timer = setInterval(load, REFRESH_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [session, load])

  const cancel = async () => {
    if (!window.confirm('Отменить занятие и все его замеры?')) return
    setCancelling(true)
    try {
      await api.cancelSession(sessionId)
      load()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setCancelling(false)
    }
  }

  if (error) return <div className="alert alert--error">{error}</div>
  if (!session) return <div className="loading">Загрузка…</div>

  const { schedule, attendance } = session
  const canCancel = session.status === 'scheduled' || session.status === 'in_progress'

  return (
    <>
      <div className="breadcrumbs">
        <Link to={`/sessions?date=${session.date}`}>Занятия</Link>
        {' / '}
        {fmtDateHuman(session.date)}
      </div>

      <header className="page-header">
        <div>
          <h1>
            {schedule.discipline.name}
            {schedule.lesson_type && (
              <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>
                {' '}
                · {schedule.lesson_type}
              </span>
            )}
          </h1>
          <dl className="session-meta">
            <div>
              <dt>Группа</dt>
              <dd>{schedule.group.name}</dd>
            </div>
            <div>
              <dt>Время</dt>
              <dd className="num">
                {fmtTime(schedule.starts_at)}–{fmtTime(schedule.ends_at)}
              </dd>
            </div>
            <div>
              <dt>Аудитория</dt>
              <dd>{schedule.classroom?.number ?? '—'}</dd>
            </div>
            <div>
              <dt>Преподаватель</dt>
              <dd>{schedule.teacher?.full_name ?? '—'}</dd>
            </div>
            <div>
              <dt>Неделя</dt>
              <dd>
                <WeekBadge week={schedule.week_type} />
                {schedule.week_type === 'every' && 'каждая'}
              </dd>
            </div>
            <div>
              <dt>Статус</dt>
              <dd>
                <Pill info={SESSION_STATUS[session.status]} />
              </dd>
            </div>
          </dl>
        </div>
        {canCancel && (
          <button className="btn btn--danger-ghost" onClick={cancel} disabled={cancelling}>
            Отменить занятие
          </button>
        )}
      </header>

      {attendance && (
        <div className="grid grid--stats section">
          <div className="card">
            <div className="stat-card__label">Посещаемость</div>
            <div className="stat-card__value">
              {attendance.attendance_rate !== null ? (
                <RateCell
                  rate={attendance.attendance_rate}
                  detail={`из ${attendance.expected_count}`}
                />
              ) : (
                '—'
              )}
            </div>
            {attendance.attendance_rate === null && attendance.expected_count === 0 && (
              <div className="stat-card__hint">не указана численность группы</div>
            )}
          </div>
          <div className="card">
            <div className="stat-card__label">Первый замер</div>
            <div className="stat-card__value">{attendance.after_start_count ?? '—'}</div>
            <div className="stat-card__hint">после начала занятия</div>
          </div>
          <div className="card">
            <div className="stat-card__label">Второй замер</div>
            <div className="stat-card__value">{attendance.before_end_count ?? '—'}</div>
            <div className="stat-card__hint">перед окончанием</div>
          </div>
          <div className="card">
            <div className="stat-card__label">Полнота данных</div>
            <div style={{ marginTop: 6 }}>
              <Pill info={CALCULATION_STATUS[attendance.calculation_status]} />
            </div>
          </div>
        </div>
      )}

      <div className="grid grid--two">
        {session.measurements.map((m) => (
          <MeasurementCard key={m.id} measurement={m} />
        ))}
        {session.measurements.length === 0 && (
          <div className="card empty">
            Замеры ещё не запланированы
            <small>Scheduler создаёт их автоматически в пределах горизонта планирования</small>
          </div>
        )}
      </div>
    </>
  )
}
