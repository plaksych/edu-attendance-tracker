interface Props {
  rate: number | null
  detail?: string
}

export function formatRate(rate: number | null): string {
  if (rate === null) return '—'
  return `${Math.round(rate * 100)}%`
}

export function rateLevel(rate: number): 'high' | 'mid' | 'low' {
  return rate >= 0.8 ? 'high' : rate >= 0.6 ? 'mid' : 'low'
}

export function RateCell({ rate, detail }: Props) {
  if (rate === null) {
    return <span style={{ color: 'var(--text-faint)' }}>—</span>
  }
  const level = rateLevel(rate)
  return (
    <div className={`rate rate--${level}`}>
      <div className="rate__row">
        <span className="rate__value">{formatRate(rate)}</span>
        {detail && <span className="rate__detail">{detail}</span>}
      </div>
      <div className="rate__bar">
        <span style={{ width: `${Math.round(rate * 100)}%` }} />
      </div>
    </div>
  )
}
