import type { ApiSchemas } from './generated/api'
import type { JsonValue } from './domain'
import { hasNonFiniteNumber } from './inputValidation'
export type { JsonValue } from './domain'

export type MathCoreOperationSpec = Required<ApiSchemas['MathCoreOperationSpec']>

export type MathCoreMetadata = Omit<ApiSchemas['MathCoreMetadata'], 'operations'> & { operations: MathCoreOperationSpec[] }

export type MathCoreCatalog = Omit<Required<ApiSchemas['MathCoreCatalog']>, 'cores' | 'limits'> & { cores: MathCoreMetadata[]; limits: Required<ApiSchemas['MathCoreLimits']> }

export type MathCoreRequest = ApiSchemas['MathCoreRequest']

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

export type MathCoreResponse = Omit<Required<ApiSchemas['MathCoreResponse']>, 'error'> & { error: Required<ApiSchemas['MathCoreExecutionError']> | null }
