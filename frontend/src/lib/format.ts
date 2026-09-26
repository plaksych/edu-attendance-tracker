export function isoDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

export function today(): string {
  if (import.meta.env.VITE_STATIC_DATA === 'true') return DEMO_DATE
  return new Intl.DateTimeFormat('en-CA', { timeZone: TIME_ZONE, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
}

export function shiftDate(iso: string, days: number): string {
  const date = new Date(`${iso}T12:00:00`)
  date.setDate(date.getDate() + days)
  return isoDate(date)
}

export function fmtTime(time: string): string {
  return time.slice(0, 5)
}

export function fmtDateHuman(iso: string): string {
  return new Date(`${iso}T12:00:00`).toLocaleDateString('ru-RU', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })
}

export function fmtDateShort(iso: string): string {
  return new Date(`${iso}T12:00:00`).toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
  })
}

export function fmtClock(isoDateTime: string): string {
  return new Date(isoDateTime).toLocaleTimeString('ru-RU', {
    timeZone: TIME_ZONE,
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function fmtBytes(bytes: number | null): string {
  if (bytes === null) return '—'
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} КБ`
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`
}
export const DEMO_DATE = '2026-09-23'
export const TIME_ZONE = import.meta.env.VITE_TIME_ZONE || 'Europe/Moscow'
