import { useEffect, useState, type FormEvent } from 'react'
import { api, isStaticData } from '../api/client'
import { managementApi, type AuditEvent, type ManagedUser } from '../api/management'
import type { Group } from '../api/types'
import { roleLabels, type Role } from '../auth/permissions'
import { Modal } from '../components/Modal'
import { fmtClock } from '../lib/format'

function UserDialog({ user, onClose, onSaved }: { user: ManagedUser | null; onClose: () => void; onSaved: () => void }) {
  const [username, setUsername] = useState(user?.username ?? '')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>(user?.role ?? 'teacher')
  const [enabled, setEnabled] = useState(user?.enabled ?? true)
  const [reason, setReason] = useState('')
  const [replaceGroups, setReplaceGroups] = useState(false)
  const [groups, setGroups] = useState<Group[]>([])
  const [selected, setSelected] = useState<number[]>([])
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  useEffect(() => { api.getGroups().then(setGroups).catch(e => setError(e.message)) }, [])
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (saving) return
    setSaving(true); setError(null)
    try {
      if (user) await managementApi.updateUser(user.id, { role, enabled, reason, ...(password ? { password } : {}), ...(replaceGroups ? { group_ids: selected } : {}) })
      else await managementApi.createUser({ username, password, role })
      setPassword(''); onSaved(); onClose()
    } catch (e) { setError((e as Error).message) }
    finally { setSaving(false) }
  }
  return <Modal title={user ? `Доступ: ${user.username}` : 'Новый пользователь'} onClose={() => { if (!saving) onClose() }}><form className="modal__form" onSubmit={submit}>
    {!user && <label className="field">Логин<input className="input" autoComplete="off" required pattern="[a-zA-Z0-9._\-]+" maxLength={120} value={username} onChange={e => setUsername(e.target.value)} /></label>}
    <label className="field">{user ? 'Новый пароль (необязательно)' : 'Пароль'}<input className="input" type="password" autoComplete="new-password" minLength={12} maxLength={256} required={!user} value={password} onChange={e => setPassword(e.target.value)} /><span>Не менее 12 символов</span></label>
    <label className="field">Роль<select className="select" value={role} onChange={e => setRole(e.target.value as Role)}>{Object.entries(roleLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
    {user && <><label><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} /> Доступ включён</label>
      <label><input type="checkbox" checked={replaceGroups} onChange={e => setReplaceGroups(e.target.checked)} /> Заменить назначения групп</label>
      {replaceGroups && <fieldset><legend>Новый полный список назначений</legend><p className="metric-note">Существующие назначения будут заменены. Пустой список отзовёт доступ ко всем группам.</p>{groups.map(g => <label className="checkbox-row" key={g.id}><input type="checkbox" checked={selected.includes(g.id)} onChange={e => setSelected(ids => e.target.checked ? [...ids, g.id] : ids.filter(id => id !== g.id))} />{g.name}</label>)}</fieldset>}
      <label className="field">Причина изменения<textarea className="input" required minLength={3} maxLength={500} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <p className="metric-note">Изменение доступа завершит действующие сессии пользователя.</p></>}
    {error && <p className="alert alert--error" role="alert">{error}</p>}
    <div className="modal__actions"><button className="btn btn--ghost" type="button" disabled={saving} onClick={onClose}>Отмена</button><button className="btn" disabled={saving}>{saving ? 'Сохранение…' : user ? 'Сохранить' : 'Создать'}</button></div>
  </form></Modal>
}

export function AdminPage({ audit = false }: { audit?: boolean }) {
  const [users, setUsers] = useState<ManagedUser[]>([])
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)
  const [editing, setEditing] = useState<ManagedUser | null | undefined>(undefined)
  useEffect(() => { setOffset(0) }, [audit])
  useEffect(() => {
    if (isStaticData) { setLoading(false); return }
    let active = true
    setLoading(true); setError(null)
    const load = audit ? managementApi.audit(offset).then(data => { if (active) setEvents(data) }) : managementApi.users(offset).then(data => { if (active) setUsers(data) })
    load.catch(e => { if (active) setError(e.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [audit, offset, revision])
  if (isStaticData) return <section className="empty"><h1>{audit ? 'Журнал действий' : 'Доступ'}</h1><p>Учебная витрина не содержит учётных записей и событий безопасности.</p></section>
  return <>
    <header className="page-header"><div><h1>{audit ? 'Журнал действий' : 'Доступ'}</h1><p>{audit ? 'События, сохранённые сервером' : 'Учётные записи и назначения групп'}</p></div>{!audit && <button className="btn" onClick={() => setEditing(null)}>Добавить пользователя</button>}</header>
    {error && <div className="alert alert--error" role="alert">{error}<button className="btn btn--ghost" onClick={() => setRevision(n => n + 1)}>Повторить</button></div>}
    {loading ? <div className="loading" role="status">Загрузка…</div> : <div className="table-wrap"><table className="table"><thead><tr>{(audit ? ['Время', 'Автор', 'Действие', 'Объект', 'Причина', 'Запрос'] : ['Логин', 'Роль', 'Доступ', 'Действия']).map(label => <th key={label} scope="col">{label}</th>)}</tr></thead><tbody>
      {audit ? events.map(e => <tr key={e.id}><td>{e.created_at.slice(0, 10)} {fmtClock(e.created_at)}</td><td>{e.actor_id ?? 'Система'}</td><td>{e.action}</td><td>{e.object_type} {e.object_id ?? ''}</td><td>{e.reason ?? '—'}</td><td>{e.request_id ?? '—'}</td></tr>) : users.map(u => <tr key={u.id}><td>{u.username}</td><td>{roleLabels[u.role]}</td><td>{u.enabled ? 'Включён' : 'Отключён'}</td><td><button className="btn btn--ghost btn--sm" onClick={() => setEditing(u)}>Изменить</button></td></tr>)}
      {(audit ? events : users).length === 0 && <tr><td colSpan={audit ? 6 : 4} className="table__empty">Нет записей</td></tr>}
    </tbody></table></div>}
    <div className="pagination"><button className="btn btn--ghost" disabled={loading || offset === 0} onClick={() => setOffset(n => Math.max(0, n - 25))}>Назад</button><span>Страница {Math.floor(offset / 25) + 1}</span><button className="btn btn--ghost" disabled={loading || (audit ? events : users).length < 25} onClick={() => setOffset(n => n + 25)}>Далее</button></div>
    {editing !== undefined && <UserDialog user={editing} onClose={() => setEditing(undefined)} onSaved={() => setRevision(n => n + 1)} />}
  </>
}
