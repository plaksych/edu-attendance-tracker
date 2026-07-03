interface Props {
  rate: number | null
}

export function formatRate(rate: number | null): string {
  if (rate === null) return '—'
  return `${Math.round(rate * 100)}%`
}

export function RateBadge({ rate }: Props) {
  if (rate === null) return <span className="rate">—</span>
  const level = rate >= 0.8 ? 'high' : rate >= 0.6 ? 'mid' : 'low'
  return <span className={`rate rate--${level}`}>{formatRate(rate)}</span>
}
