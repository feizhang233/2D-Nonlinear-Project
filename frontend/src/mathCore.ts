export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue }

export interface MathCoreOperationSpec {
  name: string
  summary: string
  required_parameters: string[]
  optional_parameters: string[]
  example_parameters: Record<string, JsonValue>
}

export interface MathCoreMetadata {
  core_id: string
  title: string
  version: string
  source_path: string
  scope: string
  residual_convention: string
  state_protocol: string
  verification_ids: string[]
  verification_meaning: string
  limitations: string[]
  operations: MathCoreOperationSpec[]
}

export interface MathCoreCatalog {
  schema_version: '1.0.0'
  adapter_version: string
  limits: {
    max_parameter_values: number
    max_parameter_depth: number
  }
  cores: MathCoreMetadata[]
}

export interface MathCoreRequest {
  schema_version?: '1.0.0'
  request_id?: string
  core: string
  operation: string
  parameters: Record<string, JsonValue>
}

export interface MathCoreResponse {
  schema_version: '1.0.0'
  request_id: string | null
  core: string
  operation: string
  status: 'ok' | 'error'
  data: JsonValue | null
  diagnostics: Record<string, JsonValue>
  error: { code: string; message: string; details: Record<string, JsonValue> } | null
}
