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
