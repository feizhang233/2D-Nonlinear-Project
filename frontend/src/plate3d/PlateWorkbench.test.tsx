// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import App from '../App'
import { studioTheme } from '../theme'
import { examplePlate } from './model'
import response from '../../../tests/fixtures/plate3d/cantilever-response.json'

const key = 'nonlinear-studio.plate3d.model.v1'
vi.setConfig({ testTimeout: 20000 })
let values: Map<string, string>
beforeEach(() => {
  values = new Map([
    ['nonlinear-studio-guide-hidden-v2', 'true'],
    [key, JSON.stringify(examplePlate())],
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
    if (String(input).includes('/plate3d/solve')) return Response.json(response)
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
  fireEvent.click(screen.getByRole('tab', { name: 'Plate 3D workspace' }))
}
it('preserves invalid drafts across properties close and spatial navigation', () => {
  open()
  expect(document.title).toBe('Plate 3D workspace — Nonlinear Studio')
  expect(screen.getByRole('tab', { name: 'Shell 3D workspace' })).toBeEnabled()
  fireEvent.click(screen.getByRole('button', { name: 'Material' }))
  fireEvent.change(screen.getByLabelText('Young modulus'), {
    target: { value: '2e-' },
  })
  expect(screen.getByRole('button', { name: 'Apply changes' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Save project' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Close' }))
  fireEvent.click(screen.getByRole('button', { name: 'Properties' }))
  expect(screen.getByLabelText('Young modulus')).toHaveValue('2e-')
  fireEvent.click(screen.getByRole('tab', { name: 'Continuum 3D workspace' }))
  fireEvent.click(screen.getByRole('tab', { name: 'Plate 3D workspace' }))
  expect(screen.getByLabelText('Young modulus')).toHaveValue('2e-')
  fireEvent.click(screen.getByRole('button', { name: 'Cancel changes' }))
  expect(screen.getByLabelText('Young modulus')).toHaveValue('210000000000')
})
it('submits a real plate contract, displays raw results, invalidates on edit and undoes', async () => {
  open()
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }))
  await waitFor(() =>
    expect(
      screen.getByText(/Numerical checks passed · residual/),
    ).toBeVisible(),
  )
  const call = vi
    .mocked(fetch)
    .mock.calls.find(([url]) => String(url).includes('/plate3d/solve'))!
  expect(JSON.parse(call[1]!.body as string)).toEqual(examplePlate())
  expect(
    screen.getByRole('table', { name: 'Plate displacements' }),
  ).toBeVisible()
  fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Result table' }))
  fireEvent.click(
    screen.getByRole('option', { name: 'Moments & shear · raw points' }),
  )
  expect(screen.getByRole('table', { name: 'Plate moments' })).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Model' }))
  fireEvent.click(screen.getByRole('button', { name: 'Material' }))
  fireEvent.change(screen.getByLabelText('Thickness'), {
    target: { value: '.08' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Apply changes' }))
  expect(JSON.parse(values.get(key)!).material.thickness).toBe(0.08)
  expect(screen.getByRole('button', { name: 'Results' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Undo' }))
  expect(JSON.parse(values.get(key)!).material.thickness).toBe(
    examplePlate().material.thickness,
  )
})
it('creates hard perimeter supports including both rotations at corners and restores cleared mesh by Undo', () => {
  open()
  fireEvent.click(screen.getByRole('button', { name: 'Support' }))
  fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Support target' }))
  fireEvent.click(screen.getByRole('option', { name: 'All boundary edges' }))
  fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Support type' }))
  fireEvent.click(screen.getByRole('option', { name: 'Hard simply supported' }))
  fireEvent.click(screen.getByRole('button', { name: 'Apply changes' }))
  const m = JSON.parse(values.get(key)!)
  expect(
    m.constraints.filter((c: { node_id: number }) => c.node_id === 1),
  ).toHaveLength(3)
  fireEvent.click(screen.getByRole('button', { name: 'Geometry & mesh' }))
  fireEvent.change(screen.getByLabelText('Divisions X'), {
    target: { value: '4' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Apply changes' }))
  expect(JSON.parse(values.get(key)!).constraints).toHaveLength(0)
  expect(JSON.parse(values.get(key)!).pressures).toHaveLength(0)
  fireEvent.click(screen.getByRole('button', { name: 'Undo' }))
  expect(JSON.parse(values.get(key)!)).toEqual(m)
})
it('blocks duplicates, ignores late cancelled results and allows retry after a failure', async () => {
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
  expect(screen.getByLabelText('Solving plate model')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Model' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  await act(async () => {
    resolve(Response.json(response))
  })
  expect(
    screen.queryByRole('table', { name: 'Plate displacements' }),
  ).not.toBeInTheDocument()
  vi.mocked(fetch).mockResolvedValueOnce(
    Response.json(
      { error: { message: 'Check plate supports' } },
      { status: 422 },
    ),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }))
  await waitFor(() =>
    expect(screen.getByText('Check plate supports')).toBeVisible(),
  )
  vi.mocked(fetch).mockResolvedValueOnce(Response.json(response))
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }))
  await waitFor(() =>
    expect(
      screen.getByRole('table', { name: 'Plate displacements' }),
    ).toBeVisible(),
  )
})
it('uses keyboard accessible paged selection and a separate 2D plate document', () => {
  open()
  fireEvent.click(screen.getByRole('button', { name: /^Nodes/ }))
  const pane = screen.getByRole('complementary', { name: 'Plate properties' })
  fireEvent.click(
    within(pane).getByRole('checkbox', { name: 'Select Plate nodes 1' }),
  )
  expect(
    screen.getByText('Selected node 1. Use Support or Load to assign it.'),
  ).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '2D' }))
  expect(screen.getByRole('tab', { name: 'Plate workspace' })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  fireEvent.click(screen.getByRole('button', { name: '3D' }))
  expect(
    screen.getByRole('tab', { name: 'Plate 3D workspace' }),
  ).toHaveAttribute('aria-selected', 'true')
})

it('keeps the committed model on rejected import and validates before replacing it', async () => {
  open()
  const original = values.get(key)!
  const candidate = { ...examplePlate(), name: 'Imported plate' }
  const file = new File(['{}'], 'import.plate3d.json', {
    type: 'application/json',
  })
  Object.defineProperty(file, 'text', {
    value: async () => JSON.stringify(candidate),
  })
  vi.mocked(fetch).mockResolvedValueOnce(
    Response.json(
      { error: { message: 'All nodes must be coplanar' } },
      { status: 422 },
    ),
  )
  fireEvent.change(screen.getByLabelText('Open plate project file'), {
    target: { files: [file] },
  })
  await waitFor(() =>
    expect(screen.getByText('All nodes must be coplanar')).toBeVisible(),
  )
  expect(values.get(key)).toBe(original)
  vi.mocked(fetch).mockResolvedValueOnce(Response.json(candidate))
  fireEvent.change(screen.getByLabelText('Open plate project file'), {
    target: { files: [file] },
  })
  await waitFor(() =>
    expect(screen.getByLabelText('Plate model name')).toHaveValue(
      'Imported plate',
    ),
  )
  expect(JSON.parse(values.get(key)!)).toEqual(candidate)
  fireEvent.click(screen.getByRole('button', { name: 'Undo' }))
  expect(values.get(key)).toBe(original)
})

it('reports local persistence failure without losing the edited model', () => {
  open()
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: {
      getItem: () => null,
      setItem: () => {
        throw new Error('Quota exceeded')
      },
    },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Material' }))
  fireEvent.change(screen.getByLabelText('Thickness'), {
    target: { value: '.08' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Apply changes' }))
  expect(
    screen.getByText(
      'Local saving is unavailable. Save project to keep a portable copy.',
    ),
  ).toBeVisible()
  expect(screen.getByLabelText('Thickness')).toHaveValue('.08')
  expect(screen.getByRole('button', { name: 'Save project' })).toBeEnabled()
})
