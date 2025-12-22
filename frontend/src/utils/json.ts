export function safeJsonParse(value: string) {
  try {
    return JSON.parse(value)
  } catch (err) {
    return null
  }
}

export function prettyJson(value: unknown) {
  try {
    return JSON.stringify(value, null, 2)
  } catch (err) {
    return ''
  }
}
