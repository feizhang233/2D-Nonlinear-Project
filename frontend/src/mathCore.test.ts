import { describe, expect, it } from 'vitest'
import { validateMathCoreParameters, type MathCoreOperationSpec } from './mathCore'
const operation: MathCoreOperationSpec = { name: 'example', summary: '', required_parameters: ['matrix'], optional_parameters: ['tolerance'], example_parameters: { matrix: [[1]] } }
const limits = { max_parameter_values: 4, max_parameter_depth: 3 }
describe('server-owned Math Core parameter validation', () => {
  it('uses required and optional names and rejects non-finite JSON numbers', () => {
    expect(validateMathCoreParameters({ matrix: [[1]], tolerance: 1e-8 }, operation, limits)).toBeNull()
    expect(validateMathCoreParameters({}, operation, limits)).toContain('Missing required')
    expect(validateMathCoreParameters({ matrix: [[1]], typo: 1 }, operation, limits)).toContain('Unsupported')
    expect(validateMathCoreParameters(JSON.parse('{"matrix": [1e999]}'), operation, limits)).toContain('finite')
  })
  it('matches server depth and scalar-count boundaries', () => {
    expect(validateMathCoreParameters({ matrix: [[1, 2], [3, 4]] }, operation, limits)).toBeNull()
    expect(validateMathCoreParameters({ matrix: [[1, 2], [3, 4]], tolerance: 1 }, operation, limits)).toContain('at most 4 values')
    expect(validateMathCoreParameters({ matrix: [[[1]]] }, operation, limits)).toContain('at most 3 levels')
  })
})
