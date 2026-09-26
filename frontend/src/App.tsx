import { lazy, Suspense } from 'react'
import { Link, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { Layout } from './components/Layout'
import { SessionProvider, useSession } from './auth/SessionProvider'
import { homeForRole, mayVisit } from './auth/permissions'
import { LoginPage } from './pages/LoginPage'

const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage').then(m => ({ default: m.AnalyticsPage })))
const AdminPage = lazy(() => import('./pages/AdminPage').then(m => ({ default: m.AdminPage })))
const SystemPage = lazy(() => import('./pages/SystemPage').then(m => ({ default: m.SystemPage })))

function ProtectedRoutes() {
  const { user, loading } = useSession()
  const location = useLocation()
  if (loading) return <div className="loading" role="status">Проверка сессии…</div>
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  return <Layout />
}
function RoleBoundary() {
  const { user } = useSession()
  const location = useLocation()
  if (!user || !mayVisit(user.role, location.pathname)) return <section className="empty"><h1>Недостаточно прав</h1><p>Этот раздел недоступен для вашей роли.</p><Link className="btn" to="/">Вернуться к обзору</Link></section>
  return <Outlet />
}
function Home() {
  const { user } = useSession()
  return user && user.role !== 'admin' ? <Navigate replace to={homeForRole[user.role]} /> : <DashboardPage />
}

const DashboardPage = lazy(() =>
  import('./pages/DashboardPage').then(({ DashboardPage }) => ({ default: DashboardPage })),
)
const SessionsPage = lazy(() =>
  import('./pages/SessionsPage').then(({ SessionsPage }) => ({ default: SessionsPage })),
)
const SessionDetailPage = lazy(() =>
  import('./pages/SessionDetailPage').then(({ SessionDetailPage }) => ({ default: SessionDetailPage })),
)
const SchedulePage = lazy(() =>
  import('./pages/SchedulePage').then(({ SchedulePage }) => ({ default: SchedulePage })),
)
const CamerasPage = lazy(() =>
  import('./pages/CamerasPage').then(({ CamerasPage }) => ({ default: CamerasPage })),
)
const CatalogPage = lazy(() =>
  import('./pages/CatalogPage').then(({ CatalogPage }) => ({ default: CatalogPage })),
)
const RecognitionPage = lazy(() =>
  import('./pages/RecognitionPage').then(({ RecognitionPage }) => ({ default: RecognitionPage })),
)

export default function App() {
  return (
    <SessionProvider><Suspense fallback={<div className="loading" role="status">Загрузка…</div>}>
      <Routes>
        <Route path="login" element={<LoginPage />} />
        <Route element={<ProtectedRoutes />}>
        <Route element={<RoleBoundary />}>
          <Route index element={<Home />} />
          <Route path="sessions" element={<SessionsPage />} />
          <Route path="sessions/:id" element={<SessionDetailPage />} />
          <Route path="schedule" element={<SchedulePage />} />
          <Route path="cameras" element={<CamerasPage />} />
          <Route path="recognition" element={<RecognitionPage />} />
          <Route path="catalog" element={<CatalogPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="admin/users" element={<AdminPage />} />
          <Route path="admin/audit" element={<AdminPage audit />} />
          <Route path="admin/system" element={<SystemPage />} />
          <Route path="*" element={<section className="empty"><h1>Страница не найдена</h1><Link className="btn" to="/">К обзору</Link></section>} />
        </Route>
        </Route>
      </Routes>
    </Suspense></SessionProvider>
  )
}
