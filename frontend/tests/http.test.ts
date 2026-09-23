// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { json, request, setCsrfToken } from '../src/api/http'
import { api } from '../src/api/client'

describe('HTTP session contract', () => {
  beforeEach(() => { setCsrfToken(null); vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}'))) })
  afterEach(() => vi.unstubAllGlobals())
  it('includes cookies and CSRF on every mutation', async () => {
    setCsrfToken('csrf-in-memory')
    await request('/auth/logout', { method: 'POST' })
    const [url, init] = vi.mocked(fetch).mock.calls[0]
    expect(url).toBe('/api/v1/auth/logout')
    expect(init?.credentials).toBe('include')
    expect(new Headers(init?.headers).get('X-CSRF-Token')).toBe('csrf-in-memory')
  })
  it('does not persist secrets or send CSRF on reads', async () => {
    setCsrfToken('secret')
    await request('/auth/me')
    expect(new Headers(vi.mocked(fetch).mock.calls[0][1]?.headers).has('X-CSRF-Token')).toBe(false)
    expect(localStorage.length).toBe(0)
  })
  it('expires the session on 401 without retrying a POST', async () => {
    const expired = vi.fn()
    window.addEventListener('session-expired', expired)
    vi.mocked(fetch).mockResolvedValue(new Response('{}', { status: 401 }))
    await expect(request('/groups', json('POST', {}))).rejects.toMatchObject({ status: 401 })
    expect(expired).toHaveBeenCalledOnce()
    expect(fetch).toHaveBeenCalledOnce()
    window.removeEventListener('session-expired', expired)
  })
  it('does not treat invalid credentials as session expiration', async () => {
    vi.mocked(fetch).mockResolvedValue(new Response('{}', { status: 401 }))
    await expect(request('/auth/login', json('POST', {}))).rejects.toThrow('Неверный логин или пароль')
  })
  it('redacts raw 500 details and carries request ID', async () => {
    vi.mocked(fetch).mockResolvedValue(new Response('{"detail":"postgresql://secret","error":{"message":"internal","request_id":"request-1"}}', { status: 500 }))
    await expect(request('/groups')).rejects.toMatchObject({ status: 500, requestId: 'request-1', message: 'Сервис временно недоступен. Повторите попытку позже.' })
  })
  it('preserves public nested validation and import conflict details', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: 'validation_error', message: 'Повреждённый файл', request_id: 'r1' } }), { status: 422 }))
    await expect(request('/recognition/uploads')).rejects.toMatchObject({ message: 'Повреждённый файл', code: 'validation_error', requestId: 'r1' })
    vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: 'conflict', message: { message: 'Импорт не применён', errors: ['Строка 4: пересечение'] } } }), { status: 409 }))
    await expect(request('/schedule/import')).rejects.toThrow('Импорт не применён\nСтрока 4: пересечение')
  })
  it('sends an idempotency key and linked IDs without forcing a multipart content type', async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({ provenance: 'server_inference', job: { result: null } })))
    await api.uploadRecognition({ file: new File(['test'], 'test.png'), sample_rate_fps: 1, confidence_threshold: .35, idempotency_key: 'logical-submission', session_id: 42, measurement_id: 7 })
    const init = vi.mocked(fetch).mock.calls[0][1]!
    expect(new Headers(init.headers).get('Idempotency-Key')).toBe('logical-submission')
    expect(new Headers(init.headers).has('Content-Type')).toBe(false)
    expect((init.body as FormData).get('session_id')).toBe('42')
    expect((init.body as FormData).get('measurement_id')).toBe('7')
  })
})
