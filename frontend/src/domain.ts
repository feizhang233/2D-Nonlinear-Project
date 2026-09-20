import type { ApiSchemas, WithDefaults } from './generated/api'

export type JsonValue = ApiSchemas['JsonValue']
export type ModelFamily = ApiSchemas['ModelFamily']
export type Dof = ApiSchemas['Dof']
export type ControlMethod = ApiSchemas['ControlMethod']
export type WorkflowStep = 'model' | 'materials' | 'supports' | 'loads' | 'mesh' | 'solve'

// Editor state materializes defaults needed by controls. Other wire fields stay optional.
type Materialized<T, K extends keyof T> = T & Required<Pick<T, K>>

export type NodeInput = ApiSchemas['NodeInput-Output']

export type MaterialInput = Materialized<ApiSchemas['MaterialInput'], 'parameters'>

export type ElementInput = Materialized<ApiSchemas['ElementInput-Output'], 'properties'>

export type LoadInput = ApiSchemas['LoadInput']

export type ConstraintInput = ApiSchemas['ConstraintInput']

export type AnalysisOptions = Omit<ApiSchemas['AnalysisOptions'], 'tolerances' | 'step_control' | 'line_search' | 'arc_length' | 'displacement_control'> & {
  control_method: ControlMethod
  newton_method: ApiSchemas['NewtonMethod']
  max_iterations: number
  tolerances: WithDefaults<ApiSchemas['ToleranceOptions']>
  step_control: WithDefaults<ApiSchemas['StepControlOptions']>
  line_search: WithDefaults<ApiSchemas['LineSearchOptions']>
  displacement_control?: WithDefaults<ApiSchemas['DisplacementControlOptions']> | null
  arc_length?: WithDefaults<ApiSchemas['ArcLengthOptions']> | null
}

export type ModelInput = Omit<ApiSchemas['ModelInput'], 'analysis' | 'materials' | 'elements' | 'units'> & {
  analysis: AnalysisOptions
  materials: MaterialInput[]
  elements: ElementInput[]
  loads: LoadInput[]
  constraints: ConstraintInput[]
  units: Materialized<ApiSchemas['UnitMetadata'], 'angle'>
}

export type ModelValidationResponse = Omit<ApiSchemas['ModelValidationResponse'], 'model'> & {
  model?: ModelInput | null
}

export type MeshBoundarySegment = ApiSchemas['MeshBoundarySegment']

export type MeshBoundary = ApiSchemas['MeshBoundary']

export type SurfaceMeshResponse = Omit<ApiSchemas['SurfaceMeshResponse'], 'elements'> & { engine: string; elements: ElementInput[] }

export type IterationRecord = Materialized<ApiSchemas['IterationRecord'], 'accepted_alpha' | 'diagnostics'>

export type FailureRecord = Materialized<ApiSchemas['FailureRecord'], 'details'>

export type StepResult = Omit<ApiSchemas['StepResult'], 'iterations' | 'failure'> & {
  iterations: IterationRecord[]
  failure?: FailureRecord | null
  response: Record<string, JsonValue>
}

export type ResultField = Materialized<ApiSchemas['ResultField'], 'is_derived'>

export type SolveResult = Omit<ApiSchemas['SolveResult'], 'steps' | 'failures' | 'post_result'> & {
  schema_version: '1.0.0'
  steps: StepResult[]
  failures: FailureRecord[]
  post_result?: { raw_fields: ResultField[]; derived_fields: ResultField[]; metadata: Record<string, JsonValue> } | null
  metadata: Record<string, JsonValue>
}

export type AnalysisRestart = ApiSchemas['AnalysisRestart'] & { restart_schema_version: '1.0.0' }

export interface RestartBundle {
  restart_bundle_schema_version: '1.0.0'
  model: ModelInput
  restart: AnalysisRestart
}

export type ApiErrorDetail = Materialized<ApiSchemas['ApiErrorDetail'], 'details'>

export type AnalysisRecord = Omit<ApiSchemas['AnalysisRecord'], 'progress' | 'result' | 'error'> & {
  control_method: ControlMethod
  progress: Materialized<ApiSchemas['AnalysisProgress'], 'accepted_steps' | 'message'>
  result?: SolveResult | null
  error?: ApiErrorDetail | null
}

export type EntityKind = 'model' | 'nodes' | 'elements' | 'materials' | 'constraints' | 'loads'
export type SelectionKind = EntityKind | 'mesh' | 'geometry' | 'sections'
export interface Selection { kind: SelectionKind; id?: string }
export type ResultView = 'model' | 'deformation' | 'reactions' | 'internal' | 'moment' | 'shear' | 'axial'
export type ResultTab = 'monitor' | 'curves' | 'tables' | 'failure'

export type RunOptions = Required<ApiSchemas['RunOptions']>

export type AuthUser = ApiSchemas['AuthUser']

export type SessionResponse = Required<ApiSchemas['SessionResponse']>

export type SavedModel = Omit<ApiSchemas['SavedModel'], 'model' | 'workspace'> & {
  model: ModelInput
  workspace?: import('./projectFiles').WorkspaceArchive | null
}
