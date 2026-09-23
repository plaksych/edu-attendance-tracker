import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, isStaticData } from '../api/client'
import type { Group, GroupTimeline } from '../api/types'
import { formatRate } from '../components/RateCell'
import { StatCard } from '../components/StatCard'
import { IconExternal, IconRefresh } from '../components/icons'
import { downloadBlob, downloadCsv } from '../lib/export'
import { managementApi } from '../api/management'
import { fmtDateShort, shiftDate, TIME_ZONE, today } from '../lib/format'

export function AnalyticsPage() {
  const [params, setParams] = useSearchParams()
  const [groups, setGroups] = useState<Group[]>([])
  const [timeline, setTimeline] = useState<GroupTimeline | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const groupId = Number(params.get('group')) || groups[0]?.id
  const from = params.get('from') || shiftDate(today(), -13)
  const to = params.get('to') || today()
  const update = (key: string, value: string) => setParams(previous => { const next = new URLSearchParams(previous); next.set(key, value); return next })
  useEffect(() => {
    let active = true
    setError(null); setLoading(true)
    api.getGroups().then(data => { if (active) { setGroups(data); if (!data.length) setLoading(false) } }).catch(e => { if (active) { setError(e.message); setLoading(false) } })
    return () => { active = false }
  }, [revision])
  useEffect(() => {
    if (!groupId || from > to) return
    let active = true
    setTimeline(null); setError(null); setLoading(true)
    api.getGroupTimeline(groupId, { date_from: from, date_to: to }).then(data => { if (active) setTimeline(data) }).catch(e => { if (active) setError(e.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [groupId, revision, from, to])
  const points = useMemo(() => timeline?.points.filter(p => p.date >= from && p.date <= to) ?? [], [timeline, from, to])
  const measured = points.filter(p => p.avg_rate !== null)
  const chart = points.map(p => ({ date: fmtDateShort(p.date), rate: p.avg_rate === null ? null : Math.round(p.avg_rate * 100) }))
  const exportReport = async () => {
    if (exporting || !groupId) return
    const filename = `attendance-${groupId}-${from}-${to}.csv`
    if (!isStaticData) {
      setExporting(true); setExportError(null)
      try { downloadBlob(filename, await managementApi.exportStats({ date_from: from, date_to: to, group_id: String(groupId) })) }
      catch (e) { setExportError((e as Error).message) }
      finally { setExporting(false) }
      return
    }
    downloadCsv(filename, [
    ['Источник', isStaticData ? 'Учебный пример (demo_fixture)' : 'Серверные агрегаты'], ['Группа', timeline?.group_name], ['Период', from, to], ['Часовой пояс', TIME_ZONE],
    ['Определение', 'Оценка числа людей / ожидаемая численность. Нет измерения: пустая ячейка. Не идентификация студентов.'],
    ['Дата', 'Присутствие, доля', 'В среднем людей', 'Ожидалось'], ...points.map(p => [p.date, p.avg_rate, p.avg_detected, p.expected]),
    ])
  }
  const exportPeriodInvalid = from > to || (Date.parse(to) - Date.parse(from)) / 86_400_000 > 365
  return <>
    <header className="page-header"><div><h1>Аналитика</h1><p>Динамика присутствия и полнота данных по группе</p></div><button className="btn" disabled={!points.length || loading || !!error || exporting || exportPeriodInvalid} onClick={() => void exportReport()}><IconExternal />{exporting ? 'Подготовка…' : 'Скачать отчёт'}</button></header>
    {exportError && <p role="alert" className="alert alert--error">{exportError}</p>}
    {exportPeriodInvalid && from <= to && <p role="alert" className="alert alert--error">Экспорт доступен за период до 366 дней.</p>}
    <div className="filter-bar">
      <label className="field">Группа<select className="select" value={groupId ?? ''} onChange={e => update('group', e.target.value)}>{groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}</select></label>
      <label className="field">С даты<input type="date" className="input" value={from} max={to} onChange={e => e.target.value && update('from', e.target.value)} /></label>
      <label className="field">По дату<input type="date" className="input" value={to} min={from} onChange={e => e.target.value && update('to', e.target.value)} /></label>
      <button className="btn btn--ghost" onClick={() => setParams({})}>Сбросить фильтры</button>
      <button className="icon-button" title="Обновить" aria-label="Обновить" onClick={() => setRevision(n => n + 1)}><IconRefresh /></button>
    </div>
    {from > to && <p role="alert" className="alert alert--error">Начало периода должно быть раньше окончания.</p>}
    {error ? <div role="alert" className="alert alert--error">{error}<button className="btn btn--ghost" onClick={() => setRevision(n => n + 1)}>Повторить</button></div> : loading ? <div className="loading" role="status">Загрузка аналитики…</div> : !points.length ? <section className="empty"><h2>Нет данных за выбранный период</h2><p>Измените даты или выберите другую группу.</p><button className="btn btn--ghost" onClick={() => setParams({})}>Сбросить фильтры</button></section> : <>
      <div className="grid grid--stats grid--stats-compact">
        <StatCard label="Дней с измерениями" value={`${measured.length} / ${points.length}`} tone="teal" hint="в полученной выборке" />
        <StatCard label="Последняя оценка" value={formatRate(measured[measured.length - 1]?.avg_rate ?? null)} tone="blue" hint={measured[measured.length - 1]?.date ?? 'нет измерений'} />
        <StatCard label="Дней без результата" value={points.length - measured.length} tone="amber" hint="не включаются как нули" />
      </div>
      <section className="section analytics-chart"><h2>Присутствие по дням</h2><ResponsiveContainer width="100%" height={280}><LineChart data={chart} margin={{ left: 0, right: 16, top: 16, bottom: 0 }}><CartesianGrid vertical={false} stroke="var(--border)" /><XAxis dataKey="date" tickLine={false} /><YAxis unit="%" domain={[0, 'auto']} width={55} tickLine={false} /><Tooltip formatter={(value: number) => [`${value}%`, 'Оценка присутствия']} /><Line dataKey="rate" stroke="var(--primary)" strokeWidth={3} dot={{ r: 3 }} connectNulls={false} isAnimationActive={false} /></LineChart></ResponsiveContainer></section>
      <p className="metric-note">Присутствие: оценка числа людей относительно численности группы. Уверенность детектора не является точностью. Пропуски не равны нулю; значения выше 100% требуют проверки.</p>
      <div className="table-wrap" role="region" aria-label="Данные графика" tabIndex={0}><table className="table"><caption>Данные за {from} — {to} · {timeline?.group_name}</caption><thead><tr><th scope="col">Дата</th><th scope="col">Оценка присутствия</th><th scope="col">В среднем людей</th><th scope="col">Ожидалось</th></tr></thead><tbody>{points.map(p => <tr key={p.date}><td>{p.date}</td><td>{p.avg_rate === null ? 'Нет результата' : formatRate(p.avg_rate)}</td><td>{p.avg_detected?.toFixed(1) ?? '—'}</td><td>{p.expected ?? '—'}</td></tr>)}</tbody></table></div>
    </>}
  </>
}
