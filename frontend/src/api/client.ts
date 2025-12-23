import { toast } from 'sonner'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const BASE_URL = API_URL.replace(/\/$/, '')

export type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'

type QueryParamValue = string | number | boolean | null | undefined

export type RequestOptions = {
  method?: HttpMethod
  path: string
  body?: unknown
  params?: Record<string, QueryParamValue>
  headers?: Record<string, string>
  isMultipart?: boolean
}

function buildUrl(path: string, params?: Record<string, QueryParamValue>) {
  const url = new URL(path.startsWith('http') ? path : `${BASE_URL}${path}`)
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '') return
      url.searchParams.set(key, String(value))
    })
  }
  return url.toString()
}

export function getToken() {
  return localStorage.getItem('token')
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

async function readErrorMessage(response: Response) {
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    const data = (await response.json()) as unknown
    if (typeof data === 'string') return data
    if (isRecord(data)) {
      const detail = data.detail
      if (Array.isArray(detail)) {
        return detail
          .map((item) => {
            if (isRecord(item) && 'msg' in item) {
              return String(item.msg ?? item)
            }
            return String(item)
          })
          .join(', ')
      }
      if (detail !== undefined) return String(detail)
    }
    return JSON.stringify(data)
  }
  return await response.text()
}

export async function apiRequest<T>({ method = 'GET', path, body, params, headers = {}, isMultipart }: RequestOptions): Promise<T> {
  const token = getToken()
  const url = buildUrl(path.startsWith('/api') ? path.replace('/api', '') : path, params)
  const finalHeaders: Record<string, string> = {
    ...(isMultipart ? {} : { 'Content-Type': 'application/json' }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...headers,
  }
  const payload = body ? (isMultipart ? (body as BodyInit) : JSON.stringify(body)) : undefined
  const response = await fetch(url, {
    method,
    headers: finalHeaders,
    body: payload,
  })

  if (response.status === 401) {
    localStorage.removeItem('token')
    toast.error('Session expired, please log in again')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }

  if (!response.ok) {
    const message = await readErrorMessage(response)
    throw new Error(message || 'Request failed')
  }

  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    return (await response.json()) as T
  }
  // fallback text
  return (await response.text()) as T
}

type ApiErrorPayload = {
  request_id?: string
  code?: string
  message?: string
  details?: unknown
}

type ApiError = Error & {
  requestId?: string
  code?: string
  details?: unknown
  status?: number
}

export async function apiRequestWithMeta<T>({
  method = 'GET',
  path,
  body,
  params,
  headers = {},
  isMultipart,
}: RequestOptions): Promise<{ data: T; requestId?: string }> {
  const token = getToken()
  const url = buildUrl(path.startsWith('/api') ? path.replace('/api', '') : path, params)
  const finalHeaders: Record<string, string> = {
    ...(isMultipart ? {} : { 'Content-Type': 'application/json' }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...headers,
  }
  const payload = body ? (isMultipart ? (body as BodyInit) : JSON.stringify(body)) : undefined
  const response = await fetch(url, {
    method,
    headers: finalHeaders,
    body: payload,
  })

  const requestId = response.headers.get('X-Request-ID') || undefined

  if (response.status === 401) {
    localStorage.removeItem('token')
    toast.error('Session expired, please log in again')
    window.location.href = '/login'
    const err = new Error('Unauthorized') as ApiError
    err.requestId = requestId
    throw err
  }

  if (!response.ok) {
    const contentType = response.headers.get('content-type') || ''
    let payload: ApiErrorPayload | undefined
    let message = ''
    if (contentType.includes('application/json')) {
      try {
        payload = (await response.clone().json()) as ApiErrorPayload
        message = payload?.message || ''
      } catch (err) {
        payload = undefined
      }
    }
    if (!message) {
      message = payload ? JSON.stringify(payload) : await readErrorMessage(response)
    }
    const err = new Error(message || 'Request failed') as ApiError
    err.requestId = payload?.request_id || requestId
    err.code = payload?.code
    err.details = payload?.details
    err.status = response.status
    throw err
  }

  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    return { data: (await response.json()) as T, requestId }
  }
  return { data: (await response.text()) as T, requestId }
}
