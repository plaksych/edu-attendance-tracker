import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { DashboardPage } from './pages/DashboardPage'
import { SchedulePage } from './pages/SchedulePage'
import { SessionsPage } from './pages/SessionsPage'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="sessions" element={<SessionsPage />} />
        <Route path="schedule" element={<SchedulePage />} />
      </Route>
    </Routes>
  )
}
