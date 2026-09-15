// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import CssBaseline from '@mui/material/CssBaseline'
import { ThemeProvider } from '@mui/material/styles'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { studioTheme } from '../theme'
import { MathCoreDialog } from './MathCoreDialog'

const catalog = {
  schema_version: '1.0.0',
  adapter_version: '0.1.0',
  limits: { max_parameter_values: 10000, max_parameter_depth: 12 },
  cores: [{
    core_id: 'plate_shell_buckling',
    title: 'Plate-Shell Buckling',
    version: '0.1.0',
    source_path: 'Plate-Shell-Buckling/python_math_core',
    scope: 'LBA and imperfection reference paths',
    residual_convention: 'R=f_int-lambda*f_ref',
    state_protocol: 'No material history.',
    verification_ids: ['V10'],
    verification_meaning: 'Reference evidence only.',
    limitations: ['Not a production shell element.'],
    operations: [
      { name: 'verify', summary: 'Run verification.', required_parameters: [], optional_parameters: [], example_parameters: {} },
      {
        name: 'linear_buckling', summary: 'Run LBA.',
        required_parameters: ['material_stiffness', 'geometric_stiffness'],
        optional_parameters: ['spectral_tolerance'],
        example_parameters: { material_stiffness: [[12, -2], [-2, 6]], geometric_stiffness: [[1, 0.2], [0.2, 0.5]] },
      },
    ],
  }],
} as const

describe('MathCoreDialog', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('loads the contract, selects an operation, and runs its executable example', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      if (String(input).endsWith('/api/v1/math-cores') && init?.method === 'GET') {
        return new Response(JSON.stringify(catalog), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (String(input).endsWith('/api/v1/math-cores/execute') && init?.method === 'POST') {
        return new Response(JSON.stringify({
          schema_version: '1.0.0', request_id: null, core: 'plate_shell_buckling', operation: 'linear_buckling',
          status: 'ok', data: { analysis_level: 'LBA', eigenpairs: [] }, diagnostics: { adapter_version: '0.1.0' }, error: null,
        }), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      throw new Error(`Unexpected request: ${String(input)}`)
    })

    render(<ThemeProvider theme={studioTheme}><CssBaseline /><MathCoreDialog open onClose={() => undefined} /></ThemeProvider>)
    expect(await screen.findByRole('dialog', { name: 'Step 2 Math Core' })).toBeTruthy()
    fireEvent.mouseDown(await screen.findByRole('combobox', { name: 'Operation' }))
    fireEvent.click(await screen.findByRole('option', { name: 'linear_buckling' }))
    expect((screen.getByRole('textbox', { name: 'Parameters (JSON)' }) as HTMLTextAreaElement).value).toContain('material_stiffness')
    fireEvent.click(screen.getByRole('button', { name: 'Run operation' }))

    expect(await screen.findByText('Completed')).toBeTruthy()
    expect(screen.getByText(/"analysis_level": "LBA"/)).toBeTruthy()
    const executeCall = fetchMock.mock.calls.find(([path]) => String(path).endsWith('/api/v1/math-cores/execute'))
    expect(JSON.parse(String(executeCall?.[1]?.body)).operation).toBe('linear_buckling')
  })

  it('keeps invalid JSON in place and shows a field-level correction', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(catalog), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )
    render(<ThemeProvider theme={studioTheme}><CssBaseline /><MathCoreDialog open onClose={() => undefined} /></ThemeProvider>)
    const editor = await screen.findByRole('textbox', { name: 'Parameters (JSON)' })
    fireEvent.input(editor, { target: { value: '{bad json' } })
    await waitFor(() => expect((editor as HTMLTextAreaElement).value).toBe('{bad json'))
    fireEvent.click(screen.getByRole('button', { name: 'Run operation' }))

    expect(await screen.findByText(/Enter valid JSON/)).toBeTruthy()
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    expect((editor as HTMLTextAreaElement).value).toBe('{bad json')
  })
})

it.each(['edit', 'operation', 'reset', 'close'] as const)('ignores an old result after %s while running', async (action) => {
  let complete!: (response: Response) => void
  let executeSignal: AbortSignal | null | undefined
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, init) => {
    if (String(url).endsWith('/execute')) {
      executeSignal = init?.signal
      return new Promise<Response>(resolve => { complete = resolve })
    }
    return new Response(JSON.stringify(catalog))
  })
  const view = render(<ThemeProvider theme={studioTheme}><MathCoreDialog open onClose={() => undefined} /></ThemeProvider>)
  await screen.findByRole('textbox', { name: 'Parameters (JSON)' })
  fireEvent.click(screen.getByRole('button', { name: 'Run operation' }))
  await waitFor(() => expect(complete).toBeTypeOf('function'))
  if (action === 'edit') fireEvent.change(screen.getByRole('textbox', { name: 'Parameters (JSON)' }), { target: { value: '{"typo": 1}' } })
  if (action === 'reset') fireEvent.click(screen.getByRole('button', { name: 'Reset example' }))
  if (action === 'operation') {
    fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Operation' }))
    fireEvent.click(await screen.findByRole('option', { name: 'linear_buckling' }))
  }
  if (action === 'close') {
    view.rerender(<ThemeProvider theme={studioTheme}><MathCoreDialog open={false} onClose={() => undefined} /></ThemeProvider>)
    view.rerender(<ThemeProvider theme={studioTheme}><MathCoreDialog open onClose={() => undefined} /></ThemeProvider>)
    await screen.findByRole('textbox', { name: 'Parameters (JSON)' })
  }
  expect(executeSignal?.aborted).toBe(true)
  complete(new Response(JSON.stringify({ schema_version: '1.0.0', request_id: null, core: 'plate_shell_buckling', operation: 'verify', status: 'ok', data: { obsolete: true }, diagnostics: {}, error: null })))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run operation' }).hasAttribute('disabled')).toBe(false))
  expect(screen.queryByText('Completed')).toBeNull()
  expect(screen.queryByText(/"obsolete"/)).toBeNull()
  cleanup()
  vi.restoreAllMocks()
})

it('preserves HTTP 200 operation errors instead of reporting completion', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => new Response(JSON.stringify(
    String(url).endsWith('/execute') ? { schema_version: '1.0.0', request_id: null, core: 'plate_shell_buckling', operation: 'verify', status: 'error', data: null, diagnostics: {}, error: { code: 'NUMERICAL_FAILURE', message: 'Singular matrix', details: {} } } : catalog,
  )))
  render(<ThemeProvider theme={studioTheme}><MathCoreDialog open onClose={() => undefined} /></ThemeProvider>)
  await screen.findByRole('textbox', { name: 'Parameters (JSON)' })
  fireEvent.click(screen.getByRole('button', { name: 'Run operation' }))
  expect(await screen.findByText('Singular matrix')).toBeTruthy()
  expect(screen.queryByText('Completed')).toBeNull()
  cleanup()
  vi.restoreAllMocks()
})
