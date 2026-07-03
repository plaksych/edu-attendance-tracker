import { useEffect, useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api/client'
import type { EntityStats, Group, GroupTimeline, SummaryStats } from '../api/types'
import { RateBadge, formatRate } from '../components/RateBadge'
import { StatCard } from '../components/StatCard'

export function DashboardPage() {
  const [summary, setSummary] = useState<SummaryStats | null>(null)
  const [groups, setGroups] = useState<Group[]>([])
  const [selectedGroup, setSelectedGroup] = useState<number | null>(null)
  const [timeline, setTimeline] = useState<GroupTimeline | null>(null)
  const [groupStats, setGroupStats] = useState<EntityStats | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.getSummary(), api.getGroups()])
      .then(([summaryData, groupsData]) => {
        setSummary(summaryData)
        setGroups(groupsData)
        if (groupsData.length > 0) setSelectedGroup(groupsData[0].id)
      })
      .catch((e: Error) => setError(e.message))
  }, [])

  useEffect(() => {
    if (selectedGroup === null) return
    setTimeline(null)
    setGroupStats(null)
    Promise.all([api.getGroupTimeline(selectedGroup), api.getGroupStats(selectedGroup)])
      .then(([timelineData, statsData]) => {
        setTimeline(timelineData)
        setGroupStats(statsData)
      })
      .catch((e: Error) => setError(e.message))
  }, [selectedGroup])

  if (error) return <div className="alert alert--error">Ошибка загрузки: {error}</div>
  if (!summary) return <div className="loading">Загрузка…</div>

  const chartData =
    timeline?.points.map((p) => ({
      date: new Date(p.date).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' }),
      rate: p.avg_rate !== null ? Math.round(p.avg_rate * 100) : null,
      detected: p.detected_avg,
    })) ?? []

  return (
    <>
      <header className="page-header">
        <h1>Дашборд</h1>
        <p>Сводная статистика посещаемости по данным распознавания</p>
      </header>

      <div className="cards-grid">
        <StatCard
          label="Средняя посещаемость"
          value={formatRate(summary.avg_attendance_rate)}
          hint="по всем завершённым занятиям"
        />
        <StatCard
          label="Занятий сегодня"
          value={summary.sessions_today}
          hint={`всего проведено: ${summary.sessions_finished}`}
        />
        <StatCard label="Групп" value={summary.groups} />
        <StatCard label="Преподавателей" value={summary.teachers} />
        <StatCard label="Дисциплин" value={summary.disciplines} />
      </div>

      <section className="section card">
        <div className="section__controls">
          <h2 style={{ margin: 0 }}>Динамика посещаемости группы</h2>
          <select
            className="select"
            value={selectedGroup ?? ''}
            onChange={(e) => setSelectedGroup(Number(e.target.value))}
          >
            {groups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </select>
        </div>
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="date" fontSize={12} />
              <YAxis domain={[0, 100]} fontSize={12} unit="%" />
              <Tooltip
                formatter={(value: number, name: string) =>
                  name === 'rate' ? [`${value}%`, 'Посещаемость'] : [value, 'В среднем человек']
                }
              />
              <Line
                type="monotone"
                dataKey="rate"
                stroke="#2f6fed"
                strokeWidth={2}
                dot={{ r: 3 }}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="loading">
            {timeline ? 'Нет данных по завершённым занятиям группы' : 'Загрузка…'}
          </div>
        )}
      </section>

      {groupStats && (
        <section className="section card">
          <h2>
            {groupStats.name}: посещаемость по дисциплинам
            {groupStats.avg_rate !== null && (
              <>
                {' — в среднем '}
                <RateBadge rate={groupStats.avg_rate} />
              </>
            )}
          </h2>
          <table className="table">
            <thead>
              <tr>
                <th>Дисциплина</th>
                <th>Занятий</th>
                <th>В среднем человек</th>
                <th>Посещаемость</th>
              </tr>
            </thead>
            <tbody>
              {groupStats.breakdown.length === 0 && (
                <tr>
                  <td colSpan={4} className="table__empty">
                    Пока нет завершённых занятий
                  </td>
                </tr>
              )}
              {groupStats.breakdown.map((row) => (
                <tr key={row.id}>
                  <td>{row.name}</td>
                  <td>{row.sessions}</td>
                  <td>{row.avg_detected ?? '—'}</td>
                  <td>
                    <RateBadge rate={row.avg_rate} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </>
  )
}
