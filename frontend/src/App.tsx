import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'

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

export default function App() {
  return (
    <Suspense fallback={<div className="loading">Загрузка…</div>}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="sessions" element={<SessionsPage />} />
          <Route path="sessions/:id" element={<SessionDetailPage />} />
          <Route path="schedule" element={<SchedulePage />} />
          <Route path="cameras" element={<CamerasPage />} />
          <Route path="catalog" element={<CatalogPage />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
