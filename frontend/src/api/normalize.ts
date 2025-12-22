export function normalizeListResponse<T>(res: unknown): T[] {
  if (Array.isArray(res)) return res as T[]
  if (res && typeof res === 'object') {
    const maybeItems = (res as { items?: unknown; data?: unknown }).items ?? (res as { data?: unknown }).data
    if (Array.isArray(maybeItems)) return maybeItems as T[]
  }
  return []
}
