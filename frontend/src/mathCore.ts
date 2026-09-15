import type { JsonValue } from './domain'
import { hasNonFiniteNumber } from './inputValidation'
export type { JsonValue } from './domain'

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
  request_id?: string | null
  core: string
  operation: string
  parameters?: Record<string, JsonValue>
}

/** Validate against the server catalog, including its published resource limits. */
export function validateMathCoreParameters(
  parameters: Record<string, JsonValue>, operation: MathCoreOperationSpec, limits: MathCoreCatalog['limits'],
): string | null {
  if (hasNonFiniteNumber(parameters)) return 'Parameters must contain only finite numbers.'
  const missing = operation.required_parameters.filter(name => !Object.hasOwn(parameters, name))
  if (missing.length) return `Missing required parameters: ${missing.join(', ')}.`
  const allowed = new Set([...operation.required_parameters, ...operation.optional_parameters])
  const unknown = Object.keys(parameters).filter(name => !allowed.has(name))
  if (unknown.length) return `Unsupported parameters: ${unknown.join(', ')}.`
  let count = 0
  let tooDeep = false
  const visit = (value: JsonValue, depth: number) => {
    if (depth > limits.max_parameter_depth) { tooDeep = true; return }
    if (value !== null && typeof value === 'object') {
      Object.values(value).forEach(item => visit(item, depth + 1))
    } else count += 1
  }
  visit(parameters, 0)
  if (tooDeep) return `Parameters may be nested at most ${limits.max_parameter_depth} levels.`
  if (count > limits.max_parameter_values) return `Parameters may contain at most ${limits.max_parameter_values} values.`
  return null
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
