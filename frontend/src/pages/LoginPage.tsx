import { useState, type FormEvent } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useSession } from '../auth/SessionProvider'
import { homeForRole } from '../auth/permissions'
import { IconLogo } from '../components/icons'

export function LoginPage() {
  const { user, login, error: sessionError, refresh } = useSession()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  if (user) {
    const from = (location.state as { from?: string } | null)?.from
    return <Navigate replace to={from?.startsWith('/') && !from.startsWith('//') && !from.includes('\\') && !from.startsWith('/login') ? from : homeForRole[user.role]} />
  }
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (busy) return
    setBusy(true); setError(null)
    try { await login(username.trim(), password) }
    catch (e) { setError((e as Error).message) }
    finally { setPassword(''); setBusy(false) }
  }
  return <main className="login-page">
    <div className="login-brand"><IconLogo /><span>Посещаемость</span></div>
    <section className="login-panel" aria-labelledby="login-title">
      <p className="eyebrow">Учебное заведение · Рабочий кабинет</p>
      <h1 id="login-title">Вход в систему</h1>
      <p>Войдите с учётной записью вашего учебного заведения.</p>
      <form onSubmit={submit} className="modal__form">
        <div className="field"><label htmlFor="username">Логин</label><input id="username" className="input" autoComplete="username" required maxLength={160} value={username} onChange={e => setUsername(e.target.value)} autoFocus /></div>
        <div className="field"><label htmlFor="password">Пароль</label><input id="password" type="password" className="input" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} /></div>
        {(error || sessionError) && <div className="alert alert--error" role="alert">{error || sessionError}</div>}
        <button className="btn" disabled={busy}>{busy ? 'Вход…' : 'Войти'}</button>
        {sessionError && <button type="button" className="btn btn--ghost" onClick={() => void refresh()}>Проверить соединение</button>}
      </form>
      <p className="login-help">Для получения доступа или восстановления пароля обратитесь к администратору.</p>
    </section>
    <p className="login-footer">Подсчёт людей, без установления личности.</p>
  </main>
}
