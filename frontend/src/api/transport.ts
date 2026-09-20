import type { JsonRoutes } from '../generated/api'

type ConcretePath<S extends string> = S extends `${infer Head}{${string}}${infer Tail}`
  ? `${Head}${string}${ConcretePath<Tail>}` : S
type JsonPath = {
  [K in keyof JsonRoutes]: K extends `${string} ${infer Path}` ? ConcretePath<Path> : never
}[keyof JsonRoutes]

const configuredBase = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? ''

export class StudioApiError extends Error {
  constructor(message: string, readonly code?: string, readonly details?: unknown, readonly status?: number) {
    super(message)
  }
}

async function request<T>(path: JsonPath, init: RequestInit, empty = false): Promise<T> {
  const controller = new AbortController()
  const forwardAbort = () => controller.abort()
  if (init.signal?.aborted) controller.abort()
  init.signal?.addEventListener('abort', forwardAbort, { once: true })
  let timedOut = false
  const timer = setTimeout(() => { timedOut = true; controller.abort() }, path === '/api/v1/meshes' ? 120_000 : 30_000)
  try {
    const response = await fetch(`${configuredBase}${path}`, {
      ...init,
      signal: controller.signal,
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', ...init.headers },
    })
    if (empty && response.ok) return undefined as T
    const payload = await response.json().catch(() => null) as Record<string, unknown> | null
    if (!response.ok) {
      const detail = payload?.error as { message?: string; code?: string; details?: { errors?: Array<{ location?: string; message?: string }> }; location?: string } | undefined
      const first = detail?.details?.errors?.[0]
      const message = first?.message
        ? `${first.location ?? detail?.location ?? 'Input'}: ${first.message}`
        : detail?.message ?? `Request failed (HTTP ${response.status})`
      throw new StudioApiError(message, detail?.code, detail?.details, response.status)
    }
    if (payload === null || typeof payload !== 'object') {
      throw new StudioApiError('The server returned an invalid JSON response. Check the API connection and retry.', 'INVALID_API_RESPONSE', undefined, response.status)
    }
    return payload as T
  } catch (error) {
    if (timedOut) throw new StudioApiError('The API request timed out. Server completion is unknown; check the connection before retrying.', 'REQUEST_TIMEOUT')
    if (controller.signal.aborted) throw new DOMException('Request aborted', 'AbortError')
    if (error instanceof TypeError) throw new StudioApiError('Cannot reach the API. Check the connection and retry.', 'NETWORK_ERROR')
    throw error
  } finally {
    clearTimeout(timer)
    init.signal?.removeEventListener('abort', forwardAbort)
  }
}

export const requestJson = <T>(path: JsonPath, init: RequestInit) => request<T>(path, init)
export const requestVoid = (path: JsonPath, init: RequestInit) => request<void>(path, init, true)

type PostPath = {
  [K in keyof JsonRoutes]: K extends `POST ${infer Path}` ? Path : never
}[keyof JsonRoutes]

/** Path, request and response must belong to the same generated HTTP operation. */
export function postJson<P extends PostPath>(
  path: P, payload: JsonRoutes[`POST ${P}`]['request'], signal?: AbortSignal,
): Promise<JsonRoutes[`POST ${P}`]['response']> {
  return requestJson(path, { method: 'POST', body: JSON.stringify(payload), signal })
}
