import { FormEvent, lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, isStaticData } from '../api/client'
import type {
  RecognitionEvaluationSummary,
  RecognitionStatus,
  RecognitionUpload,
  RecognitionUploadMedia,
} from '../api/types'
import { IconImage, IconRecognition, IconRefresh, IconUpload, IconVideo } from '../components/icons'
import { ProvenanceBadge } from '../components/Provenance'
import { RecognitionHistory } from '../components/RecognitionHistory'
import { managementApi, type Capabilities } from '../api/management'
import type { SessionDetail } from '../api/types'
const LocalRecognitionDialog = lazy(() => import('../components/LocalRecognitionDialog').then(m => ({ default: m.LocalRecognitionDialog })))
import { Modal } from '../components/Modal'
import { StatCard } from '../components/StatCard'
import { fmtBytes, fmtClock } from '../lib/format'

const ACTIVE_STATUSES = new Set<RecognitionStatus>(['pending', 'processing', 'retry_wait'])

const STATUS_LABEL: Record<RecognitionStatus, string> = {
  pending: 'В очереди',
  processing: 'Обработка',
  retry_wait: 'Повтор',
  completed: 'Готово',
  failed: 'Ошибка',
  cancelled: 'Отменено',
}

const STATUS_TONE: Record<RecognitionStatus, string> = {
  pending: 'gray',
  processing: 'blue',
  retry_wait: 'amber',
  completed: 'green',
  failed: 'red',
  cancelled: 'gray',
}


function Status({ status }: { status: RecognitionStatus }) {
  return <span className={`pill pill--${STATUS_TONE[status]}`}>{STATUS_LABEL[status]}</span>
}

function pct(value: number | null): string {
  return value === null ? '—' : `${Math.round(value * 100)}%`
}

function FramePreview({ upload, media }: { upload: RecognitionUpload; media: RecognitionUploadMedia | null }) {
  const [annotated, setAnnotated] = useState(true)
  const [zoom, setZoom] = useState(1)
  const result = upload.job.result
  const source = annotated ? media?.annotated_url : upload.media_type === 'image' ? media?.source_url : null
  if (!source || !result) {
    return <div className="recognition-frame__empty">{media?.annotated_unavailable_reason ?? 'Контрольный кадр пока недоступен'}</div>
  }
  return (
    <><div className="media-controls">
      {!isStaticData && upload.media_type === 'image' && media?.source_url && <label><input type="checkbox" checked={annotated} onChange={e => setAnnotated(e.target.checked)} /> Разметка</label>}
      <label>Масштаб <input aria-label="Масштаб кадра" type="range" min="1" max="3" step="0.25" value={zoom} onChange={e => setZoom(Number(e.target.value))} /></label>
      <button className="btn btn--ghost btn--sm" onClick={() => setZoom(1)}>Сбросить масштаб</button>
    </div><div className="media-viewport"><div className="recognition-frame" style={{ width: `${zoom * 100}%`, maxWidth: 'none' }}>
      <img src={source} alt={`${isStaticData ? 'Синтетическая схема, не результат инференса' : 'Контрольный кадр'}: ${upload.label ?? upload.filename}`} />
    </div></div></>
  )
}

function UploadDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (upload: RecognitionUpload) => void }) {
  const [params] = useSearchParams()
  const [sessionId, setSessionId] = useState(params.get('session_id') ?? '')
  const [measurementId, setMeasurementId] = useState(params.get('measurement_id') ?? '')
  const [session, setSession] = useState<SessionDetail | null>(null)
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null)
  const [configError, setConfigError] = useState<string | null>(null)
  const [configRevision, setConfigRevision] = useState(0)
  const submission = useRef<{ fingerprint: string; key: string } | null>(null)
  const pending = useRef(false)
  const [file, setFile] = useState<File | null>(null)
  const [label, setLabel] = useState('')
  const [reference, setReference] = useState('')
  const [sampleRate, setSampleRate] = useState('1')
  const [confidence, setConfidence] = useState('0.35')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let active = true
    setConfigError(null)
    managementApi.capabilities().then(value => { if (active) setCapabilities(value) }).catch(e => { if (active) setConfigError(e.message) })
    return () => { active = false }
  }, [configRevision])
  useEffect(() => {
    let active = true
    setSession(null)
    if (sessionId && Number.isSafeInteger(Number(sessionId)) && Number(sessionId) > 0) api.getSession(Number(sessionId)).then(value => { if (active) setSession(value) }).catch(() => { if (active) setSession(null) })
    return () => { active = false }
  }, [sessionId])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (pending.current || !capabilities) return
    if (!file) {
      setError('Выберите видео или изображение')
      return
    }
    const referencePeopleCount = reference === '' ? undefined : Number(reference)
    if (file.size === 0 || file.size > capabilities.max_size_bytes) { setError(`Допустимый размер: от 1 байта до ${fmtBytes(capabilities.max_size_bytes)}`); return }
    if (!capabilities.formats.includes(file.name.split('.').pop()?.toLowerCase() ?? '')) { setError('Формат файла не поддерживается'); return }
    if (sessionId && !session) { setError('Укажите доступное занятие или удалите связь'); return }
    if (referencePeopleCount !== undefined && (!Number.isInteger(referencePeopleCount) || referencePeopleCount < 0)) {
      setError('Эталонное число должно быть целым неотрицательным числом')
      return
    }
    setSaving(true)
    pending.current = true
    setError(null)
    const fingerprint = JSON.stringify([file.name, file.size, file.lastModified, label, reference, sampleRate, confidence, sessionId, measurementId])
    if (submission.current?.fingerprint !== fingerprint) submission.current = { fingerprint, key: crypto.randomUUID() }
    try {
      const upload = await api.uploadRecognition({
        file,
        idempotency_key: submission.current.key,
        session_id: sessionId ? Number(sessionId) : undefined,
        measurement_id: measurementId ? Number(measurementId) : undefined,
        label: label.trim() || undefined,
        reference_people_count: referencePeopleCount,
        sample_rate_fps: Number(sampleRate),
        confidence_threshold: Number(confidence),
      })
      onCreated(upload)
      onClose()
    } catch (requestError) {
      setError((requestError as Error).message)
    } finally {
      setSaving(false)
      pending.current = false
    }
  }

  return (
    <Modal title="Новый материал" onClose={() => { if (!pending.current) onClose() }}>
      <form className="modal__form" onSubmit={submit}>
        {configError && <div role="alert" className="alert alert--error">{configError}<button type="button" className="btn btn--ghost" onClick={() => setConfigRevision(n => n + 1)}>Повторить</button></div>}
        {!capabilities && !configError && <p role="status">Получение допустимых форматов и лимитов…</p>}
        {capabilities && <p className="metric-note">До {fmtBytes(capabilities.max_size_bytes)} · видео до {capabilities.max_duration_seconds} с · до {capabilities.max_video_dimension} px по стороне · до {capabilities.max_pixels.toLocaleString('ru-RU')} пикселей. Форматы: {capabilities.formats.join(', ')}.</p>}
        <div className="field">
          <label htmlFor="recognition-file">Видео или изображение</label>
          <input
            id="recognition-file"
            className="input file-input"
            type="file"
            disabled={!capabilities || saving}
            accept={capabilities?.formats.map(format => `.${format}`).join(',')}
            onChange={(event) => { setFile(event.target.files?.[0] ?? null); submission.current = null }}
          />
          {file && <span className="field__hint">{file.name} · {fmtBytes(file.size)}</span>}
        </div>
        <label className="field">Номер занятия (необязательно)<input className="input" type="number" min="1" step="1" value={sessionId} disabled={saving} onChange={e => { setSessionId(e.target.value); setMeasurementId('') }} /></label>
        {session && <><p>{session.schedule.group.name} · {session.schedule.discipline.name} · {session.date}</p><label className="field">Замер<select className="select" value={measurementId} onChange={e => setMeasurementId(e.target.value)}><option value="">Без указания замера</option>{session.measurements.map(m => <option key={m.id} value={m.id}>{m.type === 'after_start' ? 'Первый замер' : 'Второй замер'}</option>)}</select></label></>}
        <div className="field">
          <label htmlFor="recognition-label">Название материала</label>
          <input id="recognition-label" className="input" value={label} onChange={(event) => setLabel(event.target.value)} maxLength={160} />
        </div>
        <div className="recognition-form-grid">
          <div className="field">
            <label htmlFor="recognition-reference">Эталон, человек</label>
            <input id="recognition-reference" className="input" type="number" min="0" step="1" value={reference} onChange={(event) => setReference(event.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="recognition-rate">Выборка, кадр/с</label>
            <input id="recognition-rate" className="input" required type="number" min={capabilities?.sample_rate_fps.min} max={capabilities?.sample_rate_fps.max} step="0.1" value={sampleRate} onChange={(event) => setSampleRate(event.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="recognition-confidence">Порог</label>
            <input id="recognition-confidence" className="input" required type="number" min={capabilities?.confidence.min} max={capabilities?.confidence.max} step="0.01" value={confidence} onChange={(event) => setConfidence(event.target.value)} />
          </div>
        </div>
        {error && <div className="alert alert--error">{error}</div>}
        <div className="modal__actions">
          <button type="button" className="btn btn--ghost" disabled={saving} onClick={onClose}>Отмена</button>
          <button className="btn" disabled={saving || !capabilities}>{saving ? 'Отправка…' : 'Отправить'}</button>
        </div>
      </form>
    </Modal>
  )
}

export function RecognitionPage() {
  const [params] = useSearchParams()
  const [uploads, setUploads] = useState<RecognitionUpload[] | null>(null)
  const [summary, setSummary] = useState<RecognitionEvaluationSummary | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [media, setMedia] = useState<RecognitionUploadMedia | null>(null)
  const [loadingMedia, setLoadingMedia] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(params.has('session_id'))
  const [retrying, setRetrying] = useState(false)
  const retryKeys = useRef(new Map<number, string>())

  const load = useCallback(async () => {
    try {
      const [items, nextSummary] = await Promise.all([
        api.getRecognitionUploads(),
        api.getRecognitionEvaluationSummary(),
      ])
      setUploads(items)
      setSummary(nextSummary)
      setSelectedId((current) => current ?? items[0]?.id ?? null)
      setError(null)
    } catch (requestError) {
      setError((requestError as Error).message)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const selected = uploads?.find((item) => item.id === selectedId) ?? uploads?.[0] ?? null

  useEffect(() => {
    if (!selected) {
      setMedia(null)
      return
    }
    setLoadingMedia(true)
    setMedia(null)
    let active = true
    api.getRecognitionUploadMedia(selected.id)
      .then(value => { if (active) setMedia(value) })
      .catch(() => { if (active) setMedia(null) })
      .finally(() => { if (active) setLoadingMedia(false) })
    return () => { active = false }
  }, [selected?.id, selected?.job.status, selected?.job.id])

  useEffect(() => {
    if (!uploads?.some((item) => ACTIVE_STATUSES.has(item.job.status))) return
    const timer = window.setInterval(() => void load(), 8000)
    return () => window.clearInterval(timer)
  }, [uploads, load])

  const completed = useMemo(
    () => uploads?.filter((item) => item.job.status === 'completed') ?? [],
    [uploads],
  )
  const confidences = completed.map(item => item.job.result?.average_confidence).filter((value): value is number => value !== null && value !== undefined)
  const meanConfidence = confidences.length
    ? confidences.reduce((sum, value) => sum + value, 0) / confidences.length
    : null
  const toleranceRate = summary && summary.checked_materials > 0
    ? summary.within_tolerance_count / summary.checked_materials
    : null

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Распознавание</h1>
          <p>Очередь материалов, контрольные кадры и проверка точности относительно ручного подсчёта</p>
        </div>
        <div className="page-header__actions">
          <button className="icon-button" type="button" aria-label="Обновить данные" title="Обновить данные" onClick={() => void load()}>
            <IconRefresh />
          </button>
          <button className="btn" type="button" onClick={event => { event.currentTarget.focus(); setDialogOpen(true) }}>
            <IconUpload />
            {isStaticData ? 'Проверить файл' : 'Добавить материал'}
          </button>
        </div>
      </header>

      {isStaticData && <div className="recognition-mode">Учебный пример: синтетическая схема и заранее заданное число, без инференса. Проверка своего файла выполняется отдельно в браузере.</div>}
      {error && <div className="alert alert--error" role="alert">{error}</div>}

      <section className="grid grid--stats recognition-stats">
        <StatCard label="Материалов" value={uploads?.length ?? '—'} hint={`${completed.length} завершено`} icon={<IconRecognition />} tone="teal" />
        <StatCard label="В допуске" value={pct(toleranceRate)} hint={summary ? `${summary.within_tolerance_count} из ${summary.checked_materials} с эталоном` : 'нет разметки'} icon={<IconRecognition />} tone="green" />
        <StatCard label="Средняя ошибка" value={summary?.mean_absolute_error?.toFixed(1) ?? '—'} hint={summary?.max_absolute_error !== null && summary?.max_absolute_error !== undefined ? `максимум ${summary.max_absolute_error} чел.` : 'нет разметки'} icon={<IconRecognition />} tone="amber" />
        <StatCard label="Средняя уверенность" value={pct(meanConfidence)} hint="по завершённым заданиям" icon={<IconRecognition />} tone="blue" />
      </section>

      <section className="recognition-workspace">
        <div className="card recognition-list">
          <div className="recognition-list__head">
            <div>
              <h2>Материалы</h2>
              <span>{uploads?.length ?? 0} в журнале</span>
            </div>
          </div>
          {uploads === null ? (
            <div className="loading">Загрузка…</div>
          ) : uploads.length === 0 ? (
            <div className="empty">Материалы ещё не добавлены</div>
          ) : (
            <div className="recognition-list__items">
              {uploads.map((upload) => {
                const result = upload.job.result
                const active = upload.id === selected?.id
                return (
                  <button
                    type="button"
                    className={`recognition-item${active ? ' recognition-item--active' : ''}`}
                    key={upload.id}
                    onClick={() => setSelectedId(upload.id)}
                  >
                    <span className="recognition-item__icon">{upload.media_type === 'video' ? <IconVideo /> : <IconImage />}</span>
                    <span className="recognition-item__body">
                      <span className="recognition-item__title">{upload.label ?? upload.filename}</span>
                      <span className="recognition-item__meta">{upload.filename} · {fmtBytes(upload.size_bytes)}</span>
                    </span>
                    <span className="recognition-item__result">
                      <Status status={upload.job.status} />
                      {result && <strong>{result.people_count} чел.</strong>}
                    </span>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        <div className="card recognition-inspector">
          {selected ? (
            <>
              <div className="recognition-inspector__head">
                <div>
                  <div className="recognition-inspector__eyebrow">Контрольный кадр</div>
                  <h2>{selected.label ?? selected.filename}</h2>
                </div>
                <Status status={selected.job.status} />
              </div>
              {selected.job.result ? <ProvenanceBadge source={selected.provenance} /> : <span className="provenance">Серверная обработка · результат ещё не получен</span>}
              {loadingMedia ? <div className="loading">Загрузка кадра…</div> : <FramePreview key={selected.id} upload={selected} media={media} />}
              <div className="recognition-inspector__facts">
                <span>{selected.media_type === 'video' ? 'Видео' : 'Изображение'} · {fmtBytes(selected.size_bytes)}</span>
                <span>порог {selected.job.confidence_threshold.toFixed(2)}</span>
                <span>модель {selected.job.model_name} v{selected.job.model_version}</span>
              </div>
              {selected.job.result && (
                <dl className="recognition-metrics">
                  <div><dt>Результат</dt><dd>{selected.job.result.people_count}<small>чел.</small></dd></div>
                  <div><dt>Эталон</dt><dd>{selected.reference_people_count ?? '—'}{selected.reference_people_count !== null && <small>чел.</small>}</dd></div>
                  <div><dt>Ошибка</dt><dd>{selected.job.result.absolute_error ?? '—'}{selected.job.result.absolute_error !== null && <small>чел.</small>}</dd></div>
                  <div><dt>Относительная ошибка</dt><dd>{pct(selected.job.result.relative_error)}</dd></div>
                  <div><dt>Уверенность</dt><dd>{pct(selected.job.result.average_confidence)}</dd></div>
                  <div><dt>Разброс</dt><dd>{selected.job.result.count_stddev.toFixed(2)}</dd></div>
                  <div><dt>Кадров</dt><dd>{selected.job.result.sampled_frames}<small>из {selected.job.result.source_frames}</small></dd></div>
                  <div><dt>Позиция</dt><dd>{Math.round(selected.job.result.representative_frame_ms / 1000)}<small>с</small></dd></div>
                </dl>
              )}
              {selected.job.error && <div className="capture__error">{selected.job.error}</div>}
              <p className="metric-note">Уверенность детектора не равна точности подсчёта. Подсчёт не устанавливает личность.</p>
              {!isStaticData && ['failed', 'completed', 'cancelled'].includes(selected.job.status) && <button className="btn btn--ghost" disabled={retrying} onClick={async () => {
                if (retrying) return
                setRetrying(true)
                const key = retryKeys.current.get(selected.id) ?? crypto.randomUUID()
                retryKeys.current.set(selected.id, key)
                try { const next = await managementApi.retry(selected.id, key); setUploads(items => items?.map(item => item.id === next.id ? next : item) ?? [next]); retryKeys.current.delete(selected.id) }
                catch (e) { setError((e as Error).message) }
                finally { setRetrying(false) }
              }}>{retrying ? 'Создание версии…' : 'Повторить обработку'}</button>}
              <div className="recognition-inspector__footer">
                <span>Создано {fmtClock(selected.created_at)}</span>
                {selected.media_type === 'video' && media?.source_url && <a href={media.source_url} target="_blank" rel="noopener noreferrer">Открыть видео</a>}
              </div>
              {!isStaticData && <RecognitionHistory key={selected.id} uploadId={selected.id} jobId={selected.job.id} hasResult={!!selected.job.result} />}
            </>
          ) : <div className="empty">Выберите материал</div>}
        </div>
      </section>

      {dialogOpen && (isStaticData ? (
        <Suspense fallback={<div className="loading" role="status">Подготовка локальной проверки…</div>}><LocalRecognitionDialog onClose={() => setDialogOpen(false)} /></Suspense>
      ) : (
        <UploadDialog onClose={() => setDialogOpen(false)} onCreated={(upload) => {
          setUploads((current) => current ? [upload, ...current] : [upload])
          setSelectedId(upload.id)
          void load()
        }} />
      ))}
    </>
  )
}
