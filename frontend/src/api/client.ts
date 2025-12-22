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

async function readErrorMessage(response: Response) {
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    const data = await response.json()
    if (typeof data === 'string') return data
    if (data && typeof data === 'object') {
      if (Array.isArray((data as any).detail)) {
        return (data as any).detail.map((item: any) => item?.msg || item).join(', ')
      }
      if ('detail' in data) return String((data as any).detail)
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
