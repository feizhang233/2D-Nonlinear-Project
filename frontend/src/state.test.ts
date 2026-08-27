import { describe, expect, it } from 'vitest'
import type { AnalysisRecord } from './domain'
import { activeWorkspace, editingModel, initialStudioState, studioReducer, workspaceHasDraft } from './state'

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
  it('keeps results while edits are staged and invalidates them only after Apply', () => {
    let state = initialStudioState()
    state = studioReducer(state, { type: 'analysisSucceeded', family: 'frame', record, revision: 0 })
    expect(activeWorkspace(state).record).toBe(record)
    const changed = structuredClone(activeWorkspace(state).model)
    changed.nodes[1].coordinates[1] = 0.25
    state = studioReducer(state, { type: 'modelDraftChanged', model: changed })
    expect(activeWorkspace(state).record).toBe(record)
    expect(activeWorkspace(state).modelRevision).toBe(0)
    expect(workspaceHasDraft(activeWorkspace(state))).toBe(true)
    state = studioReducer(state, { type: 'draftApplied' })
    expect(activeWorkspace(state).record).toBeNull()
    expect(activeWorkspace(state).resultInvalidated).toBe(true)
    expect(activeWorkspace(state).modelRevision).toBe(1)
    expect(editingModel(activeWorkspace(state)).nodes[1].coordinates[1]).toBe(0.25)
  })

  it('ignores a late response from an older model revision', () => {
    let state = initialStudioState()
    state = studioReducer(state, { type: 'modelDraftChanged', model: structuredClone(activeWorkspace(state).model) })
    state = studioReducer(state, { type: 'draftApplied' })
    state = studioReducer(state, { type: 'analysisSucceeded', family: 'frame', record, revision: 0 })
    expect(activeWorkspace(state).record).toBeNull()
    expect(activeWorkspace(state).modelRevision).toBe(1)
  })

  it('cancels staged edits without changing the committed model', () => {
    let state = initialStudioState()
    const changed = structuredClone(activeWorkspace(state).model)
    changed.name = 'Draft name'
    state = studioReducer(state, { type: 'modelDraftChanged', model: changed })
    expect(editingModel(activeWorkspace(state)).name).toBe('Draft name')
    state = studioReducer(state, { type: 'draftCancelled' })
    expect(editingModel(activeWorkspace(state)).name).toBe('Shallow arch limit-point demo')
    expect(activeWorkspace(state).modelRevision).toBe(0)
  })

  it('preserves independent documents when switching workspaces', () => {
    let state = initialStudioState()
    const changed = structuredClone(activeWorkspace(state).model)
    changed.name = 'Frame workspace draft'
    state = studioReducer(state, { type: 'modelDraftChanged', model: changed })
    state = studioReducer(state, { type: 'draftApplied' })
    state = studioReducer(state, { type: 'workspaceChanged', family: 'continuum' })
    expect(activeWorkspace(state).model.model_family).toBe('continuum')
    state = studioReducer(state, { type: 'workspaceChanged', family: 'frame' })
    expect(activeWorkspace(state).model.name).toBe('Frame workspace draft')
  })
})
