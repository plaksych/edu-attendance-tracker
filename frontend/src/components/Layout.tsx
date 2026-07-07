import type { ReactNode } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import {
  IconCamera,
  IconCatalog,
  IconDashboard,
  IconLogo,
  IconSchedule,
  IconSessions,
} from './icons'

interface NavItem {
  to: string
  label: string
  icon: ReactNode
}

const monitoring: NavItem[] = [
  { to: '/', label: 'Дашборд', icon: <IconDashboard /> },
  { to: '/sessions', label: 'Занятия', icon: <IconSessions /> },
]

const setup: NavItem[] = [
  { to: '/schedule', label: 'Расписание', icon: <IconSchedule /> },
  { to: '/cameras', label: 'Аудитории и камеры', icon: <IconCamera /> },
  { to: '/catalog', label: 'Справочники', icon: <IconCatalog /> },
]

function Links({ items }: { items: NavItem[] }) {
  return (
    <>
      {items.map(({ to, label, icon }) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/'}
          className={({ isActive }) =>
            isActive ? 'sidebar__link sidebar__link--active' : 'sidebar__link'
          }
        >
          {icon}
          <span>{label}</span>
        </NavLink>
      ))}
    </>
  )
}

export function Layout() {
  return (
    <div className="layout">
      <nav className="sidebar">
        <div className="sidebar__brand">
          <div className="sidebar__logo">
            <IconLogo />
          </div>
          <div>
            Посещаемость
            <small>контроль занятий</small>
          </div>
        </div>
        <div className="sidebar__section">Мониторинг</div>
        <Links items={monitoring} />
        <div className="sidebar__section">Настройка</div>
        <Links items={setup} />
      </nav>
      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}
