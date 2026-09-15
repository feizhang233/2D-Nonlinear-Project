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

describe('API transport failures', () => {
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers() })

  it('rejects successful HTML/empty responses instead of returning null', async () => {
    const { getSession } = await import('./api')
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('<html>wrong proxy</html>', { status: 200 }))
    await expect(getSession()).rejects.toMatchObject({ code: 'INVALID_API_RESPONSE' })
  })

  it('exposes the backend schema error path and correction detail', async () => {
    const { validateModel } = await import('./api')
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ error: {
      code: 'REQUEST_VALIDATION_FAILED', message: 'HTTP request failed API schema validation',
      details: { errors: [{ location: '$.mesh_size', message: 'Input should be greater than 0' }] },
    } }), { status: 422 }))
    await expect(validateModel(cloneSampleModel())).rejects.toMatchObject({ code: 'REQUEST_VALIDATION_FAILED', message: '$.mesh_size: Input should be greater than 0' })
  })

  it('bounds a stalled request and distinguishes timeout from user cancellation', async () => {
    const { getSession } = await import('./api')
    vi.useFakeTimers()
    vi.spyOn(globalThis, 'fetch').mockImplementation((_url, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
    }))
    const pending = getSession()
    const assertion = expect(pending).rejects.toMatchObject({ code: 'REQUEST_TIMEOUT' })
    await vi.advanceTimersByTimeAsync(30_000)
    await assertion
    const controller = new AbortController()
    const cancelled = getSession(controller.signal)
    controller.abort()
    await expect(cancelled).rejects.toMatchObject({ name: 'AbortError' })
  })
})

describe('analysis control payloads', () => {
  afterEach(() => vi.restoreAllMocks())
  it.each(MODEL_FAMILY_ORDER.flatMap(family => (['load', 'displacement', 'arc_length'] as const).map(control => ({ family, control }))))('sends only the $control run parameter for $family', async ({ family, control }) => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 201 }))
    const model = cloneSampleModel(family)
    model.analysis.control_method = control
    await runAnalysis(model, { targetLoadFactor: 2.5, numberOfSteps: 7 }, null)
    const payload = JSON.parse(String(fetchMock.mock.calls[0][1]?.body))
    expect(payload.model.analysis.control_method).toBe(control)
    if (control === 'load') {
      expect(payload.target_load_factor).toBe(2.5)
      expect(payload).not.toHaveProperty('number_of_steps')
    } else {
      expect(payload.number_of_steps).toBe(7)
      expect(payload).not.toHaveProperty('target_load_factor')
    }
  })
})
