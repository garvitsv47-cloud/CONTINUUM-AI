export async function readJsonResponse<T>(response: Response): Promise<T> {
  const body = await response.text()
  const contentType = response.headers.get('content-type')?.toLowerCase() ?? ''

  if (!body.trim()) {
    throw new Error(`Request failed with an empty response (HTTP ${response.status}).`)
  }

  if (!contentType.includes('application/json')) {
    throw new Error(
      `Request returned an unexpected response (HTTP ${response.status}). Please try again.`,
    )
  }

  let data: unknown
  try {
    data = JSON.parse(body)
  } catch {
    throw new Error(`Request returned invalid JSON (HTTP ${response.status}). Please try again.`)
  }

  if (!response.ok) {
    const detail =
      typeof data === 'object' &&
      data !== null &&
      'detail' in data &&
      typeof data.detail === 'string'
        ? data.detail
        : `Request failed (HTTP ${response.status}).`
    throw new Error(detail)
  }

  return data as T
}

export function apiUrl(path: string): string {
  const normalizedPath = (path.startsWith('/') ? path : `/${path}`).replace(/\/+$/, '') || '/'
  return normalizedPath
}
