import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { api, isStaticData } from '../api/client'
import type {
  RecognitionEvaluationSummary,
  RecognitionStatus,
  RecognitionUpload,
  RecognitionUploadMedia,
} from '../api/types'
import { IconImage, IconRecognition, IconRefresh, IconUpload, IconVideo } from '../components/icons'
import { LocalRecognitionDialog } from '../components/LocalRecognitionDialog'
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

type Box = { left: number; top: number; width: number; height: number }

const DEMO_BOXES: Record<number, Box[]> = {
  104: [
    { left: 6, top: 36, width: 13, height: 33 },
    { left: 15, top: 28, width: 10, height: 22 },
    { left: 38, top: 29, width: 8, height: 22 },
    { left: 45, top: 33, width: 10, height: 30 },
    { left: 39, top: 44, width: 14, height: 45 },
    { left: 63, top: 27, width: 9, height: 24 },
    { left: 77, top: 34, width: 9, height: 24 },
    { left: 88, top: 39, width: 11, height: 43 },
  ],
  103: [
    { left: 9, top: 43, width: 9, height: 31 },
    { left: 19, top: 45, width: 10, height: 39 },
    { left: 28, top: 40, width: 10, height: 30 },
    { left: 36, top: 39, width: 8, height: 27 },
    { left: 48, top: 40, width: 8, height: 25 },
    { left: 48, top: 48, width: 10, height: 36 },
    { left: 63, top: 40, width: 9, height: 28 },
    { left: 72, top: 41, width: 10, height: 31 },
    { left: 80, top: 41, width: 9, height: 28 },
    { left: 87, top: 43, width: 9, height: 31 },
    { left: 72, top: 52, width: 13, height: 42 },
  ],
  102: [
    { left: 8, top: 34, width: 15, height: 33 },
    { left: 22, top: 42, width: 18, height: 50 },
    { left: 39, top: 20, width: 10, height: 24 },
    { left: 52, top: 24, width: 12, height: 36 },
    { left: 73, top: 22, width: 10, height: 30 },
    { left: 81, top: 39, width: 15, height: 40 },
  ],
}

function Status({ status }: { status: RecognitionStatus }) {
  return <span className={`pill pill--${STATUS_TONE[status]}`}>{STATUS_LABEL[status]}</span>
}

function pct(value: number | null): string {
  return value === null ? '—' : `${Math.round(value * 100)}%`
}

function FramePreview({ upload, media }: { upload: RecognitionUpload; media: RecognitionUploadMedia | null }) {
  const result = upload.job.result
  const source = media?.annotated_url
  if (!source || !result) {
    return <div className="recognition-frame__empty">Контрольный кадр появится после обработки</div>
  }
  const boxes = isStaticData ? DEMO_BOXES[upload.id] ?? [] : []
  return (
    <div className="recognition-frame">
      <img src={source} alt={`Контрольный кадр: ${upload.label ?? upload.filename}`} />
      {boxes.map((box, index) => (
        <span
          className="recognition-frame__box"
          key={`${upload.id}-${index}`}
          style={{ left: `${box.left}%`, top: `${box.top}%`, width: `${box.width}%`, height: `${box.height}%` }}
        >
          <i>{index + 1}</i>
        </span>
      ))}
    </div>
  )
}

function UploadDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (upload: RecognitionUpload) => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [label, setLabel] = useState('')
  const [reference, setReference] = useState('')
  const [sampleRate, setSampleRate] = useState('1')
  const [confidence, setConfidence] = useState('0.35')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!file) {
      setError('Выберите видео или изображение')
      return
    }
    const referencePeopleCount = reference === '' ? undefined : Number(reference)
    if (referencePeopleCount !== undefined && (!Number.isInteger(referencePeopleCount) || referencePeopleCount < 0)) {
      setError('Эталонное число должно быть целым неотрицательным числом')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const upload = await api.uploadRecognition({
        file,
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
    }
  }

  return (
    <Modal title="Новый материал" onClose={onClose}>
      <form className="modal__form" onSubmit={submit}>
        <div className="field">
          <label htmlFor="recognition-file">Видео или изображение</label>
          <input
            id="recognition-file"
            className="input file-input"
            type="file"
            accept="video/mp4,video/quicktime,video/x-msvideo,video/webm,image/jpeg,image/png,image/webp"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
          {file && <span className="field__hint">{file.name} · {fmtBytes(file.size)}</span>}
        </div>
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
            <input id="recognition-rate" className="input" type="number" min="0.1" max="10" step="0.1" value={sampleRate} onChange={(event) => setSampleRate(event.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="recognition-confidence">Порог</label>
            <input id="recognition-confidence" className="input" type="number" min="0.05" max="0.95" step="0.05" value={confidence} onChange={(event) => setConfidence(event.target.value)} />
          </div>
        </div>
        {error && <div className="alert alert--error">{error}</div>}
        <div className="modal__actions">
          <button type="button" className="btn btn--ghost" onClick={onClose}>Отмена</button>
          <button className="btn" disabled={saving}>{saving ? 'Создание…' : 'Отправить'}</button>
        </div>
      </form>
    </Modal>
  )
}

export function RecognitionPage() {
  const [uploads, setUploads] = useState<RecognitionUpload[] | null>(null)
  const [summary, setSummary] = useState<RecognitionEvaluationSummary | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [media, setMedia] = useState<RecognitionUploadMedia | null>(null)
  const [loadingMedia, setLoadingMedia] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)

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
    api.getRecognitionUploadMedia(selected.id)
      .then(setMedia)
      .catch(() => setMedia(null))
      .finally(() => setLoadingMedia(false))
  }, [selected?.id])

  useEffect(() => {
    if (!uploads?.some((item) => ACTIVE_STATUSES.has(item.job.status))) return
    const timer = window.setInterval(() => void load(), 8000)
    return () => window.clearInterval(timer)
  }, [uploads, load])

  const completed = useMemo(
    () => uploads?.filter((item) => item.job.status === 'completed') ?? [],
    [uploads],
  )
  const meanConfidence = completed.length
    ? completed.reduce((sum, item) => sum + (item.job.result?.average_confidence ?? 0), 0) / completed.length
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
          <button className="btn" type="button" onClick={() => setDialogOpen(true)}>
            <IconUpload />
            {isStaticData ? 'Проверить файл' : 'Добавить материал'}
          </button>
        </div>
      </header>

      {isStaticData && <div className="recognition-mode">Публикация: локальная проверка фото и видео, демонстрационный журнал и контрольные кадры.</div>}
      {error && <div className="alert alert--error">{error}</div>}

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
              {loadingMedia ? <div className="loading">Загрузка кадра…</div> : <FramePreview upload={selected} media={media} />}
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
                  <div><dt>Точность</dt><dd>{selected.job.result.relative_error === null ? '—' : `${Math.round((1 - selected.job.result.relative_error) * 100)}%`}</dd></div>
                  <div><dt>Уверенность</dt><dd>{pct(selected.job.result.average_confidence)}</dd></div>
                  <div><dt>Разброс</dt><dd>{selected.job.result.count_stddev.toFixed(2)}</dd></div>
                  <div><dt>Кадров</dt><dd>{selected.job.result.sampled_frames}<small>из {selected.job.result.source_frames}</small></dd></div>
                  <div><dt>Позиция</dt><dd>{Math.round(selected.job.result.representative_frame_ms / 1000)}<small>с</small></dd></div>
                </dl>
              )}
              {selected.job.error && <div className="capture__error">{selected.job.error}</div>}
              <div className="recognition-inspector__footer">
                <span>Создано {fmtClock(selected.created_at)}</span>
                {selected.media_type === 'video' && media?.source_url && <a href={media.source_url} target="_blank" rel="noopener noreferrer">Открыть видео</a>}
              </div>
            </>
          ) : <div className="empty">Выберите материал</div>}
        </div>
      </section>

      {dialogOpen && (isStaticData ? (
        <LocalRecognitionDialog onClose={() => setDialogOpen(false)} />
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
