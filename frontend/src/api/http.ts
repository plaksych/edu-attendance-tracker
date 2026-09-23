const API_BASE = '/api/v1'
let csrfToken: string | null = null

export function setCsrfToken(token: string | null) { csrfToken = token }

export class ApiError extends Error {
  constructor(public status: number, message: string, public requestId?: string, public code?: string, public fields?: { field: string; code: string }[]) {
    super(message)
    this.name = 'ApiError'
  }
}

const messages: Record<number, string> = {
  401: 'Сессия завершена. Войдите снова.',
  403: 'Недостаточно прав для этого действия.',
  404: 'Запись не найдена или больше недоступна.',
  409: 'Данные изменились. Обновите страницу перед повтором.',
  413: 'Файл превышает разрешённый размер.',
  422: 'Проверьте введённые данные и формат файла.',
  429: 'Слишком много запросов. Повторите попытку позже.',
}

export async function requestResponse(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  const method = (init.method ?? 'GET').toUpperCase()
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && csrfToken) headers.set('X-CSRF-Token', csrfToken)
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers, credentials: 'include' })
  } catch {
    throw new ApiError(0, 'Сервер недоступен. Проверьте соединение и повторите попытку.')
  }
  if (!response.ok) {
    let message = messages[response.status] ?? 'Сервис временно недоступен. Повторите попытку позже.'
    if (response.status === 401 && path === '/auth/login') message = 'Неверный логин или пароль.'
    let requestId = response.headers.get('X-Request-ID') ?? undefined
    let code: string | undefined
    let fields: { field: string; code: string }[] | undefined
    try {
      const body = await response.json()
      requestId = typeof body.error?.request_id === 'string' ? body.error.request_id : requestId
      code = typeof body.error?.code === 'string' ? body.error.code : undefined
      // Never display raw server detail/tracebacks. Only use the public error contract.
      if (response.status < 500) {
        const publicMessage = body.error?.message
        if (typeof publicMessage === 'string') message = publicMessage
        else if (publicMessage && typeof publicMessage.message === 'string') {
          const errors = Array.isArray(publicMessage.errors) ? publicMessage.errors.filter((value: unknown): value is string => typeof value === 'string') : []
          message = [publicMessage.message, ...errors].join('\n')
        }
        if (Array.isArray(body.error?.fields)) {
          fields = body.error.fields.filter((value: { field?: unknown; code?: unknown }) => typeof value.field === 'string' && typeof value.code === 'string')
          if (fields?.length) message += ` Поля: ${fields.map(value => value.field.replace(/^body\./, '')).join(', ')}.`
        }
      }
    } catch { /* The proxy may return an HTML error page. */ }
    if (response.status === 401 && path !== '/auth/login') {
      csrfToken = null
      window.dispatchEvent(new Event('session-expired'))
    }
    throw new ApiError(response.status, message, requestId, code, fields)
  }
  return response
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await requestResponse(path, init)
  if (response.status === 204) return undefined as T
  const body = await response.text()
  return body ? JSON.parse(body) as T : undefined as T
}

export function json(method: string, body: unknown): RequestInit {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
}
