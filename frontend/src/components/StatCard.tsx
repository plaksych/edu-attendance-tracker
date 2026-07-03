interface Props {
  label: string
  value: string | number
  hint?: string
}

export function StatCard({ label, value, hint }: Props) {
  return (
    <div className="card">
      <div className="stat-card__label">{label}</div>
      <div className="stat-card__value">{value}</div>
      {hint && <div className="stat-card__hint">{hint}</div>}
    </div>
  )
}
