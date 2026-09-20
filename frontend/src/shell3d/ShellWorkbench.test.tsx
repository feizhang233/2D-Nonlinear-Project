// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import App from '../App'
import { studioTheme } from '../theme'
import { exampleShell } from './model'
import response from '../../../tests/fixtures/shell3d/cantilever-response.json'
const key = 'nonlinear-studio.shell3d.model.v1'
vi.setConfig({ testTimeout: 20000 })
let values: Map<string, string>
beforeEach(() => {
  values = new Map([
    ['nonlinear-studio-guide-hidden-v2', 'true'],
    [key, JSON.stringify(exampleShell())],
  ])
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: {
      getItem: (k: string) => values.get(k) ?? null,
      setItem: (k: string, v: string) => values.set(k, v),
    },
  })
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      disconnect() {}
      unobserve() {}
    },
  )
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    if (String(input).includes('/auth/session'))
      return Response.json({ authenticated: false, user: null })
    if (String(input).includes('/shell3d/solve')) return Response.json(response)
    throw new Error(`Unexpected request ${input}`)
  })
})
afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})
function open() {
  render(
    <ThemeProvider theme={studioTheme}>
      <App />
    </ThemeProvider>,
  )
  fireEvent.click(screen.getByRole('button', { name: '3D' }))
  fireEvent.click(screen.getByRole('tab', { name: 'Shell 3D workspace' }))
}
it('preserves incomplete scientific input across workspace switches and discards safely', () => {
  open()
  expect(document.title).toBe('Shell 3D workspace — Nonlinear Studio')
  fireEvent.click(screen.getByRole('button', { name: 'Material' }))
  fireEvent.change(screen.getByLabelText("Young's modulus"), {
    target: { value: '2e-' },
  })
  expect(screen.getByRole('button', { name: 'Apply changes' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Save project' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Close' }))
  fireEvent.click(screen.getByRole('button', { name: 'Properties' }))
  expect(screen.getByLabelText("Young's modulus")).toHaveValue('2e-')
  fireEvent.click(screen.getByRole('tab', { name: 'Plate 3D workspace' }))
  fireEvent.click(screen.getByRole('tab', { name: 'Shell 3D workspace' }))
  expect(screen.getByLabelText("Young's modulus")).toHaveValue('2e-')
  fireEvent.click(screen.getByRole('button', { name: 'Cancel changes' }))
  expect(screen.getByLabelText("Young's modulus")).toHaveValue('210000000000')
})
it('submits the real shell contract and displays unsmoothed fields, then invalidates results on edit', async () => {
  open()
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }))
  await waitFor(() =>
    expect(screen.getByRole('table', { name: 'Shell results' })).toBeVisible(),
  )
  const call = vi
    .mocked(fetch)
    .mock.calls.find(([url]) => String(url).includes('/shell3d/solve'))!
  expect(JSON.parse(call[1]!.body as string)).toEqual(exampleShell())
  fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Result table' }))
  fireEvent.click(
    screen.getByRole('option', { name: 'Raw membrane resultants' }),
  )
  expect(screen.getByRole('columnheader', { name: 'Nx (N/m)' })).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Model' }))
  fireEvent.click(screen.getByRole('button', { name: 'Material' }))
  fireEvent.change(screen.getByLabelText('Thickness'), {
    target: { value: '.03' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Apply changes' }))
  expect(JSON.parse(values.get(key)!).material.thickness).toBe(0.03)
  expect(screen.getByRole('button', { name: 'Results' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Undo' }))
  expect(JSON.parse(values.get(key)!).material.thickness).toBe(0.02)
})
it('regenerates a flat mesh, clears dependent data, and restores all data with Undo', () => {
  open()
  fireEvent.click(screen.getByRole('button', { name: 'Geometry' }))
  fireEvent.change(screen.getByLabelText('Fold angle'), {
    target: { value: '0' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Apply changes' }))
  const m = JSON.parse(values.get(key)!)
  expect(m.constraints).toHaveLength(0)
  expect(m.pressures).toHaveLength(0)
  expect(m.nodes.every((n: { z: number }) => n.z === 0)).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: 'Undo' }))
  expect(JSON.parse(values.get(key)!)).toEqual(exampleShell())
})
it('assigns selected nodal moments and single-DOF supports without losing other restraints', () => {
  open()
  fireEvent.click(screen.getByRole('button', { name: /^Nodes/ }))
  fireEvent.click(
    screen.getByRole('checkbox', { name: 'Select Shell nodes 1' }),
  )
  fireEvent.click(screen.getByRole('button', { name: /^Loads/ }))
  fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Load type' }))
  fireEvent.click(
    screen.getByRole('option', { name: 'Global nodal force and moment' }),
  )
  fireEvent.change(screen.getByLabelText('Moment Y'), {
    target: { value: '50' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Apply changes' }))
  expect(JSON.parse(values.get(key)!).nodal_loads[0].moment).toEqual([0, 50, 0])
  fireEvent.click(screen.getByRole('button', { name: /^Supports/ }))
  fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Support target' }))
  fireEvent.click(screen.getByRole('option', { name: 'Selected node' }))
  fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Support type' }))
  fireEvent.click(screen.getByRole('option', { name: 'Prescribed single DOF' }))
  fireEvent.change(screen.getByLabelText('Prescribed value'), {
    target: { value: '.001' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Apply changes' }))
  const cs = JSON.parse(values.get(key)!).constraints.filter(
    (c: { node_id: number }) => c.node_id === 1,
  )
  expect(cs).toHaveLength(6)
  expect(cs.find((c: { dof: string }) => c.dof === 'uz').value).toBe(0.001)
})
it('cancels late results and recovers from an actionable solver error', async () => {
  open()
  let resolve: (r: Response) => void = () => {}
  vi.mocked(fetch).mockImplementation((input) =>
    String(input).includes('/auth/session')
      ? Promise.resolve(Response.json({ authenticated: false, user: null }))
      : new Promise((r) => {
          resolve = r
        }),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }))
  expect(screen.getByLabelText('Solving shell')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Model' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  await act(async () => resolve(Response.json(response)))
  expect(
    screen.queryByRole('table', { name: 'Shell results' }),
  ).not.toBeInTheDocument()
  vi.mocked(fetch).mockResolvedValueOnce(
    Response.json(
      { error: { message: 'Check shell supports' } },
      { status: 422 },
    ),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }))
  await waitFor(() =>
    expect(screen.getByText('Check shell supports')).toBeVisible(),
  )
  vi.mocked(fetch).mockResolvedValueOnce(Response.json(response))
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }))
  await waitFor(() =>
    expect(screen.getByRole('table', { name: 'Shell results' })).toBeVisible(),
  )
})
it('keeps the current document when imported geometry is rejected by the server', async () => {
  open()
  const candidate = { ...exampleShell(), name: 'Rejected import' }
  vi.mocked(fetch).mockResolvedValueOnce(
    Response.json(
      { error: { message: 'Warped facet rejected' } },
      { status: 422 },
    ),
  )
  const file = new File([JSON.stringify(candidate)], 'bad.shell3d.json', {
    type: 'application/json',
  })
  Object.defineProperty(file, 'text', {
    value: async () => JSON.stringify(candidate),
  })
  fireEvent.change(
    document.querySelector(
      'input[type=file][accept=".json,application/json"]',
    )!,
    { target: { files: [file] } },
  )
  await waitFor(() =>
    expect(screen.getByText('Warped facet rejected')).toBeVisible(),
  )
  expect(JSON.parse(values.get(key)!)).toEqual(exampleShell())
})

it('restores generator fields when cancelling incomplete geometry edits', () => {
  open()
  fireEvent.click(screen.getByRole('button', { name: 'Geometry' }))
  fireEvent.change(screen.getByLabelText('Fold angle'), {
    target: { value: '2e-' },
  })
  expect(screen.getByRole('button', { name: 'Apply changes' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Cancel changes' }))
  expect(screen.getByLabelText('Fold angle')).toHaveValue('45')
  expect(JSON.parse(values.get(key)!)).toEqual(exampleShell())
})
