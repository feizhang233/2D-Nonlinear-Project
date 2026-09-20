// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import App from '../App'
import { studioTheme } from '../theme'
import { example3D } from './model'
import response from '../../../tests/fixtures/frame3d/cantilever_response.json'

const key = 'nonlinear-studio.frame3d.model.v1'
let values: Map<string, string>
beforeEach(() => {
  values = new Map([['nonlinear-studio-guide-hidden-v2', 'true'], [key, JSON.stringify(example3D())]])
  Object.defineProperty(window, 'localStorage', { configurable: true, value: {
    getItem: (k: string) => values.get(k) ?? null,
    setItem: (k: string, v: string) => values.set(k, v),
  } })
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} unobserve() {} })
  vi.spyOn(globalThis, 'fetch').mockImplementation(async input => {
    if (String(input).includes('/3d/solve')) return Response.json(response)
    if (String(input).includes('/auth/session')) return Response.json({ authenticated: false, user: null })
    throw new Error(`Unexpected request: ${input}`)
  })
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })
function openSpatial() {
  render(<ThemeProvider theme={studioTheme}><App /></ThemeProvider>)
  fireEvent.click(screen.getByRole('button', { name: '3D' }))
}
it('retains independent workspaces, title, property draft and local model across switches', () => {
  openSpatial()
  fireEvent.change(screen.getByLabelText('3D model name'), { target: { value: 'My space frame' } })
  fireEvent.blur(screen.getByLabelText('3D model name'))
  fireEvent.click(screen.getByRole('button', { name: 'Materials' }))
  fireEvent.change(screen.getByLabelText('E (GPa)'), { target: { value: '2e-' } })
  fireEvent.click(screen.getByRole('button', { name: '2D' }))
  expect(document.title).toBe('Frame workspace — Nonlinear Studio')
  expect(screen.getByText('Shallow arch limit-point demo')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: '3D' }))
  expect(screen.getByLabelText('3D model name')).toHaveProperty('value', 'My space frame')
  expect(screen.getByLabelText('E (GPa)')).toHaveProperty('value', '2e-')
  expect(document.title).toBe('Frame 3D workspace — Nonlinear Studio')
})
it('rejects invalid material assignment and applies only material values with undo', () => {
  openSpatial()
  fireEvent.click(screen.getByRole('button', { name: 'Materials' }))
  fireEvent.change(screen.getByLabelText('E (GPa)'), { target: { value: '-1' } })
  fireEvent.click(screen.getByRole('button', { name: 'Apply material to all elements' }))
  expect(screen.getByText('Correct the highlighted values before applying.')).toBeTruthy()
  expect(JSON.parse(values.get(key)!).elements[0].E).toBe(210e9)
  fireEvent.change(screen.getByLabelText('E (GPa)'), { target: { value: '195' } })
  fireEvent.click(screen.getByRole('button', { name: 'Apply material to all elements' }))
  expect(JSON.parse(values.get(key)!).elements[0]).toMatchObject({ E: 195e9, A: .01, Iy: 8.33e-5 })
  fireEvent.click(screen.getByRole('button', { name: 'Undo 3D change' }))
  expect(JSON.parse(values.get(key)!).elements[0].E).toBe(210e9)
})
it('solves through the host route, shows six result components and invalidates results on edit', async () => {
  openSpatial()
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }))
  await screen.findByText('Checks passed')
  const call = vi.mocked(fetch).mock.calls.find(([url]) => String(url).includes('/3d/solve'))!
  const body = JSON.parse(String(call[1]?.body))
  expect(body.include_plots).toBe(false)
  expect(body).not.toHaveProperty('name')
  fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Display' }))
  expect(screen.getByRole('option', { name: 'Torsion T' })).toBeTruthy()
  fireEvent.click(screen.getByRole('option', { name: 'Torsion T' }))
  fireEvent.click(screen.getByRole('button', { name: '2D' }))
  fireEvent.click(screen.getByRole('button', { name: '3D' }))
  expect(screen.getByText('Checks passed')).toBeTruthy()
  fireEvent.change(screen.getByLabelText('3D model name'), { target: { value: 'Changed' } })
  fireEvent.blur(screen.getByLabelText('3D model name'))
  expect(screen.queryByText('Checks passed')).toBeNull()
})
it('shows request failure and allows retry; cancellation prevents late results', async () => {
  openSpatial()
  vi.mocked(fetch).mockResolvedValueOnce(Response.json({ error: { code: 'FRAME3D_INVALID_MODEL', message: 'Unrestrained mechanism' } }, { status: 422 }))
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }))
  await screen.findByText('Unrestrained mechanism')
  let finish!: (r: Response) => void
  vi.mocked(fetch).mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
  fireEvent.click(screen.getByRole('button', { name: 'Retry analysis' }))
  await screen.findByText('Solving 3D frame…')
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  finish(Response.json(response))
  await waitFor(() => expect(screen.queryByText('Solving 3D frame…')).toBeNull())
  expect(screen.queryByText('Checks passed')).toBeNull()
  expect(screen.getByText(/The server may still be finishing/)).toBeTruthy()
})
