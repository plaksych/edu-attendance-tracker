import type { ReactNode } from 'react'

interface Props {
  label: string
  value: string | number
  hint?: string
  icon?: ReactNode
  tone?: 'teal' | 'blue' | 'green' | 'amber'
}

export function StatCard({ label, value, hint, icon, tone = 'blue' }: Props) {
  return (
    <div className={`card stat-card stat-card--${tone}`}>
      <div className="stat-card__head">
        <div className="stat-card__label">{label}</div>
        {icon && <span className="stat-card__icon">{icon}</span>}
      </div>
      <div className="stat-card__value">{value}</div>
      {hint && <div className="stat-card__hint">{hint}</div>}
    </div>
  )
}
