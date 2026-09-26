import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { Session } from '../api/types'
import { shiftDate, today } from '../lib/format'
import { IconChevronLeft, IconChevronRight, IconClose, IconExternal } from './icons'

export function presentationSteps(sessions: Session[], date: string) {
  const first = [...sessions].sort((a, b) => a.schedule.starts_at.localeCompare(b.schedule.starts_at) || a.id - b.id)[0]
  const analytics = new URLSearchParams({ from: shiftDate(date, -13), to: date })
  if (first) analytics.set('group', String(first.schedule.group.id))
  return [
    { label: 'Обзор', to: '/' },
    { label: 'Распознавание', to: '/recognition' },
    { label: first ? 'Первое занятие' : 'Занятия: нет данных', to: first ? `/sessions/${first.id}?date=${date}` : `/sessions?date=${date}` },
    { label: 'Аналитика', to: `/analytics?${analytics}` },
  ]
}

type Run = { steps: ReturnType<typeof presentationSteps>; returnTo: string }

export function PresentationControls({ onActiveChange }: { onActiveChange: (active: boolean) => void }) {
  const [run, setRun] = useState<Run | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fullscreen, setFullscreen] = useState(false)
  const trigger = useRef<HTMLButtonElement>(null)
  const ownsFullscreen = useRef(false)
  const requestVersion = useRef(0)
  const navigate = useNavigate()
  const location = useLocation()
  const index = run?.steps.findIndex(step => step.to.split('?')[0] === location.pathname) ?? -1

  useEffect(() => {
    onActiveChange(!!run)
    return () => onActiveChange(false)
  }, [run, onActiveChange])
  useEffect(() => () => { requestVersion.current += 1 }, [])

  const exit = useCallback((restore = false) => {
    if (restore && run) navigate(run.returnTo, { replace: true })
    setRun(null); setError(null); setFullscreen(false)
    if (ownsFullscreen.current && document.fullscreenElement) {
      ownsFullscreen.current = false
      void document.exitFullscreen().catch(() => {})
    }
    requestAnimationFrame(() => trigger.current?.focus())
  }, [run, navigate])

  useEffect(() => {
    if (!run) return
    const onKey = (event: KeyboardEvent) => {
      // A nested dialog owns Escape until it closes.
      if (event.key === 'Escape' && !document.querySelector('[role="dialog"]')) {
        event.preventDefault(); exit()
      }
    }
    const onFullscreen = () => {
      setFullscreen(!!document.fullscreenElement)
      if (ownsFullscreen.current && !document.fullscreenElement) {
        ownsFullscreen.current = false; exit()
      }
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('fullscreenchange', onFullscreen)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('fullscreenchange', onFullscreen)
    }
  }, [run, exit])

  async function start() {
    const version = ++requestVersion.current
    setLoading(true); setError(null)
    const requestedDate = new URLSearchParams(location.search).get('date')
    const date = requestedDate && /^\d{4}-\d{2}-\d{2}$/.test(requestedDate) && !Number.isNaN(Date.parse(requestedDate)) ? requestedDate : today()
    try {
      const steps = presentationSteps(await api.getSessions(date), date)
      if (version !== requestVersion.current) return
      setRun({ steps, returnTo: location.pathname + location.search + location.hash })
      navigate(steps[0].to)
    } catch (e) {
      if (version === requestVersion.current) setError((e as Error).message)
    } finally {
      if (version === requestVersion.current) setLoading(false)
    }
  }

  async function toggleFullscreen() {
    setError(null)
    try {
      if (document.fullscreenElement) {
        ownsFullscreen.current = false
        await document.exitFullscreen()
      } else {
        await document.documentElement.requestFullscreen()
        ownsFullscreen.current = true
      }
      setFullscreen(!!document.fullscreenElement)
    } catch {
      setError('Полный экран недоступен. Показ продолжается в окне.')
    }
  }

  if (!run) return <div className="presentation-entry">
    <button ref={trigger} className="btn btn--ghost btn--sm" disabled={loading} onClick={() => void start()}>{loading ? 'Подготовка показа…' : 'Режим показа'}</button>
    {error && <p role="alert" className="alert alert--error">{error}</p>}
  </div>

  return <section className="presentation-controls" aria-label="Навигация показа">
    <p className="presentation-step" role="status" aria-live="polite">{index < 0 ? 'Вне сценария' : `${index + 1} / ${run.steps.length} · ${run.steps[index].label}`}</p>
    <div className="presentation-actions">
      <button className="btn btn--ghost" disabled={index <= 0} onClick={() => navigate(run.steps[index - 1].to)}><IconChevronLeft />Назад</button>
      <button className="btn" disabled={index === run.steps.length - 1} onClick={() => navigate(run.steps[index + 1].to)}>Далее<IconChevronRight /></button>
      {document.fullscreenEnabled && <button className="btn btn--ghost" aria-pressed={fullscreen} onClick={() => void toggleFullscreen()}><IconExternal />Полный экран</button>}
      <button className="btn btn--ghost" onClick={() => exit()}><IconClose />Выйти из показа</button>
      <button className="btn btn--ghost" onClick={() => exit(true)}>Вернуться к работе</button>
    </div>
    {error && <p role="alert" className="alert alert--error">{error}</p>}
  </section>
}
