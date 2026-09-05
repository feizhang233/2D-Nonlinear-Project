import type {
  AnalysisRecord,
  AnalysisRestart,
  ModelInput,
  RunOptions,
  SavedModel,
  SessionResponse,
  SurfaceMeshResponse,
} from './domain'
import type { MathCoreCatalog, MathCoreRequest, MathCoreResponse } from './mathCore'

const configuredBase = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? ''

export class StudioApiError extends Error {
  constructor(message: string, readonly code?: string, readonly details?: unknown, readonly status?: number) {
    super(message)
  }
}

async function request<T>(path: string, init: RequestInit, empty = false): Promise<T> {
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

const requestJson = <T>(path: string, init: RequestInit) => request<T>(path, init)
const requestVoid = (path: string, init: RequestInit) => request<void>(path, init, true)

export function getSession(signal?: AbortSignal) {
  return requestJson<SessionResponse>('/api/v1/auth/session', { method: 'GET', signal })
}

export function registerAccount(
  payload: { email: string; display_name: string; password: string },
  signal?: AbortSignal,
) {
  return requestJson<SessionResponse>('/api/v1/auth/register', {
    method: 'POST', body: JSON.stringify(payload), signal,
  })
}

export function loginAccount(payload: { email: string; password: string }, signal?: AbortSignal) {
  return requestJson<SessionResponse>('/api/v1/auth/login', {
    method: 'POST', body: JSON.stringify(payload), signal,
  })
}

export function logoutAccount(signal?: AbortSignal) {
  return requestVoid('/api/v1/auth/logout', { method: 'POST', signal })
}

export function listSavedModels(signal?: AbortSignal) {
  return requestJson<SavedModel[]>('/api/v1/models', { method: 'GET', signal })
}

export function saveModelSnapshot(model: ModelInput, name: string, signal?: AbortSignal) {
  return requestJson<SavedModel>('/api/v1/models', {
    method: 'POST', body: JSON.stringify({ name, model }), signal,
  })
}

export function deleteSavedModel(entryId: string, signal?: AbortSignal) {
  return requestVoid(`/api/v1/models/${encodeURIComponent(entryId)}`, { method: 'DELETE', signal })
}

export function validateModel(model: ModelInput, signal?: AbortSignal) {
  return requestJson<{ valid: boolean; execution_eligible: boolean; model?: ModelInput; dof_count?: number; errors?: Array<{ json_path: string; message: string }>; limit_error?: { code: string; message: string } }>(
    '/api/v1/models/validate',
    { method: 'POST', body: JSON.stringify(model), signal },
  )
}

export function generateSurfaceMesh(model: ModelInput, meshSize: number, signal?: AbortSignal) {
  return requestJson<SurfaceMeshResponse>('/api/v1/meshes', {
    method: 'POST',
    body: JSON.stringify({ model, mesh_size: meshSize }),
    signal,
  })
}

export function runAnalysis(model: ModelInput, runOptions: RunOptions, restart: AnalysisRestart | null, signal?: AbortSignal) {
  const control = model.analysis.control_method
  return requestJson<AnalysisRecord>('/api/v1/analyses', {
    method: 'POST',
    body: JSON.stringify({
      model,
      execution_mode: 'asynchronous',
      ...(restart ? { restart } : {}),
      ...(control === 'load'
        ? { target_load_factor: runOptions.targetLoadFactor }
        : { number_of_steps: runOptions.numberOfSteps }),
    }),
    signal,
  })
}

export function getAnalysis(analysisId: string, signal?: AbortSignal) {
  return requestJson<AnalysisRecord>(`/api/v1/analyses/${encodeURIComponent(analysisId)}`, { method: 'GET', signal })
}

export function cancelAnalysis(analysisId: string, signal?: AbortSignal) {
  return requestJson<AnalysisRecord>(`/api/v1/analyses/${encodeURIComponent(analysisId)}`, { method: 'DELETE', signal })
}

export function listMathCores(signal?: AbortSignal) {
  return requestJson<MathCoreCatalog>('/api/v1/math-cores', { method: 'GET', signal })
}

export function executeMathCore(payload: MathCoreRequest, signal?: AbortSignal) {
  return requestJson<MathCoreResponse>('/api/v1/math-cores/execute', {
    method: 'POST', body: JSON.stringify(payload), signal,
  })
}
