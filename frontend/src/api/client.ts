import { toast } from 'sonner'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const BASE_URL = API_URL.replace(/\/$/, '')

export type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'

export type RequestOptions = {
  method?: HttpMethod
  path: string
  body?: any
  params?: Record<string, any>
  headers?: Record<string, string>
  isMultipart?: boolean
}

function buildUrl(path: string, params?: Record<string, any>) {
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

export async function apiRequest<T>({ method = 'GET', path, body, params, headers = {}, isMultipart }: RequestOptions): Promise<T> {
  const token = getToken()
  const url = buildUrl(path.startsWith('/api') ? path.replace('/api', '') : path, params)
  const finalHeaders: Record<string, string> = {
    ...(isMultipart ? {} : { 'Content-Type': 'application/json' }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...headers,
  }
  const response = await fetch(url, {
    method,
    headers: finalHeaders,
    body: body ? (isMultipart ? body : JSON.stringify(body)) : undefined,
  })

  if (response.status === 401) {
    localStorage.removeItem('token')
    toast.error('Session expired, please log in again')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || 'Request failed')
  }

  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    return (await response.json()) as T
  }
  // fallback text
  return (await response.text()) as T
}
