import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getBrowserRecognizer, releaseBrowserRecognizer, type BrowserRecognitionResult } from '../lib/browserRecognition'
import { SAMPLE_DELAY_MS, validateDimensions, validateMediaContent, validateThreshold, validateVideoDuration } from '../lib/browserRecognitionCore'
import { fmtBytes } from '../lib/format'
import { Modal } from './Modal'

type Phase = 'idle' | 'validating' | 'loading-media' | 'loading-model' | 'analysing' | 'result' | 'cancelled' | 'error'
interface Props { onClose: () => void }

function median(values: number[]): number | null {
  if (!values.length) return null
  const ordered = [...values].sort((a, b) => a - b)
  const middle = Math.floor(ordered.length / 2)
  return ordered.length % 2 ? ordered[middle] : (ordered[middle - 1] + ordered[middle]) / 2
}

export function LocalRecognitionDialog({ onClose }: Props) {
  const imageRef = useRef<HTMLImageElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const generation = useRef(0)
  const inferenceInProgress = useRef(false)
  const activeUrl = useRef<string | null>(null)
  const downloadUrl = useRef<string | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [kind, setKind] = useState<'image' | 'video' | null>(null)
  const [sourceUrl, setSourceUrl] = useState<string | null>(null)
  const [mediaReady, setMediaReady] = useState(false)
  const [dimensions, setDimensions] = useState<{ width: number; height: number } | null>(null)
  const [confidence, setConfidence] = useState('0.35')
  const [phase, setPhase] = useState<Phase>('idle')
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<BrowserRecognitionResult | null>(null)
  const [counts, setCounts] = useState<number[]>([])
  const [live, setLive] = useState(false)
  const [resultTime, setResultTime] = useState<number | null>(null)
  const [videoTime, setVideoTime] = useState(0)

  useEffect(() => () => {
    generation.current += 1
    releaseBrowserRecognizer()
    if (downloadUrl.current) URL.revokeObjectURL(downloadUrl.current)
  }, [])

  useEffect(() => {
    const video = videoRef.current
    return () => {
      if (video) { video.pause(); video.removeAttribute('src'); video.load() }
      if (sourceUrl) URL.revokeObjectURL(sourceUrl)
    }
  }, [sourceUrl])

  const stop = useCallback(() => {
    generation.current += 1
    inferenceInProgress.current = false
    releaseBrowserRecognizer()
    if (downloadUrl.current) URL.revokeObjectURL(downloadUrl.current)
    downloadUrl.current = null
    setLive(false)
    videoRef.current?.pause()
  }, [])

  const failMedia = useCallback((message: string) => {
    stop()
    setMediaReady(false)
    setResult(null)
    setError(message)
    setPhase('error')
    // Unmount the media element so the browser can drop its decoder/buffers.
    activeUrl.current = null
    setSourceUrl(null)
  }, [stop])

  useEffect(() => {
    if (!sourceUrl || mediaReady) return
    const timer = window.setTimeout(() => failMedia('Файл не удалось декодировать за 20 секунд. Выберите другой файл.'), 20_000)
    return () => window.clearTimeout(timer)
  }, [failMedia, mediaReady, sourceUrl])

  const selectFile = async (nextFile: File | null) => {
    stop()
    const token = generation.current
    activeUrl.current = null
    setSourceUrl(null)
    setFile(null)
    setKind(null)
    setDimensions(null)
    setMediaReady(false)
    setError(null)
    setResult(null)
    setResultTime(null)
    setCounts([])
    setPhase(nextFile ? 'validating' : 'idle')
    if (fileInputRef.current) fileInputRef.current.value = ''
    if (!nextFile) return
    try {
      const nextKind = await validateMediaContent(nextFile)
      if (generation.current !== token) return
      const url = URL.createObjectURL(nextFile)
      activeUrl.current = url
      setFile(nextFile)
      setKind(nextKind)
      setSourceUrl(url)
      setPhase('loading-media')
    } catch (nextError) {
      if (generation.current !== token) return
      setError(nextError instanceof Error ? nextError.message : String(nextError))
      setPhase('error')
    }
  }

  const mediaLoaded = (element: HTMLImageElement | HTMLVideoElement) => {
    if (element.src !== activeUrl.current) return
    try {
      const width = element instanceof HTMLVideoElement ? element.videoWidth : element.naturalWidth
      const height = element instanceof HTMLVideoElement ? element.videoHeight : element.naturalHeight
      validateDimensions(width, height)
      if (element instanceof HTMLVideoElement) validateVideoDuration(element.duration)
      setDimensions({ width, height })
      setMediaReady(true)
      setPhase('idle')
    } catch (nextError) { failMedia(nextError instanceof Error ? nextError.message : String(nextError)) }
  }

  const analyseFrame = useCallback(async () => {
    if (inferenceInProgress.current || !mediaReady || !dimensions) return false
    const source = kind === 'image' ? imageRef.current : videoRef.current
    if (!source) return false
    const token = generation.current
    inferenceInProgress.current = true
    setError(null)
    try {
      validateThreshold(confidence.trim() ? Number(confidence) : NaN)
      if (kind === 'video' && !live) videoRef.current?.pause()
      setPhase('loading-model')
      const recognizer = await getBrowserRecognizer()
      if (generation.current !== token) return false
      setPhase('analysing')
      const frameTime = kind === 'video' ? videoRef.current?.currentTime ?? null : null
      const nextResult = await recognizer.detect(source, dimensions.width, dimensions.height, Number(confidence))
      if (generation.current !== token) return false
      setResult(nextResult)
      setResultTime(frameTime)
      setCounts((current) => [...current.slice(-59), nextResult.boxes.length])
      setPhase('result')
      return true
    } catch (nextError) {
      if (generation.current !== token) return false
      releaseBrowserRecognizer()
      setResult(null)
      setLive(false)
      setError(nextError instanceof Error ? nextError.message : String(nextError))
      setPhase('error')
      return false
    } finally {
      if (generation.current === token) inferenceInProgress.current = false
    }
  }, [confidence, dimensions, kind, live, mediaReady])

  useEffect(() => {
    if (!live || kind !== 'video') return
    let cancelled = false
    let timer: number | undefined
    const run = async () => {
      if (cancelled) return
      const video = videoRef.current
      if (!video || video.paused || video.ended) { setLive(false); return }
      const succeeded = await analyseFrame()
      if (!cancelled && succeeded) timer = window.setTimeout(() => void run(), SAMPLE_DELAY_MS)
      else if (!cancelled) setLive(false)
    }
    void run()
    return () => { cancelled = true; if (timer !== undefined) window.clearTimeout(timer) }
  }, [analyseFrame, kind, live])

  const startLive = async () => {
    const token = generation.current
    try {
      validateThreshold(confidence.trim() ? Number(confidence) : NaN)
      await videoRef.current?.play()
      if (generation.current === token) setLive(true)
    } catch (nextError) {
      if (generation.current !== token) return
      setError(nextError instanceof Error ? nextError.message : 'Браузер не разрешил воспроизведение видео')
      setPhase('error')
    }
  }

  const countMedian = useMemo(() => median(counts), [counts])
  const countMax = counts.length ? Math.max(...counts) : null
  const isBusy = phase === 'loading-model' || phase === 'analysing'
  const status = { idle: mediaReady ? 'Готово к обработке' : 'Файл не выбран', validating: 'Проверка файла', 'loading-media': 'Подготовка медиа', 'loading-model': 'Подготовка модели', analysing: 'Обработка кадра', result: 'Обработано в браузере', cancelled: 'Обработка остановлена', error: 'Обработка не выполнена' }[phase]
  const showBoxes = kind === 'image' || (!live && resultTime !== null && Math.abs(videoTime - resultTime) < 0.05)

  const exportResult = () => {
    if (!result) return
    if (downloadUrl.current) URL.revokeObjectURL(downloadUrl.current)
    const report = {
      ...result, count: result.boxes.length, frameTimeSeconds: resultTime,
      recentFrameCounts: counts, samplingDelayAfterInferenceMs: SAMPLE_DELAY_MS,
      quality: { confidenceIsAccuracy: false, classroomAccuracy: 'not_evaluated' },
    }
    downloadUrl.current = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }))
    const link = document.createElement('a')
    link.href = downloadUrl.current
    link.download = 'browser-inference.json'
    link.click()
  }

  return (
    <Modal title="Локальный анализ" onClose={() => { stop(); onClose() }} wide>
      <div className="local-recognition">
        <div className="field" onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); void selectFile(event.dataTransfer.files[0] ?? null) }}>
          <label htmlFor="local-recognition-file">Фото или видео</label>
          <input ref={fileInputRef} id="local-recognition-file" className="input file-input" type="file" accept="video/mp4,video/quicktime,video/webm,image/jpeg,image/png,image/webp" onChange={(event) => void selectFile(event.target.files?.[0] ?? null)} />
          <span className="field__hint">JPEG, PNG, WebP: до 20 МиБ. MP4, MOV, WebM: до 200 МиБ и 10 минут. До 16 Мп, до 8192 пикселей по стороне. Кодек должен поддерживаться браузером.</span>
          {file && <span className="field__hint" style={{ overflowWrap: 'anywhere' }}>{file.name} · {fmtBytes(file.size)}</span>}
        </div>
        <div role="status" aria-live="polite">{status}</div>
        <div className="local-recognition__toolbar">
          <details>
            <summary>Параметры обработки</summary>
            <div className="field local-recognition__threshold">
              <label htmlFor="local-recognition-threshold">Порог уверенности</label>
              <input id="local-recognition-threshold" className="input" type="number" min="0.1" max="0.9" step="0.05" value={confidence} disabled={isBusy || live} onChange={(event) => { setConfidence(event.target.value); setResult(null); setCounts([]) }} />
            </div>
          </details>
          <div className="local-recognition__actions">
            {kind === 'video' && <button className="btn btn--ghost" type="button" onClick={() => void startLive()} disabled={!mediaReady || isBusy || live}>Анализ видео</button>}
            <button className="btn" type="button" onClick={() => void analyseFrame()} disabled={!mediaReady || isBusy || live}>{phase === 'error' ? 'Повторить' : kind === 'video' ? 'Проверить кадр' : 'Распознать'}</button>
            {(isBusy || live || phase === 'validating') && <button className="btn btn--ghost" type="button" onClick={() => { stop(); setPhase('cancelled') }}>Остановить</button>}
            {(file || result || error) && <button className="btn btn--ghost" type="button" onClick={() => void selectFile(null)}>Очистить</button>}
          </div>
        </div>
        {sourceUrl && kind && (
          <div className="local-recognition__frame" style={{ maxWidth: dimensions ? `min(100%, calc(58vh * ${dimensions.width / dimensions.height}))` : '100%', marginInline: 'auto' }}>
            {kind === 'image' ? (
              <img key={sourceUrl} ref={imageRef} src={sourceUrl} alt="Выбранное изображение" style={{ maxHeight: 'none' }} onLoad={(event) => mediaLoaded(event.currentTarget)} onError={() => failMedia('Изображение повреждено или не поддерживается браузером')} />
            ) : (
              <video key={sourceUrl} ref={videoRef} src={sourceUrl} controls preload="auto" style={{ maxHeight: 'none' }} onLoadedData={(event) => mediaLoaded(event.currentTarget)} onError={() => failMedia('Видео повреждено или кодек не поддерживается браузером')} onTimeUpdate={(event) => setVideoTime(event.currentTarget.currentTime)} onSeeking={() => { stop(); setResult(null); setPhase('idle') }} onPause={() => setLive(false)} onEnded={() => { stop(); setPhase('idle') }} />
            )}
            {showBoxes && result?.boxes.map((box, index) => (
              <span className="local-recognition__box" key={index} style={{ left: `${box.x / result.sourceWidth * 100}%`, top: `${box.y / result.sourceHeight * 100}%`, width: `${box.width / result.sourceWidth * 100}%`, height: `${box.height / result.sourceHeight * 100}%` }}><i>{index + 1}</i></span>
            ))}
          </div>
        )}
        {result && (
          <>
            <dl className="local-recognition__metrics">
              <div><dt>Найдено в кадре</dt><dd>{result.boxes.length}<small>чел.</small></dd></div>
              {resultTime !== null && <div><dt>Время кадра</dt><dd>{resultTime.toFixed(1)}<small>с</small></dd></div>}
              <div><dt>Источник</dt><dd style={{ fontSize: '1rem' }}>Обработано в браузере</dd></div>
            </dl>
            <button className="btn btn--ghost" type="button" onClick={exportResult}>Скачать локальный результат JSON</button>
            <details>
              <summary>Сведения о результате</summary>
              <p>YOLOv8n · COCO · {result.runtime}</p>
              <p>Средняя уверенность детектора: {result.averageConfidence === null ? 'нет детекций' : `${Math.round(result.averageConfidence * 100)}%`}. Это не точность подсчёта. Качество на аудиториях не подтверждено размеченным набором.</p>
              <p>Последние {counts.length} кадров (до 60): медиана {countMedian ?? '—'}, максимум {countMax ?? '—'}. Это не число уникальных людей. Интервал выборки: время обработки + 0.9 с.</p>
              <p>Порог {result.confidenceThreshold}; NMS IoU {result.nmsIouThreshold}. Обработка кадра: {(result.elapsedMs / 1000).toFixed(2)} с.</p>
              <p style={{ overflowWrap: 'anywhere' }}>SHA-256: {result.modelSha256}</p>
              <p>Источник и лицензия весов требуют проверки перед публичным выпуском.</p>
            </details>
          </>
        )}
        {error && <div className="alert alert--error" role="alert">{error}</div>}
        <div className="local-recognition__privacy">Медиа обрабатывается на устройстве и не отправляется на сервер. Модель загружается при запуске анализа. Материалы и результаты не сохраняются после закрытия.</div>
      </div>
    </Modal>
  )
}
