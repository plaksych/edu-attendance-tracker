import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  getBrowserRecognizer,
  type BrowserRecognitionModel,
  type BrowserRecognitionResult,
} from '../lib/browserRecognition'
import { fmtBytes } from '../lib/format'
import { Modal } from './Modal'

type MediaKind = 'image' | 'video' | null
type Phase = 'idle' | 'loading-model' | 'analysing' | 'error'

const DEFAULT_CONFIDENCE: Record<BrowserRecognitionModel, string> = {
  coco: '0.35',
  classroom: '0.20',
}

interface Props {
  onClose: () => void
}

function percent(value: number | null): string {
  return value === null ? '—' : `${Math.round(value * 100)}%`
}

function median(values: number[]): number | null {
  if (!values.length) return null
  const ordered = [...values].sort((first, second) => first - second)
  const middle = Math.floor(ordered.length / 2)
  return ordered.length % 2 ? ordered[middle] : Math.round((ordered[middle - 1] + ordered[middle]) / 2)
}

export function LocalRecognitionDialog({ onClose }: Props) {
  const imageRef = useRef<HTMLImageElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const inferenceInProgress = useRef(false)
  const activeAnalysis = useRef<AbortController | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [kind, setKind] = useState<MediaKind>(null)
  const [sourceUrl, setSourceUrl] = useState<string | null>(null)
  const [mediaReady, setMediaReady] = useState(false)
  const [confidence, setConfidence] = useState(DEFAULT_CONFIDENCE.coco)
  const [model, setModel] = useState<BrowserRecognitionModel>('coco')
  const [phase, setPhase] = useState<Phase>('idle')
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<BrowserRecognitionResult | null>(null)
  const [counts, setCounts] = useState<number[]>([])
  const [live, setLive] = useState(false)

  useEffect(() => () => {
    if (sourceUrl) URL.revokeObjectURL(sourceUrl)
  }, [sourceUrl])

  useEffect(() => () => activeAnalysis.current?.abort(), [])

  const selectFile = (nextFile: File | null) => {
    activeAnalysis.current?.abort()
    activeAnalysis.current = null
    inferenceInProgress.current = false
    if (sourceUrl) URL.revokeObjectURL(sourceUrl)
    setFile(nextFile)
    setSourceUrl(nextFile ? URL.createObjectURL(nextFile) : null)
    setKind(nextFile?.type.startsWith('video/') ? 'video' : nextFile ? 'image' : null)
    setMediaReady(false)
    setPhase('idle')
    setError(null)
    setResult(null)
    setCounts([])
    setLive(false)
  }

  const analyseFrame = useCallback(async () => {
    if (inferenceInProgress.current) return false
    const source = kind === 'image' ? imageRef.current : videoRef.current
    const sourceWidth = kind === 'image' ? imageRef.current?.naturalWidth : videoRef.current?.videoWidth
    const sourceHeight = kind === 'image' ? imageRef.current?.naturalHeight : videoRef.current?.videoHeight
    if (!source || !sourceWidth || !sourceHeight) {
      setError('Дождитесь загрузки файла')
      setPhase('error')
      return false
    }

    inferenceInProgress.current = true
    const controller = new AbortController()
    activeAnalysis.current = controller
    setError(null)
    try {
      setPhase('loading-model')
      const recognizer = await getBrowserRecognizer(model)
      controller.signal.throwIfAborted()
      setPhase('analysing')
      const nextResult = await recognizer.detect(source, sourceWidth, sourceHeight, Number(confidence), {
        // The classroom confidence preset was calibrated on full-frame inference.
        detailed: kind === 'image' && model === 'coco',
        signal: controller.signal,
      })
      if (controller.signal.aborted) return false
      setResult(nextResult)
      setCounts((current) => [...current.slice(-59), nextResult.boxes.length])
      setPhase('idle')
      return true
    } catch (nextError) {
      if (controller.signal.aborted) return false
      setError((nextError as Error).message)
      setPhase('error')
      return false
    } finally {
      if (activeAnalysis.current === controller) {
        activeAnalysis.current = null
        inferenceInProgress.current = false
      }
    }
  }, [confidence, kind, model])

  useEffect(() => {
    if (!live || kind !== 'video') return
    let cancelled = false
    let timer: number | undefined
    const run = async () => {
      if (cancelled) return
      const video = videoRef.current
      if (!video || video.paused || video.ended) {
        setLive(false)
        return
      }
      await analyseFrame()
      if (!cancelled) timer = window.setTimeout(() => void run(), 900)
    }
    void run()
    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [analyseFrame, kind, live])

  const startLive = async () => {
    const video = videoRef.current
    if (!video) return
    try {
      await video.play()
      setLive(true)
    } catch {
      setError('Браузер не разрешил воспроизведение видео')
      setPhase('error')
    }
  }

  const countMedian = useMemo(() => median(counts), [counts])
  const countMax = useMemo(() => counts.length ? Math.max(...counts) : null, [counts])
  const isBusy = phase === 'loading-model' || phase === 'analysing'
  const actionLabel = phase === 'loading-model'
    ? 'Загрузка модели…'
    : phase === 'analysing'
      ? 'Анализ…'
      : kind === 'video'
        ? 'Проверить кадр'
        : 'Распознать'

  return (
    <Modal title="Проверка файла" onClose={onClose} wide>
      <div className="local-recognition">
        <div className="field">
          <label htmlFor="local-recognition-file">Фото или видео</label>
          <input
            id="local-recognition-file"
            className="input file-input"
            type="file"
            accept="video/mp4,video/quicktime,video/x-msvideo,video/webm,image/jpeg,image/png,image/webp"
            onChange={(event) => selectFile(event.target.files?.[0] ?? null)}
          />
          {file && <span className="field__hint">{file.name} · {fmtBytes(file.size)}</span>}
        </div>

        {sourceUrl && kind && (
          <>
            <div className="local-recognition__toolbar">
              <div className="field">
                <label htmlFor="local-recognition-model">Модель</label>
                <select
                  id="local-recognition-model"
                  className="input"
                  value={model}
                  disabled={isBusy || live}
                  onChange={(event) => {
                    const nextModel = event.target.value === 'classroom' ? 'classroom' : 'coco'
                    setModel(nextModel)
                    setConfidence(DEFAULT_CONFIDENCE[nextModel])
                    setResult(null)
                    setCounts([])
                    setPhase('idle')
                    setError(null)
                  }}
                >
                  <option value="coco">YOLOv8n · COCO</option>
                  <option value="classroom">YOLOv8n · аудитории</option>
                </select>
              </div>
              <div className="field local-recognition__threshold">
                <label htmlFor="local-recognition-threshold">Порог</label>
                <input
                  id="local-recognition-threshold"
                  className="input"
                  type="number"
                  min="0.1"
                  max="0.9"
                  step="0.05"
                  value={confidence}
                  onChange={(event) => setConfidence(event.target.value)}
                  disabled={isBusy}
                />
              </div>
              <div className="local-recognition__actions">
                {kind === 'video' && (
                  <button className="btn btn--ghost" type="button" onClick={() => live ? setLive(false) : void startLive()} disabled={!mediaReady || isBusy}>
                    {live ? 'Остановить' : 'В реальном времени'}
                  </button>
                )}
                <button className="btn" type="button" onClick={() => void analyseFrame()} disabled={!mediaReady || isBusy}>
                  {actionLabel}
                </button>
              </div>
            </div>

            <div className="local-recognition__frame">
              {kind === 'image' ? (
                <img ref={imageRef} src={sourceUrl} alt="Выбранное изображение" onLoad={() => setMediaReady(true)} />
              ) : (
                <video ref={videoRef} src={sourceUrl} controls preload="metadata" onLoadedMetadata={() => setMediaReady(true)} onPause={() => setLive(false)} />
              )}
              {result?.boxes.map((box, index) => (
                <span
                  className="local-recognition__box"
                  key={`${index}-${box.x}-${box.y}`}
                  style={{
                    left: `${(box.x / (kind === 'image' ? imageRef.current?.naturalWidth ?? 1 : videoRef.current?.videoWidth ?? 1)) * 100}%`,
                    top: `${(box.y / (kind === 'image' ? imageRef.current?.naturalHeight ?? 1 : videoRef.current?.videoHeight ?? 1)) * 100}%`,
                    width: `${(box.width / (kind === 'image' ? imageRef.current?.naturalWidth ?? 1 : videoRef.current?.videoWidth ?? 1)) * 100}%`,
                    height: `${(box.height / (kind === 'image' ? imageRef.current?.naturalHeight ?? 1 : videoRef.current?.videoHeight ?? 1)) * 100}%`,
                  }}
                >
                  <i>{index + 1}</i>
                </span>
              ))}
            </div>

            {result && (
              <dl className="local-recognition__metrics">
                <div><dt>Найдено</dt><dd>{result.boxes.length}<small>чел.</small></dd></div>
                <div><dt>Уверенность</dt><dd>{percent(result.averageConfidence)}</dd></div>
                <div><dt>Кадров</dt><dd>{counts.length}</dd></div>
                <div><dt>Медиана</dt><dd>{countMedian ?? '—'}<small>{countMedian === null ? '' : ' чел.'}</small></dd></div>
                <div><dt>Максимум</dt><dd>{countMax ?? '—'}<small>{countMax === null ? '' : ' чел.'}</small></dd></div>
                <div><dt>Время</dt><dd>{(result.elapsedMs / 1000).toFixed(2)}<small>с</small></dd></div>
              </dl>
            )}
          </>
        )}
        {error && <div className="alert alert--error">{error}</div>}
        <div className="local-recognition__privacy">Файл обрабатывается локально и не отправляется на сервер.</div>
      </div>
    </Modal>
  )
}
