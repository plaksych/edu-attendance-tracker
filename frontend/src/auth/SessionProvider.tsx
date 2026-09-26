import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { isStaticData } from '../api/client'
import { ApiError, json, request, setCsrfToken } from '../api/http'
import type { Role } from './permissions'

export interface User { id: number; username: string; role: Role; csrf_token: string }
function validateUser(user: User): User {
  if (!user || !['admin', 'operator', 'teacher', 'analyst'].includes(user.role) || !user.csrf_token) {
    throw new Error('Некорректный ответ сервера авторизации.')
  }
  return user
}
interface SessionContextValue {
  user: User | null; loading: boolean; error: string | null
  refresh: () => Promise<void>; login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>; setDemoRole: (role: Role) => void
}
const SessionContext = createContext<SessionContextValue | null>(null)
const demoUser: User = { id: 0, username: 'Учебный кабинет', role: 'admin', csrf_token: '' }

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(isStaticData ? demoUser : null)
  const [loading, setLoading] = useState(!isStaticData)
  const [error, setError] = useState<string | null>(null)
  const accept = (next: User) => { setCsrfToken(next.csrf_token); setUser(next) }
  const refresh = useCallback(async () => {
    if (isStaticData) return
    setLoading(true)
    setError(null)
    try { accept(validateUser(await request<User>('/auth/me'))) }
    catch (e) {
      setUser(null)
      setCsrfToken(null)
      if (!(e instanceof ApiError && e.status === 401)) setError((e as Error).message)
    } finally { setLoading(false) }
  }, [])
  useEffect(() => {
    void refresh()
    const expire = () => { setUser(null); setCsrfToken(null) }
    window.addEventListener('session-expired', expire)
    return () => window.removeEventListener('session-expired', expire)
  }, [refresh])
  const login = async (username: string, password: string) => {
    await request<unknown>('/auth/login', json('POST', { username, password }))
    accept(validateUser(await request<User>('/auth/me')))
    setError(null)
  }
  const logout = async () => {
    await request<void>('/auth/logout', { method: 'POST' })
    setCsrfToken(null)
    setUser(null)
  }
  return <SessionContext.Provider value={{ user, loading, error, refresh, login, logout,
    setDemoRole: (role) => { if (isStaticData) setUser({ ...demoUser, role }) },
  }}>{children}</SessionContext.Provider>
}
export function useSession() {
  const value = useContext(SessionContext)
  if (!value) throw new Error('SessionProvider is required')
  return value
}
