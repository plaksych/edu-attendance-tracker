// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { SessionProvider, useSession } from '../src/auth/SessionProvider'
import { LoginPage } from '../src/pages/LoginPage'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })
it('restores a cookie session, then sends CSRF logout', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ id: 1, username: 'operator', role: 'operator', csrf_token: 'csrf' }))).mockResolvedValueOnce(new Response(null, { status: 204 })))
  function Consumer() { const { user, logout } = useSession(); return <><span>{user?.username ?? 'guest'}</span><button onClick={() => void logout()}>Logout</button></> }
  render(<SessionProvider><Consumer /></SessionProvider>)
  await screen.findByText('operator')
  fireEvent.click(screen.getByText('Logout'))
  await screen.findByText('guest')
  const init = vi.mocked(fetch).mock.calls[1][1]
  expect(new Headers(init?.headers).get('X-CSRF-Token')).toBe('csrf')
})
it('shows login error, clears password, and submits exact credentials', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 401 })))
  render(<MemoryRouter><SessionProvider><LoginPage /></SessionProvider></MemoryRouter>)
  await act(async () => {})
  fireEvent.change(screen.getByLabelText('Логин'), { target: { value: 'operator' } })
  fireEvent.change(screen.getByLabelText('Пароль'), { target: { value: 'incorrect-password' } })
  fireEvent.click(screen.getByRole('button', { name: 'Войти' }))
  await screen.findByText('Неверный логин или пароль.')
  expect(screen.getByLabelText('Пароль')).toHaveValue('')
  expect(JSON.parse(String(vi.mocked(fetch).mock.calls[1][1]?.body))).toEqual({ username: 'operator', password: 'incorrect-password' })
})
