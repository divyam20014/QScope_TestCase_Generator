const BASE_URL = '/api'

class ApiError extends Error {
  status: number
  /** The raw `detail` field from the error response, before it was coerced
   * to a display string - e.g. `{retry_after_seconds: 12.5}` for a 429. */
  detail: unknown
  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

// FastAPI's `detail` is usually a string, but some endpoints raise
// HTTPException(detail={"message": ..., "retry_after_seconds": ...}) for a
// 429 - an object. Passing an object straight to `Error(message)` silently
// stringifies it to the useless literal "[object Object]", so detail must
// always be reduced to a real string before it reaches ApiError/Error.
function detailToMessage(detail: unknown, fallback: string): string {
  if (typeof detail === 'string' && detail) return detail
  if (detail && typeof detail === 'object' && 'message' in detail && typeof (detail as { message: unknown }).message === 'string') {
    return (detail as { message: string }).message
  }
  if (detail && typeof detail === 'object') {
    try {
      return JSON.stringify(detail)
    } catch {
      return fallback
    }
  }
  return fallback
}

async function readErrorAndThrow(res: Response): Promise<never> {
  let detail: unknown = undefined
  try {
    const body = await res.json()
    detail = body.detail
  } catch {
    // ignore non-JSON error bodies
  }
  throw new ApiError(res.status, detailToMessage(detail, res.statusText), detail)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) await readErrorAndThrow(res)
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

async function upload<T>(path: string, formData: FormData): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, { method: 'POST', body: formData })
  if (!res.ok) await readErrorAndThrow(res)
  return (await res.json()) as T
}

async function downloadBlob(path: string): Promise<Blob> {
  const res = await fetch(`${BASE_URL}${path}`)
  if (!res.ok) await readErrorAndThrow(res)
  return res.blob()
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  upload: <T>(path: string, formData: FormData) => upload<T>(path, formData),
  downloadBlob,
}

export { ApiError }
