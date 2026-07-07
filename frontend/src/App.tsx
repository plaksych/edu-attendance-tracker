import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { CamerasPage } from './pages/CamerasPage'
import { CatalogPage } from './pages/CatalogPage'
import { DashboardPage } from './pages/DashboardPage'
import { SchedulePage } from './pages/SchedulePage'
import { SessionDetailPage } from './pages/SessionDetailPage'
import { SessionsPage } from './pages/SessionsPage'

export default function App() {
  return (
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
  )
}
