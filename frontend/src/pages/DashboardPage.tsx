import { useEffect, useMemo, useState } from 'react'
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
import type { Discipline, EntityStats, Group, GroupTimeline, SummaryStats, Teacher } from '../api/types'
import { formatRate, RateCell } from '../components/RateCell'
import { StatCard } from '../components/StatCard'
import { fmtDateShort } from '../lib/format'

type Dimension = 'groups' | 'teachers' | 'disciplines'

const DIMENSIONS: { key: Dimension; label: string; breakdownTitle: string }[] = [
  { key: 'groups', label: 'Группы', breakdownTitle: 'По дисциплинам' },
  { key: 'teachers', label: 'Преподаватели', breakdownTitle: 'По группам' },
  { key: 'disciplines', label: 'Дисциплины', breakdownTitle: 'По группам' },
]

export function DashboardPage() {
  const [summary, setSummary] = useState<SummaryStats | null>(null)
  const [groups, setGroups] = useState<Group[]>([])
  const [teachers, setTeachers] = useState<Teacher[]>([])
  const [disciplines, setDisciplines] = useState<Discipline[]>([])
  const [dimension, setDimension] = useState<Dimension>('groups')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [stats, setStats] = useState<EntityStats | null>(null)
  const [timeline, setTimeline] = useState<GroupTimeline | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.getSummary(), api.getGroups(), api.getTeachers(), api.getDisciplines()])
      .then(([summaryData, groupsData, teachersData, disciplinesData]) => {
        setSummary(summaryData)
        setGroups(groupsData)
        setTeachers(teachersData)
        setDisciplines(disciplinesData)
      })
      .catch((e: Error) => setError(e.message))
  }, [])

  const options = useMemo(() => {
    if (dimension === 'groups') return groups.map((g) => ({ id: g.id, name: g.name }))
    if (dimension === 'teachers') return teachers.map((t) => ({ id: t.id, name: t.full_name }))
    return disciplines.map((d) => ({ id: d.id, name: d.name }))
  }, [dimension, groups, teachers, disciplines])

  useEffect(() => {
    setSelectedId(options.length > 0 ? options[0].id : null)
  }, [options])

  useEffect(() => {
    if (selectedId === null) return
    setStats(null)
    setTimeline(null)
    const loadStats =
      dimension === 'groups'
        ? api.getGroupStats(selectedId)
        : dimension === 'teachers'
          ? api.getTeacherStats(selectedId)
          : api.getDisciplineStats(selectedId)
    loadStats.then(setStats).catch((e: Error) => setError(e.message))
    if (dimension === 'groups') {
      api
        .getGroupTimeline(selectedId)
        .then(setTimeline)
        .catch(() => setTimeline(null))
    }
  }, [dimension, selectedId])

  if (error) return <div className="alert alert--error">Ошибка загрузки: {error}</div>
  if (!summary) return <div className="loading">Загрузка…</div>

  const chartData =
    timeline?.points.map((p) => ({
      date: fmtDateShort(p.date),
      rate: p.avg_rate !== null ? Math.round(p.avg_rate * 100) : null,
    })) ?? []

  const measured = summary.records_complete + summary.records_partial + summary.records_failed
  const dimensionMeta = DIMENSIONS.find((d) => d.key === dimension)!

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Дашборд</h1>
          <p>Посещаемость по данным автоматических замеров</p>
        </div>
      </header>

      <div className="grid grid--stats">
        <StatCard
          label="Средняя посещаемость"
          value={formatRate(summary.avg_attendance_rate)}
          hint="по всем занятиям с замерами"
        />
        <StatCard
          label="Занятий сегодня"
          value={summary.sessions_today}
          hint={`проведено всего: ${summary.sessions_finished}`}
        />
        <StatCard
          label="Замеры выполнены"
          value={measured > 0 ? `${summary.records_complete} / ${measured}` : '—'}
          hint={
            measured > 0
              ? `частичных: ${summary.records_partial}, неудачных: ${summary.records_failed}`
              : 'занятия ещё не измерялись'
          }
        />
        <StatCard label="Групп" value={summary.groups} hint={`камер: ${summary.cameras}`} />
      </div>

      <section className="card section">
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 12,
            flexWrap: 'wrap',
            marginBottom: 16,
          }}
        >
          <div className="segmented">
            {DIMENSIONS.map((d) => (
              <button
                key={d.key}
                className={dimension === d.key ? 'active' : ''}
                onClick={() => setDimension(d.key)}
              >
                {d.label}
              </button>
            ))}
          </div>
          <select
            className="select"
            value={selectedId ?? ''}
            onChange={(e) => setSelectedId(Number(e.target.value))}
          >
            {options.map((option) => (
              <option key={option.id} value={option.id}>
                {option.name}
              </option>
            ))}
          </select>
        </div>

        {options.length === 0 ? (
          <div className="empty">
            Нет данных
            <small>Загрузите расписание — справочники заполнятся автоматически</small>
          </div>
        ) : stats === null ? (
          <div className="loading">Загрузка…</div>
        ) : (
          <>
            <div className="grid grid--stats">
              <StatCard label="Занятий с итогом" value={stats.sessions_finished} />
              <StatCard
                label="Средняя посещаемость"
                value={formatRate(stats.avg_rate)}
                hint={
                  stats.avg_detected !== null
                    ? `в среднем ${stats.avg_detected} чел.`
                    : undefined
                }
              />
              <StatCard
                label="Полные замеры"
                value={stats.records_complete}
                hint={`частичных: ${stats.records_partial}, неудачных: ${stats.records_failed}`}
              />
            </div>

            {dimension === 'groups' && chartData.length > 0 && (
              <div style={{ marginBottom: 18 }}>
                <h2>Динамика по датам</h2>
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={chartData} margin={{ top: 4, right: 12, bottom: 0, left: -18 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="date" fontSize={12} tickLine={false} />
                    <YAxis domain={[0, 100]} fontSize={12} unit="%" tickLine={false} />
                    <Tooltip formatter={(value: number) => [`${value}%`, 'Посещаемость']} />
                    <Line
                      type="monotone"
                      dataKey="rate"
                      stroke="var(--primary)"
                      strokeWidth={2}
                      dot={{ r: 2.5 }}
                      connectNulls
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            <h2>{dimensionMeta.breakdownTitle}</h2>
            <table className="table">
              <thead>
                <tr>
                  <th>Название</th>
                  <th>Занятий</th>
                  <th>В среднем человек</th>
                  <th>Посещаемость</th>
                </tr>
              </thead>
              <tbody>
                {stats.breakdown.length === 0 && (
                  <tr>
                    <td colSpan={4} className="table__empty">
                      Пока нет занятий с рассчитанным итогом
                    </td>
                  </tr>
                )}
                {stats.breakdown.map((row) => (
                  <tr key={row.id}>
                    <td>{row.name}</td>
                    <td className="num">{row.sessions}</td>
                    <td className="num">{row.avg_detected ?? '—'}</td>
                    <td style={{ maxWidth: 160 }}>
                      <RateCell rate={row.avg_rate} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </section>
    </>
  )
}
