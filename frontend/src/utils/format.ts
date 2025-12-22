export function formatNumber(num?: number) {
  if (num === undefined || num === null || Number.isNaN(num)) return '-'
  return Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(num)
}

export function truncate(text: string, length = 24) {
  return text.length > length ? `${text.slice(0, length)}…` : text
}
