import type { ReactNode } from 'react'

interface IconProps {
  size?: number
}

const base = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
}

function IconFrame({ size = 18, children }: IconProps & { children: ReactNode }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}>
      {children}
    </svg>
  )
}

export function IconDashboard({ size = 18 }: IconProps) {
  return (
    <IconFrame size={size}>
      <rect x="3" y="3" width="7.5" height="8" rx="1.5" />
      <rect x="13.5" y="3" width="7.5" height="5" rx="1.5" />
      <rect x="13.5" y="11" width="7.5" height="10" rx="1.5" />
      <rect x="3" y="14" width="7.5" height="7" rx="1.5" />
    </IconFrame>
  )
}

export function IconSessions({ size = 18 }: IconProps) {
  return (
    <IconFrame size={size}>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M3 10h18M8 3v4M16 3v4" />
      <path d="m9 15 2 2 4-4" />
    </IconFrame>
  )
}

export function IconSchedule({ size = 18 }: IconProps) {
  return (
    <IconFrame size={size}>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M3 10h18M8 3v4M16 3v4M7.5 14h3M13.5 14h3M7.5 17.5h3" />
    </IconFrame>
  )
}

export function IconCamera({ size = 18 }: IconProps) {
  return (
    <IconFrame size={size}>
      <rect x="2.5" y="7" width="13" height="10" rx="2" />
      <path d="m15.5 11 5-2.5v7l-5-2.5" />
      <path d="M6 11.5h3" />
    </IconFrame>
  )
}

export function IconCatalog({ size = 18 }: IconProps) {
  return (
    <IconFrame size={size}>
      <circle cx="9" cy="8.5" r="3.2" />
      <path d="M3.5 19.5c0-3 2.5-5 5.5-5s5.5 2 5.5 5" />
      <path d="M16 5.8a3.2 3.2 0 0 1 0 5.4M20.5 19.5c0-2.5-1.7-4.3-4-4.9" />
    </IconFrame>
  )
}

export function IconLogo({ size = 24 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <path d="M5 5h8v5H5zM19 5h8v9h-8zM5 19h8v8H5z" fill="currentColor" opacity="0.22" />
      <path d="M5 5h8v5H5zM19 5h8v9h-8zM5 19h8v8H5z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M19 20.5h8M19 24h5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
      <path d="m16 11.5 2.1 2.1 4.4-4.5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function IconExternal({ size = 16 }: IconProps) {
  return (
    <IconFrame size={size}>
      <path d="M14 4h6v6M20 4l-9 9M20 14v5a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 19V5.5A1.5 1.5 0 0 1 5.5 4H10" />
    </IconFrame>
  )
}

export function IconMenu({ size = 20 }: IconProps) {
  return (
    <IconFrame size={size}>
      <path d="M4 7h16M4 12h16M4 17h16" />
    </IconFrame>
  )
}

export function IconClose({ size = 20 }: IconProps) {
  return (
    <IconFrame size={size}>
      <path d="m6 6 12 12M18 6 6 18" />
    </IconFrame>
  )
}

export function IconChevronLeft({ size = 18 }: IconProps) {
  return (
    <IconFrame size={size}>
      <path d="m14.5 5-7 7 7 7" />
    </IconFrame>
  )
}

export function IconChevronRight({ size = 18 }: IconProps) {
  return (
    <IconFrame size={size}>
      <path d="m9.5 5 7 7-7 7" />
    </IconFrame>
  )
}

export function IconAttendance({ size = 20 }: IconProps) {
  return (
    <IconFrame size={size}>
      <path d="M4 19V9M10 19V5M16 19v-7M22 19V8" />
      <path d="M3 19h20" />
    </IconFrame>
  )
}

export function IconPulse({ size = 20 }: IconProps) {
  return (
    <IconFrame size={size}>
      <path d="M3 12h4l2.2-5 4 10 2.1-5H21" />
    </IconFrame>
  )
}

export function IconCalendarMark({ size = 20 }: IconProps) {
  return (
    <IconFrame size={size}>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M3 10h18M8 3v4M16 3v4M8 15h3M8 18h7" />
    </IconFrame>
  )
}
