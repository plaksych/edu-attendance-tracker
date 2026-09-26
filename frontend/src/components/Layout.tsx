import type { ReactNode } from 'react'
import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { isStaticData } from '../api/client'
import { useSession } from '../auth/SessionProvider'
import { homeForRole, mayVisit, roleLabels, type Role } from '../auth/permissions'
import { DEMO_DATE, TIME_ZONE } from '../lib/format'
import { PresentationControls } from './PresentationControls'
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
  { to: '/', label: 'Обзор', icon: <IconDashboard /> },
  { to: '/sessions', label: 'Занятия', icon: <IconSessions /> },
  { to: '/recognition', label: 'Распознавание', icon: <IconRecognition /> },
  { to: '/analytics', label: 'Аналитика', icon: <IconDashboard /> },
]

const setup: NavItem[] = [
  { to: '/schedule', label: 'Расписание', icon: <IconSchedule /> },
  { to: '/cameras', label: 'Аудитории и камеры', icon: <IconCamera /> },
  { to: '/catalog', label: 'Справочники', icon: <IconCatalog /> },
  { to: '/admin/users', label: 'Доступ', icon: <IconCatalog /> },
  { to: '/admin/audit', label: 'Журнал действий', icon: <IconSessions /> },
  { to: '/admin/system', label: 'Состояние системы', icon: <IconDashboard /> },
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
  const [logoutError, setLogoutError] = useState<string | null>(null)
  const [loggingOut, setLoggingOut] = useState(false)
  const [presenting, setPresenting] = useState(false)
  const { user, logout, setDemoRole } = useSession()
  const location = useLocation()
  const navigate = useNavigate()
  const menuButton = useRef<HTMLButtonElement>(null)
  const navigation = useRef<HTMLElement>(null)
  const content = useRef<HTMLElement>(null)

  useEffect(() => {
    content.current?.focus()
    document.title = `${[...monitoring, ...setup].find(item => item.to === location.pathname)?.label ?? 'Занятие'} · Посещаемость`
  }, [location.pathname])
  useEffect(() => {
    if (!menuOpen) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    navigation.current?.querySelector<HTMLElement>('button, a')?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { setMenuOpen(false); menuButton.current?.focus() }
      if (event.key === 'Tab') {
        const items = [...(navigation.current?.querySelectorAll<HTMLElement>('a, button, select') ?? [])].filter(el => el.getClientRects().length > 0)
        const first = items[0], last = items[items.length - 1]
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
      }
    }
    document.addEventListener('keydown', onKey)
    return () => { document.body.style.overflow = previousOverflow; document.removeEventListener('keydown', onKey) }
  }, [menuOpen])
  if (!user) return null
  const visible = (items: NavItem[]) => items.filter(item => mayVisit(user.role, item.to) && (item.to !== '/' || user.role === 'admin'))

  const closeMenu = () => setMenuOpen(false)

  return (
    <div className={`layout${presenting ? ' layout--presentation' : ''}`}>
      <a className="skip-link" href="#main-content">К содержимому</a>
      <header className="mobile-header">
        <NavLink to="/" className="mobile-header__brand" onClick={closeMenu}>
          <span className="mobile-header__mark"><IconLogo /></span>
          <span>Посещаемость</span>
        </NavLink>
        <button
          ref={menuButton}
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
      <nav ref={navigation} id="main-navigation" className={`sidebar${menuOpen ? ' sidebar--open' : ''}`} aria-label="Основная навигация">
        <div className="sidebar__top">
          <div className="sidebar__brand">
            <div className="sidebar__logo">
              <IconLogo />
            </div>
            <div>
              Посещаемость
              <small>учебное пространство</small>
            </div>
          </div>
          <button type="button" className="sidebar__dismiss" aria-label="Закрыть навигацию" onClick={closeMenu}>
            <IconClose />
          </button>
        </div>
        <div className="sidebar__section">Рабочее пространство</div>
        <Links items={visible(monitoring)} onNavigate={closeMenu} />
        {visible(setup).length > 0 && <div className="sidebar__section">Организация</div>}
        <Links items={visible(setup)} onNavigate={closeMenu} />
        <div className="sidebar__account">
          {isStaticData ? <label className="field">Роль в учебном примере<select className="select" value={user.role} onChange={event => {
            const role = event.target.value as Role
            setDemoRole(role); navigate(homeForRole[role]); closeMenu()
          }}>{Object.entries(roleLabels).map(([role, label]) => <option key={role} value={role}>{label}</option>)}</select></label> : <><strong>{user.username}</strong><span>{roleLabels[user.role]}</span>
            <button className="btn btn--ghost" disabled={loggingOut} onClick={async () => {
              setLoggingOut(true); setLogoutError(null)
              try { await logout() } catch (e) { setLogoutError((e as Error).message) } finally { setLoggingOut(false) }
            }}>{loggingOut ? 'Выход…' : 'Выйти'}</button>
            {logoutError && <p role="alert">{logoutError}</p>}
          </>}
        </div>
      </nav>
      <main ref={content} tabIndex={-1} id="main-content" className="content">
        <div className="workspace-bar"><span className="workspace-source"><i />{isStaticData ? `Учебный пример · ${DEMO_DATE}` : 'Рабочие данные'}</span><span>{TIME_ZONE}</span>
          {user.role === 'admin' && <PresentationControls onActiveChange={setPresenting} />}
        </div>
        <Outlet />
        <footer className="workspace-footer">{isStaticData ? 'Синтетические данные. Изменения действуют до перезагрузки.' : 'Доступ ограничен вашей ролью и назначениями.'} Подсчёт людей не подтверждает присутствие конкретного студента.</footer>
      </main>
    </div>
  )
}
