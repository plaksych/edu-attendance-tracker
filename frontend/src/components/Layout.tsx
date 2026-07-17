import type { ReactNode } from 'react'
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import {
  IconCamera,
  IconCatalog,
  IconClose,
  IconDashboard,
  IconLogo,
  IconMenu,
  IconRecognition,
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
  { to: '/recognition', label: 'Распознавание', icon: <IconRecognition /> },
]

const setup: NavItem[] = [
  { to: '/schedule', label: 'Расписание', icon: <IconSchedule /> },
  { to: '/cameras', label: 'Аудитории и камеры', icon: <IconCamera /> },
  { to: '/catalog', label: 'Справочники', icon: <IconCatalog /> },
]

function Links({ items, onNavigate }: { items: NavItem[]; onNavigate?: () => void }) {
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
          onClick={onNavigate}
        >
          {icon}
          <span>{label}</span>
        </NavLink>
      ))}
    </>
  )
}

export function Layout() {
  const [menuOpen, setMenuOpen] = useState(false)

  const closeMenu = () => setMenuOpen(false)

  return (
    <div className="layout">
      <header className="mobile-header">
        <NavLink to="/" className="mobile-header__brand" onClick={closeMenu}>
          <span className="mobile-header__mark"><IconLogo /></span>
          <span>Посещаемость</span>
        </NavLink>
        <button
          type="button"
          className="icon-button mobile-header__menu"
          aria-label={menuOpen ? 'Закрыть навигацию' : 'Открыть навигацию'}
          aria-expanded={menuOpen}
          aria-controls="main-navigation"
          onClick={() => setMenuOpen((open) => !open)}
        >
          {menuOpen ? <IconClose /> : <IconMenu />}
        </button>
      </header>
      {menuOpen && (
        <button
          type="button"
          className="sidebar-backdrop"
          aria-label="Закрыть навигацию"
          onClick={closeMenu}
        />
      )}
      <nav id="main-navigation" className={`sidebar${menuOpen ? ' sidebar--open' : ''}`} aria-label="Основная навигация">
        <div className="sidebar__top">
          <div className="sidebar__brand">
            <div className="sidebar__logo">
              <IconLogo />
            </div>
            <div>
              Посещаемость
              <small>контроль занятий</small>
            </div>
          </div>
          <button type="button" className="sidebar__dismiss" aria-label="Закрыть навигацию" onClick={closeMenu}>
            <IconClose />
          </button>
        </div>
        <div className="sidebar__section">Мониторинг</div>
        <Links items={monitoring} onNavigate={closeMenu} />
        <div className="sidebar__section">Настройка</div>
        <Links items={setup} onNavigate={closeMenu} />
      </nav>
      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}
