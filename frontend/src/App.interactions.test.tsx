// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })
const queued = { analysis_id: 'pending-solve', status: 'queued', progress: { accepted_steps: 0, message: 'queued' } }
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((yes) => { resolve = yes })
  return { promise, resolve }
}

beforeEach(() => {
  Object.defineProperty(window, 'localStorage', { configurable: true, value: { getItem: () => 'true', setItem: vi.fn() } })
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })

function mockRequests(handler: (url: string, init?: RequestInit) => Promise<Response>) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => String(input).endsWith('/auth/session')
    ? Promise.resolve(json({ authenticated: false, user: null }))
    : handler(String(input), init))
}

describe('workbench async boundaries', () => {
  it('does not trigger Run from a text field, IME composition, or an account dialog', async () => {
    const fetch = mockRequests(async () => { throw new Error('Unexpected solve') })
    render(<App />)
    fireEvent.keyDown(screen.getByRole('textbox', { name: 'Display name' }), { key: 'Enter', ctrlKey: true })
    fireEvent.keyDown(window, { key: 'Enter', ctrlKey: true, isComposing: true })
    fireEvent.click(await screen.findByRole('button', { name: 'Guest account' }))
    fireEvent.keyDown(window, { key: 'Enter', ctrlKey: true })
    expect(fetch.mock.calls.filter(([url]) => String(url).includes('/validate'))).toHaveLength(0)
  })

  it('cancels validation without submitting a solve even if validation resolves late', async () => {
    const validation = deferred<Response>()
    const fetch = mockRequests(async () => validation.promise)
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    await act(async () => validation.resolve(json({ valid: true, execution_eligible: true })))
    expect(fetch.mock.calls.filter(([url]) => String(url).endsWith('/analyses'))).toHaveLength(0)
    expect(screen.getByRole('main', { name: 'Model editing canvas' })).toBeTruthy()
  })

  it('cancels the server job when the POST acknowledges after client cancellation', async () => {
    const submission = deferred<Response>()
    const fetch = mockRequests(async (url, init) => {
      if (url.endsWith('/validate')) return json({ valid: true, execution_eligible: true })
      if (url.endsWith('/analyses')) return submission.promise
      if (init?.method === 'DELETE') return json({ ...queued, status: 'cancelled' })
      throw new Error(`Unexpected request ${url}`)
    })
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }))
    await waitFor(() => expect(fetch.mock.calls.some(([url]) => String(url).endsWith('/analyses'))).toBe(true))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    await act(async () => submission.resolve(json(queued, 201)))
    await waitFor(() => expect(fetch.mock.calls.some(([url, init]) => String(url).endsWith('/analyses/pending-solve') && init?.method === 'DELETE')).toBe(true))
    expect(screen.queryByText('Results current')).toBeNull()
  })

  it('shows backend execution limits and avoids submitting an ineligible model', async () => {
    const fetch = mockRequests(async () => json({ valid: true, execution_eligible: false, limit_error: { code: 'DOF_LIMIT_EXCEEDED', message: 'Model exceeds the 600 DOF execution limit' } }))
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }))
    await waitFor(() => expect(screen.getAllByText(/Model exceeds the 600 DOF execution limit/).length).toBeGreaterThan(0))
    expect(screen.queryByText(/The current result has no failure records/)).toBeNull()
    expect(fetch.mock.calls.some(([url]) => String(url).endsWith('/analyses'))).toBe(false)
  })

  it('keeps monitoring when the API rejects cancellation and allows another attempt', async () => {
    const fetch = mockRequests(async (url, init) => {
      if (url.endsWith('/validate')) return json({ valid: true, execution_eligible: true })
      if (init?.method === 'DELETE') return json({ error: { code: 'UNAVAILABLE', message: 'Try again' } }, 503)
      return json(queued, url.endsWith('/analyses') ? 201 : 200)
    })
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }))
    await waitFor(() => expect(fetch.mock.calls.some(([url]) => String(url).endsWith('/analyses'))).toBe(true))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(await screen.findByText(/Cancellation was not confirmed: Try again/)).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Cancel' }) as HTMLButtonElement).disabled).toBe(false)
    expect(screen.queryByText('Results current')).toBeNull()
  })

  it('rejects an invalid import without replacing the current model', async () => {
    const { cloneSampleModel } = await import('./sampleModel')
    mockRequests(async () => json({ valid: false, execution_eligible: false, errors: [{ json_path: '$.nodes[0].coordinates', message: 'Invalid coordinates' }] }))
    render(<App />)
    const file = new File(['model'], 'invalid-model.json', { type: 'application/json' })
    Object.defineProperty(file, 'text', { value: async () => JSON.stringify({ ...cloneSampleModel(), name: 'Invalid replacement' }) })
    fireEvent.change(document.querySelector('input[type=file]')!, { target: { files: [file] } })
    expect(await screen.findByText('$.nodes[0].coordinates: Invalid coordinates')).toBeTruthy()
    expect((screen.getByRole('textbox', { name: 'Display name' }) as HTMLInputElement).value).toBe('Shallow arch limit-point demo')
  })
})
