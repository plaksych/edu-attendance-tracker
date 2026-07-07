import type { SessionStatus } from '../api/types'

const labels: Record<SessionStatus, string> = {
  scheduled: 'Запланировано',
  in_progress: 'Идёт',
  finished: 'Завершено',
}

export function StatusBadge({ status }: { status: SessionStatus }) {
  return <span className={`badge badge--${status}`}>{labels[status]}</span>
}
