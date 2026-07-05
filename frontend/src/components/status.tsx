import type {
  CalculationStatus,
  CaptureStatus,
  MeasurementStatus,
  SessionStatus,
} from '../api/types'

type Tone = 'gray' | 'blue' | 'green' | 'amber' | 'red'

interface StatusInfo {
  label: string
  tone: Tone
  pulse?: boolean
}

export const SESSION_STATUS: Record<SessionStatus, StatusInfo> = {
  scheduled: { label: 'Запланировано', tone: 'gray' },
  in_progress: { label: 'Идёт', tone: 'blue', pulse: true },
  finished: { label: 'Завершено', tone: 'green' },
  cancelled: { label: 'Отменено', tone: 'gray' },
}

export const MEASUREMENT_STATUS: Record<MeasurementStatus, StatusInfo> = {
  scheduled: { label: 'Ожидает', tone: 'gray' },
  capturing: { label: 'Запись', tone: 'blue', pulse: true },
  recognizing: { label: 'Распознавание', tone: 'blue', pulse: true },
  completed: { label: 'Выполнен', tone: 'green' },
  partially_completed: { label: 'Частично', tone: 'amber' },
  failed: { label: 'Ошибка', tone: 'red' },
  cancelled: { label: 'Отменён', tone: 'gray' },
}

export const CAPTURE_STATUS: Record<CaptureStatus, StatusInfo> = {
  pending: { label: 'В очереди', tone: 'gray' },
  claimed: { label: 'Назначено', tone: 'blue' },
  recording: { label: 'Запись', tone: 'blue', pulse: true },
  uploading: { label: 'Загрузка', tone: 'blue', pulse: true },
  completed: { label: 'Записано', tone: 'green' },
  retry_wait: { label: 'Повтор', tone: 'amber' },
  failed: { label: 'Ошибка', tone: 'red' },
  cancelled: { label: 'Отменено', tone: 'gray' },
}

export const CALCULATION_STATUS: Record<CalculationStatus, StatusInfo> = {
  complete: { label: 'Оба замера', tone: 'green' },
  partial: { label: 'Один замер', tone: 'amber' },
  failed: { label: 'Нет замеров', tone: 'red' },
}

export function Pill({ info }: { info: StatusInfo }) {
  const pulse = info.pulse ? ' pill--pulse' : ''
  return <span className={`pill pill--${info.tone}${pulse}`}>{info.label}</span>
}

export function Dot({ info }: { info: StatusInfo }) {
  const pulse = info.pulse ? ' dot--pulse' : ''
  return <span className={`measure-chip__dot dot--${info.tone}${pulse}`} />
}
