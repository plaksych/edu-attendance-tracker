import { NavLink, Outlet } from 'react-router-dom'

const links = [
  { to: '/', label: 'Дашборд' },
  { to: '/sessions', label: 'Занятия' },
  { to: '/schedule', label: 'Расписание' },
]

export function Layout() {
  return (
    <div className="layout">
      <nav className="sidebar">
        <div className="sidebar__brand">
          Посещаемость
          <span>Контроль на основе компьютерного зрения</span>
        </div>
        {links.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              isActive ? 'sidebar__link sidebar__link--active' : 'sidebar__link'
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>
      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}
