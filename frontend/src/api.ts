import type { JsonRoutes } from './generated/api'
import { requestJson, requestVoid } from './api/transport'
export { StudioApiError } from './api/transport'
export { solveSpatialFrame, solveContinuum3D, validateContinuum3D, solvePlate3D, validatePlate3D, solveShell3D, validateShell3D } from './api/spatial'
import type { ProjectDocument, WorkspaceArchive } from './projectFiles'
import type {
  AnalysisRecord,
  AnalysisRestart,
  ModelInput,
  ModelValidationResponse,
  RunOptions,
  SavedModel,
  SessionResponse,
  SurfaceMeshResponse,
} from './domain'
import type { MathCoreCatalog, MathCoreRequest, MathCoreResponse } from './mathCore'

export function getSession(signal?: AbortSignal) {
  return requestJson<SessionResponse>('/api/v1/auth/session', { method: 'GET', signal })
}

export function registerAccount(
  payload: JsonRoutes['POST /api/v1/auth/register']['request'],
  signal?: AbortSignal,
) {
  return requestJson<SessionResponse>('/api/v1/auth/register', {
    method: 'POST', body: JSON.stringify(payload satisfies JsonRoutes['POST /api/v1/auth/register']['request']), signal,
  })
}

export function loginAccount(payload: JsonRoutes['POST /api/v1/auth/login']['request'], signal?: AbortSignal) {
  return requestJson<SessionResponse>('/api/v1/auth/login', {
    method: 'POST', body: JSON.stringify(payload satisfies JsonRoutes['POST /api/v1/auth/login']['request']), signal,
  })
}

export function logoutAccount(signal?: AbortSignal) {
  return requestVoid('/api/v1/auth/logout', { method: 'POST', signal })
}

export function listSavedModels(signal?: AbortSignal) {
  return requestJson<SavedModel[]>('/api/v1/models', { method: 'GET', signal })
}

export function saveModelSnapshot(model: ModelInput, name: string, signal?: AbortSignal, workspace?: WorkspaceArchive) {
  return requestJson<SavedModel>('/api/v1/models', {
    method: 'POST', body: JSON.stringify({ name, model, ...(workspace ? { workspace } : {}) } satisfies JsonRoutes['POST /api/v1/models']['request']), signal,
  })
}

export function deleteSavedModel(entryId: string, signal?: AbortSignal) {
  return requestVoid(`/api/v1/models/${encodeURIComponent(entryId)}`, { method: 'DELETE', signal })
}

export function validateModel(model: ModelInput, signal?: AbortSignal) {
  return requestJson<ModelValidationResponse>(
    '/api/v1/models/validate',
    { method: 'POST', body: JSON.stringify(model), signal },
  )
}

export function generateSurfaceMesh(model: ModelInput, meshSize: number, signal?: AbortSignal) {
  return requestJson<SurfaceMeshResponse>('/api/v1/meshes', {
    method: 'POST',
    body: JSON.stringify({ model, mesh_size: meshSize } satisfies JsonRoutes['POST /api/v1/meshes']['request']),
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
    } satisfies JsonRoutes['POST /api/v1/analyses']['request']),
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
    method: 'POST', body: JSON.stringify(payload satisfies JsonRoutes['POST /api/v1/math-cores/execute']['request']), signal,
  })
}

export function validateProject(project: ProjectDocument, signal?: AbortSignal) {
  return requestJson<ProjectDocument>('/api/v1/projects/validate', { method: 'POST', body: JSON.stringify(project satisfies JsonRoutes['POST /api/v1/projects/validate']['request']), signal })
}
