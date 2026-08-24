export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue }
export type ModelFamily = 'frame' | 'continuum' | 'plate' | 'shell'
export type Dof = 'UX' | 'UY' | 'UZ' | 'RX' | 'RY' | 'RZ'
export type ControlMethod = 'load' | 'displacement' | 'arc_length'

export interface NodeInput {
  id: string
  coordinates: number[]
  extensions?: Record<string, JsonValue>
}

export interface MaterialInput {
  id: string
  model: string
  parameters: Record<string, JsonValue>
  extensions?: Record<string, JsonValue>
}

export interface ElementInput {
  id: string
  formulation: string
  node_ids: string[]
  material_id: string
  properties: Record<string, JsonValue>
  extensions?: Record<string, JsonValue>
}

export interface LoadInput {
  id: string
  kind: 'nodal' | 'element' | 'body' | 'edge' | 'surface'
  components: Record<string, number>
  node_id?: string | null
  element_id?: string | null
  coordinate_system?: 'global' | 'local'
  pattern?: string
  scale?: number
  extensions?: Record<string, JsonValue>
}

export interface ConstraintInput {
  id: string
  node_id: string
  dof: Dof
  value?: number
  extensions?: Record<string, JsonValue>
}

export interface AnalysisOptions {
  control_method: ControlMethod
  newton_method: 'full' | 'modified'
  max_iterations: number
  tolerances: {
    residual: number
    displacement: number
    energy: number
    linear_solver: number
    force_floor: number
    displacement_floor: number
    energy_floor: number
  }
  step_control: {
    initial_step: number
    min_step: number
    max_step: number
    max_steps: number
    max_retries: number
    target_iterations: number
    cutback_factor: number
    growth_factor: number
  }
  line_search: {
    enabled: boolean
    method: 'backtracking' | 'orthogonality'
    max_iterations: number
    min_alpha: number
    reduction_factor: number
  }
  displacement_control?: {
    target: { node_id: string; dof: Dof }
    increment: number
  }
  arc_length?: {
    radius: number
    min_radius: number
    max_radius: number
    beta: number
    root_selection: 'direction_continuity'
  }
  extensions?: Record<string, JsonValue>
}

export interface ModelInput {
  schema_version: '1.0.0'
  model_id: string
  name: string
  model_family: ModelFamily
  units: {
    length: string
    force: string
    stress: string
    angle: string
    system_label?: string
  }
  nodes: NodeInput[]
  elements: ElementInput[]
  materials: MaterialInput[]
  loads: LoadInput[]
  constraints: ConstraintInput[]
  analysis: AnalysisOptions
  extensions?: Record<string, JsonValue>
}

export interface MeshBoundarySegment {
  element_id: string
  local_edge: number
  node_ids: [string, string]
}

export interface MeshBoundary {
  id: string
  label: string
  node_ids: string[]
  segments: MeshBoundarySegment[]
  length: number
}

export interface SurfaceMeshResponse {
  engine: 'Gmsh'
  engine_version: string
  model_family: ModelFamily
  formulation: string
  mesh_size: number
  nodes: NodeInput[]
  elements: ElementInput[]
  boundaries: MeshBoundary[]
}

export interface IterationRecord {
  step_index: number
  iteration_index: number
  load_factor: number
  residual_norm: number
  displacement_correction_norm: number
  energy_norm: number
  linear_residual_norm: number
  accepted_alpha: number
  tangent_reassembled: boolean
  status: 'continue' | 'converged' | 'rejected'
  diagnostics: Record<string, JsonValue>
}

export interface FailureRecord {
  code: string
  message: string
  json_path?: string | null
  step_index?: number | null
  iteration_index?: number | null
  details: Record<string, JsonValue>
}

export interface StepResult {
  step_index: number
  status: 'accepted' | 'rejected'
  control_method: ControlMethod
  load_factor: number
  requested_step_size: number
  accepted_step_size?: number | null
  state_id?: string | null
  iterations: IterationRecord[]
  failure?: FailureRecord | null
  response: Record<string, JsonValue>
}

export interface ResultField {
  name: string
  location: 'global' | 'node' | 'element' | 'gauss_point'
  basis?: string | null
  records: Array<Record<string, JsonValue>>
  is_derived: boolean
  source?: string | null
}

export interface SolveResult {
  schema_version: '1.0.0'
  model_id: string
  model_sha256: string
  solver_version: string
  status: 'succeeded' | 'failed'
  steps: StepResult[]
  failures: FailureRecord[]
  post_result?: {
    raw_fields: ResultField[]
    derived_fields: ResultField[]
    metadata: Record<string, JsonValue>
  } | null
  metadata: Record<string, JsonValue>
}

export interface AnalysisRestart {
  restart_schema_version: '1.0.0'
  committed_state: Record<string, JsonValue>
  arc_length_increment?: Record<string, JsonValue> | null
}

export interface RestartBundle {
  restart_bundle_schema_version: '1.0.0'
  model: ModelInput
  restart: AnalysisRestart
}

export interface ApiErrorDetail {
  category: 'input' | 'computation' | 'server'
  code: string
  message: string
  location?: string | null
  details: Record<string, JsonValue>
}

export interface AnalysisRecord {
  analysis_id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
  execution_mode: 'synchronous' | 'asynchronous'
  created_at: string
  started_at?: string | null
  completed_at?: string | null
  model_id: string
  model_sha256: string
  control_method: ControlMethod
  dof_count: number
  progress: {
    current_step?: number | null
    current_iteration?: number | null
    accepted_steps: number
    message: string
  }
  result?: SolveResult | null
  error?: ApiErrorDetail | null
}

export type EntityKind = 'model' | 'nodes' | 'elements' | 'materials' | 'constraints' | 'loads'
export type SelectionKind = EntityKind | 'mesh'
export interface Selection { kind: SelectionKind; id?: string }
export type ResultView = 'model' | 'deformation' | 'reactions' | 'internal'
export type ResultTab = 'monitor' | 'curves' | 'tables' | 'failure'

export interface RunOptions {
  targetLoadFactor: number
  numberOfSteps: number
}

export interface AuthUser {
  id: string
  email: string
  display_name: string
  created_at: string
}

export interface SessionResponse {
  authenticated: boolean
  user: AuthUser | null
}

export interface SavedModel {
  id: string
  name: string
  model_family: ModelFamily
  saved_at: string
  model: ModelInput
}
