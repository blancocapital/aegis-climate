export function formatDate(value?: string | number | Date) {
  if (!value) return '-'
  const d = typeof value === 'string' || typeof value === 'number' ? new Date(value) : value
  return d.toLocaleString()
}
