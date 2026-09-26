import { useEffect, useState, type FormEvent } from 'react'
import { managementApi } from '../api/management'
import type { RecognitionHistory as History } from '../api/types'
import { Modal } from './Modal'
import { fmtClock } from '../lib/format'

export function RecognitionHistory({ uploadId, jobId, hasResult }: { uploadId: number; jobId: number; hasResult: boolean }) {
  const [history, setHistory] = useState<History | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)
  const [correcting, setCorrecting] = useState(false)
  const [count, setCount] = useState('')
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  useEffect(() => {
    let active = true
    setHistory(null); setError(null)
    managementApi.history(uploadId).then(data => { if (active) setHistory(data) }).catch(e => { if (active) setError(e.message) })
    return () => { active = false }
  }, [uploadId, jobId, revision])
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (saving) return
    setSaving(true); setSaveError(null)
    try { await managementApi.correct(uploadId, { people_count: Number(count), reason }); setCorrecting(false); setCount(''); setReason(''); setRevision(n => n + 1) }
    catch (e) { setSaveError((e as Error).message) }
    finally { setSaving(false) }
  }
  return <section className="history-section"><h2>История результата</h2>
    {error && <p className="alert alert--error" role="alert">{error}<button className="btn btn--ghost" onClick={() => setRevision(n => n + 1)}>Повторить</button></p>}
    {!history && !error && <p role="status">Загрузка истории…</p>}
    {history && <><div className="table-wrap"><table className="table"><thead><tr><th>Версия</th><th>Состояние</th><th>Исходный подсчёт</th><th>Модель</th></tr></thead><tbody>{history.jobs.map(job => <tr key={job.id}><td>#{job.id}</td><td>{{ pending: 'В очереди', processing: 'Обработка', retry_wait: 'Ожидает повтора', completed: 'Готово', failed: 'Ошибка', cancelled: 'Отменено' }[job.status]}</td><td>{job.result?.people_count ?? 'Нет результата'}</td><td>{job.model_name} · {job.model_version}</td></tr>)}</tbody></table></div>
      <h3>Ручные корректировки</h3>{history.corrections.length === 0 ? <p className="metric-note">Корректировок нет.</p> : <div className="table-wrap"><table className="table"><thead><tr><th>Версия</th><th>Человек</th><th>Автор</th><th>Причина</th><th>Время</th></tr></thead><tbody>{history.corrections.map(c => <tr key={c.id}><td>#{c.job_id}</td><td>{c.people_count}</td><td>{c.actor_id === null ? 'Не указан' : `#${c.actor_id}`}</td><td>{c.reason}</td><td>{c.created_at.slice(0, 10)} {fmtClock(c.created_at)}</td></tr>)}</tbody></table></div>}</>}
    {hasResult && <button className="btn btn--ghost" onClick={() => { setCorrecting(true); setSaveError(null) }}>Добавить корректировку</button>}
    {correcting && <Modal title="Ручная корректировка" onClose={() => { if (!saving) setCorrecting(false) }}><form className="modal__form" onSubmit={submit}>
      <p>Исходный результат сохранится. Корректировка не подтверждает личности студентов.</p>
      <label className="field">Количество людей<input className="input" type="number" required min="0" max="10000" step="1" value={count} onChange={e => setCount(e.target.value)} /></label>
      <label className="field">Причина<textarea className="input" required minLength={3} maxLength={500} value={reason} onChange={e => setReason(e.target.value)} /></label>
      {saveError && <p role="alert" className="alert alert--error">{saveError}</p>}
      <button className="btn" disabled={saving}>{saving ? 'Сохранение…' : 'Сохранить корректировку'}</button>
    </form></Modal>}
  </section>
}
