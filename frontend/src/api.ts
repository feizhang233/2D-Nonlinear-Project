import type {
  AnalysisRecord,
  AnalysisRestart,
  ModelInput,
  RunOptions,
  SavedModel,
  SessionResponse,
  SurfaceMeshResponse,
} from './domain'

const configuredBase = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? ''

export class StudioApiError extends Error {
  constructor(message: string, readonly code?: string, readonly details?: unknown, readonly status?: number) {
    super(message)
  }
}

async function requestJson<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${configuredBase}${path}`, {
    ...init,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...init.headers },
  })
  const payload = await response.json().catch(() => null) as Record<string, unknown> | null
  if (!response.ok) {
    const detail = payload?.error as { message?: string; code?: string; details?: unknown } | undefined
    throw new StudioApiError(
      detail?.message ?? `Request failed (HTTP ${response.status})`,
      detail?.code,
      detail?.details,
      response.status,
    )
  }
  return payload as T
}

async function requestVoid(path: string, init: RequestInit): Promise<void> {
  const response = await fetch(`${configuredBase}${path}`, {
    ...init,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...init.headers },
  })
  if (response.ok) return
  const payload = await response.json().catch(() => null) as Record<string, unknown> | null
  const detail = payload?.error as { message?: string; code?: string; details?: unknown } | undefined
  throw new StudioApiError(
    detail?.message ?? `Request failed (HTTP ${response.status})`,
    detail?.code,
    detail?.details,
    response.status,
  )
}

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
  return requestJson<{ valid: boolean; execution_eligible: boolean; dof_count?: number; errors?: Array<{ json_path: string; message: string }> }>(
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
  return requestJson<AnalysisRecord>(`/api/v1/analyses/${analysisId}`, { method: 'GET', signal })
}

export function cancelAnalysis(analysisId: string) {
  return requestJson<AnalysisRecord>(`/api/v1/analyses/${analysisId}`, { method: 'DELETE' })
}
