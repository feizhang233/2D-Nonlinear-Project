import { describe, expect, it } from 'vitest'
import type { AnalysisRecord } from './domain'
import { initialStudioState, studioReducer } from './state'

const record = {
  analysis_id: 'test-analysis', status: 'succeeded', execution_mode: 'asynchronous', created_at: '', model_id: 'p11-shallow-arch',
  model_sha256: 'a'.repeat(64), control_method: 'load', dof_count: 9,
  progress: { accepted_steps: 1, message: 'done' },
  result: {
    schema_version: '1.0.0', model_id: 'p11-shallow-arch', model_sha256: 'a'.repeat(64), solver_version: 'test', status: 'succeeded', failures: [], metadata: {},
    steps: [{ step_index: 0, status: 'accepted', control_method: 'load', load_factor: 0.1, requested_step_size: 0.1, accepted_step_size: 0.1, state_id: 'state', iterations: [], response: { displacement: [0, 0, 0] } }],
  },
} as AnalysisRecord

describe('studioReducer result revision safety', () => {
  it('removes current results whenever the model changes', () => {
    let state = initialStudioState()
    state = studioReducer(state, { type: 'analysisSucceeded', record, revision: 0 })
    expect(state.record).toBe(record)
    const changed = structuredClone(state.model)
    changed.nodes[1].coordinates[1] = 0.25
    state = studioReducer(state, { type: 'modelChanged', model: changed })
    expect(state.record).toBeNull()
    expect(state.resultInvalidated).toBe(true)
    expect(state.modelRevision).toBe(1)
  })

  it('ignores a late response from an older model revision', () => {
    let state = initialStudioState()
    state = studioReducer(state, { type: 'modelChanged', model: structuredClone(state.model) })
    state = studioReducer(state, { type: 'analysisSucceeded', record, revision: 0 })
    expect(state.record).toBeNull()
    expect(state.modelRevision).toBe(1)
  })
})
