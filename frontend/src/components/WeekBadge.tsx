import type { WeekType } from '../api/types'

const labels: Record<WeekType, string> = {
  every: 'каждая',
  white: 'белая',
  green: 'зелёная',
}

export function weekLabel(week: WeekType): string {
  return labels[week]
}

export function WeekBadge({ week }: { week: WeekType }) {
  if (week === 'every') return null
  return <span className={`badge badge--week-${week}`}>{labels[week]}</span>
}
