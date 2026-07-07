interface IconProps {
  size?: number
}

const base = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.7,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
}

export function IconDashboard({ size = 16 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}>
      <rect x="3" y="3" width="7.5" height="9" rx="1.5" />
      <rect x="13.5" y="3" width="7.5" height="5.5" rx="1.5" />
      <rect x="13.5" y="12" width="7.5" height="9" rx="1.5" />
      <rect x="3" y="15.5" width="7.5" height="5.5" rx="1.5" />
    </svg>
  )
}

export function IconSessions({ size = 16 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M3 10h18M8 3v4M16 3v4" />
      <path d="m9.5 15.5 2 2 3.5-3.5" />
    </svg>
  )
}

export function IconSchedule({ size = 16 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M3 10h18M8 3v4M16 3v4M7.5 14h3M13.5 14h3M7.5 17.5h3" />
    </svg>
  )
}

export function IconCamera({ size = 16 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}>
      <rect x="2.5" y="7" width="13" height="10" rx="2" />
      <path d="m15.5 11 5-2.5v7l-5-2.5" />
    </svg>
  )
}

export function IconCatalog({ size = 16 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}>
      <circle cx="9" cy="8.5" r="3.2" />
      <path d="M3.5 19.5c0-3 2.5-5 5.5-5s5.5 2 5.5 5" />
      <path d="M16 5.8a3.2 3.2 0 0 1 0 5.4M20.5 19.5c0-2.5-1.7-4.3-4-4.9" />
    </svg>
  )
}

export function IconLogo({ size = 16 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base} strokeWidth={2}>
      <path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2" />
      <circle cx="12" cy="10" r="2.4" />
      <path d="M7.5 17c.7-2 2.4-3.2 4.5-3.2s3.8 1.2 4.5 3.2" />
    </svg>
  )
}

export function IconExternal({ size = 14 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}>
      <path d="M14 4h6v6M20 4l-9 9M20 14v5a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 19V5.5A1.5 1.5 0 0 1 5.5 4H10" />
    </svg>
  )
}
