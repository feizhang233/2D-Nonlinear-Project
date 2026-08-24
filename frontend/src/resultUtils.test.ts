import { describe, expect, it } from 'vitest'
import { cloneSampleModel } from './sampleModel'
import { displacementByNode, elementResultSummary, failureSuggestion, loadDisplacementPoints } from './resultUtils'
import type { SolveResult } from './domain'

const result: SolveResult = {
  schema_version: '1.0.0', model_id: 'test', model_sha256: 'b'.repeat(64), solver_version: 'test', status: 'succeeded', failures: [], metadata: {},
  steps: [{ step_index: 0, status: 'accepted', control_method: 'load', load_factor: 0.1, requested_step_size: 0.1, accepted_step_size: 0.1, state_id: 'state', iterations: [], response: { displacement: [0, 0, 0, 0, -0.02, 0, 0, 0, 0] } }],
  post_result: { raw_fields: [{ name: 'displacement', location: 'node', basis: 'global-dof-order', is_derived: false, records: [{ dof_index: 4, node_id: 'N2', dof: 'UY', value: -0.02 }] }], derived_fields: [], metadata: {} },
}

describe('result extraction', () => {
  it('maps global DOF recovery to model nodes', () => {
    expect(displacementByNode(cloneSampleModel(), result).get('N2')?.UY).toBe(-0.02)
  })

  it('builds a load-displacement point without re-solving anything', () => {
    expect(loadDisplacementPoints(cloneSampleModel(), result)).toEqual([{ x: -0.02, y: 0.1 }])
  })

  it('offers a bounded diagnostic suggestion for nonconvergence', () => {
    expect(failureSuggestion('NONCONVERGENCE')).toContain('Reduce the step size')
  })

  it('extracts family-specific element recovery without treating Q4 data as Frame end forces', () => {
    expect(elementResultSummary('continuum', {
      element_id: 'E1', energy: 4,
      gauss_points: [{ cauchy: [10, 20, 3, 5] }, { cauchy: [14, 24, 5, 7] }],
    }).metrics).toEqual([12, 22, 4])
    expect(elementResultSummary('plate', {
      element_id: 'E1', energy: 2,
      gauss_points: [{ membrane_resultant: [3, 4, 0], bending_moment: [0, 0, 2], shear_force: [6, 8] }],
    }).metrics).toEqual([5, 2, 10])
    expect(elementResultSummary('shell', {
      element_id: 'E1', energy: 3,
      gauss_points: [{ membrane_resultant: [0, 0, 1], bending_resultant: [0, 3, 4], shear_resultant: [0, 2] }],
    }).metrics).toEqual([1, 5, 2])
  })
})
