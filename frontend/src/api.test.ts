import { afterEach, describe, expect, it, vi } from 'vitest'
import { runAnalysis } from './api'
import { defaultRunOptions, MODEL_FAMILY_ORDER } from './modelFamilies'
import { cloneSampleModel } from './sampleModel'

describe('analysis API family bridge', () => {
  afterEach(() => vi.restoreAllMocks())

  it.each(MODEL_FAMILY_ORDER)('submits the selected %s document without Frame coercion', async (family) => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      analysis_id: `${family}-analysis`, status: 'queued', execution_mode: 'asynchronous',
      created_at: '2026-08-20T00:00:00Z', model_id: family, model_sha256: 'a'.repeat(64),
      control_method: 'load', dof_count: 1, progress: { accepted_steps: 0, message: 'queued' },
    }), { status: 201, headers: { 'Content-Type': 'application/json' } }))

    await runAnalysis(cloneSampleModel(family), defaultRunOptions(family), null)
    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body))
    expect(body.execution_mode).toBe('asynchronous')
    expect(body.model.model_family).toBe(family)
    expect(body.model.elements[0].formulation).toBe(cloneSampleModel(family).elements[0].formulation)
  })
})
