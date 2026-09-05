// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import CssBaseline from '@mui/material/CssBaseline'
import { ThemeProvider } from '@mui/material/styles'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { studioTheme } from './theme'

describe('Nonlinear Studio shell', () => {
  beforeEach(() => {
    const values = new Map<string, string>([['nonlinear-studio-guide-hidden-v2', 'true']])
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        getItem: (key: string) => values.get(key) ?? null,
        setItem: (key: string, value: string) => values.set(key, value),
        removeItem: (key: string) => values.delete(key),
        clear: () => values.clear(),
      },
    })
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      if (String(input).endsWith('/api/v1/auth/session')) {
        return new Response(JSON.stringify({ authenticated: false, user: null }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      throw new Error(`Unexpected request: ${String(input)}`)
    })
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('renders the model navigator, central canvas, and properties inspector', () => {
    render(<ThemeProvider theme={studioTheme}><CssBaseline /><App /></ThemeProvider>)
    expect(screen.getByText('Nonlinear Studio')).toBeTruthy()
    expect(screen.queryByText('Model builder')).toBeNull()
    expect(screen.queryByText('p11-shallow-arch')).toBeNull()
    expect(screen.queryByDisplayValue('p11-shallow-arch')).toBeNull()
    expect(screen.getAllByText('Model 1').length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: 'Open mesh settings' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Run analysis' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Guide' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Math Core' })).toBeTruthy()
    expect(screen.queryByRole('tab', { name: 'Solve monitor' })).toBeNull()
    expect((screen.getByRole('button', { name: 'Results' }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByLabelText('Modeling workflow progress')).toBeTruthy()
    expect(screen.getByText('5 of 6 complete')).toBeTruthy()
    expect(screen.queryByText('Setup readiness')).toBeNull()
    expect(screen.queryByRole('textbox', { name: 'Search model entities' })).toBeNull()
    const inspector = screen.getByRole('complementary', { name: 'Model properties' })
    expect(inspector.contains(screen.getByRole('tab', { name: 'Properties' }))).toBe(true)
    expect(screen.getByRole('main', { name: 'Model editing canvas' })).toBeTruthy()
    expect(screen.getByRole('tab', { name: 'Frame workspace' })).toBeTruthy()
  })

  it('collapses Properties on an entity double-click and keeps an explicit restore control', () => {
    render(<ThemeProvider theme={studioTheme}><CssBaseline /><App /></ThemeProvider>)
    fireEvent.doubleClick(screen.getByRole('button', { name: /Model information/ }))
    expect(screen.queryByRole('tab', { name: 'Properties' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Expand Properties' }))
    expect(screen.getByRole('tab', { name: 'Properties' })).toBeTruthy()
  })

  it('switches the complete working document between all supported model families', async () => {
    render(<ThemeProvider theme={studioTheme}><CssBaseline /><App /></ThemeProvider>)
    fireEvent.click(screen.getByRole('tab', { name: 'Continuum workspace' }))
    expect(screen.getByText('Q4 plane-strain tension')).toBeTruthy()
    expect(screen.getByRole('tab', { name: 'Continuum workspace' }).getAttribute('aria-selected')).toBe('true')

    fireEvent.click(screen.getByRole('tab', { name: 'Plate workspace' }))
    expect(screen.getByText('von Kármán MITC4 plate cantilever')).toBeTruthy()

    fireEvent.click(screen.getByRole('tab', { name: 'Shell workspace' }))
    expect(screen.getByText('Corotational Q4 flat-shell cantilever')).toBeTruthy()
  })

  it('validates, submits, and renders one successful API analysis flow', async () => {
    const result = {
      schema_version: '1.0.0', model_id: 'p11-shallow-arch', model_sha256: 'a'.repeat(64),
      solver_version: '0.1.0', status: 'succeeded', failures: [], metadata: {},
      steps: [{
        step_index: 0, status: 'accepted', control_method: 'load', load_factor: 0.1,
        requested_step_size: 0.1, accepted_step_size: 0.1, state_id: 'state-p15',
        iterations: [], response: { displacement: [0, 0, 0, 0, -0.0148, 0, 0, 0, 0] },
      }],
      post_result: { raw_fields: [], derived_fields: [], metadata: {} },
    }
    const record = {
      analysis_id: 'p15-e2e', status: 'succeeded', execution_mode: 'asynchronous', created_at: '2026-08-20T00:00:00Z',
      model_id: 'p11-shallow-arch', model_sha256: 'a'.repeat(64), control_method: 'load',
      dof_count: 9, progress: { accepted_steps: 1, message: 'analysis completed' }, result,
    }
    const fetchMock = vi.mocked(globalThis.fetch)
    let pollCount = 0
    fetchMock.mockImplementation(async (input, init) => {
      const path = String(input)
      if (path.endsWith('/api/v1/auth/session')) {
        return new Response(JSON.stringify({ authenticated: false, user: null }), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (path.endsWith('/api/v1/models/validate')) {
        return new Response(JSON.stringify({ valid: true, execution_eligible: true, dof_count: 9 }), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (path.endsWith('/api/v1/analyses') && init?.method === 'POST') {
        return new Response(JSON.stringify({ ...record, status: 'queued', result: null, progress: { accepted_steps: 0, message: 'analysis is queued' } }), { status: 201, headers: { 'Content-Type': 'application/json' } })
      }
      if (path.endsWith('/api/v1/analyses/p15-e2e')) {
        pollCount += 1
        return new Response(JSON.stringify(pollCount === 1
          ? { ...record, status: 'running', result: null, progress: { current_step: 1, current_iteration: 2, accepted_steps: 0, message: 'nonlinear iteration is running' } }
          : record), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    render(<ThemeProvider theme={studioTheme}><CssBaseline /><App /></ThemeProvider>)
    fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }))

    expect(await screen.findByText('Results current')).toBeTruthy()
    expect(await screen.findByText('Analysis complete: 1 accepted step')).toBeTruthy()
    expect(screen.getByRole('main', { name: 'Analysis results workspace' })).toBeTruthy()
    expect(screen.getByRole('tab', { name: 'Solve monitor' })).toBeTruthy()
    expect(screen.queryByRole('complementary', { name: 'Model navigator' })).toBeNull()
    expect(screen.queryByText(/ID p15/)).toBeNull()
    const analysisCalls = fetchMock.mock.calls.filter(([path]) => !String(path).endsWith('/api/v1/auth/session'))
    expect(analysisCalls[0]).toEqual(['/api/v1/models/validate', expect.objectContaining({ method: 'POST' })])
    expect(analysisCalls[1]).toEqual(['/api/v1/analyses', expect.objectContaining({ method: 'POST' })])
    expect(analysisCalls[2]).toEqual(['/api/v1/analyses/p15-e2e', expect.objectContaining({ method: 'GET' })])
    expect(analysisCalls[3]).toEqual(['/api/v1/analyses/p15-e2e', expect.objectContaining({ method: 'GET' })])
    expect(JSON.parse(String(analysisCalls[1][1]?.body)).execution_mode).toBe('asynchronous')
  })

  it('groups constraints by support class and deletes an added load', () => {
    render(<ThemeProvider theme={studioTheme}><CssBaseline /><App /></ThemeProvider>)
    fireEvent.click(screen.getAllByText('Supports')[0])
    expect(screen.getAllByText('Fixed').length).toBeGreaterThan(0)
    expect(screen.getByText('Custom')).toBeTruthy()
    expect(screen.queryByText('C1')).toBeNull()
    expect(screen.getByText('Support 1')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Delete Support 1' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Add loads' }))
    expect(screen.getAllByText('Load 2').length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: 'Delete Load 2' }))
    expect(screen.queryByText('Load 2')).toBeNull()
  })

  it('renames model entities without exposing or changing their solver IDs', () => {
    render(<ThemeProvider theme={studioTheme}><CssBaseline /><App /></ThemeProvider>)
    fireEvent.click(screen.getByRole('button', { name: /Materials Constitutive models/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Material 1' }))
    const displayName = screen.getByRole('textbox', { name: 'Display name' }) as HTMLInputElement
    fireEvent.change(displayName, { target: { value: 'S355 structural steel' } })

    expect(displayName.value).toBe('S355 structural steel')
    expect(screen.getAllByText('S355 structural steel').length).toBeGreaterThan(0)
    expect(screen.queryByText('M1')).toBeNull()

    fireEvent.click(screen.getAllByRole('button', { name: /Supports Boundary conditions/ }).at(-1)!)
    fireEvent.click(screen.getByRole('button', { name: /^Support 1/ }))
    const supportName = screen.getByRole('textbox', { name: 'Display name' }) as HTMLInputElement
    fireEvent.change(supportName, { target: { value: 'West abutment' } })
    expect(screen.getAllByText('West abutment').length).toBeGreaterThan(0)
    expect(screen.queryByText('N1')).toBeNull()
  })

  it('keeps Guest mode open and registers before saving private model history', async () => {
    const user = {
      id: 'user-1',
      email: 'engineer@example.com',
      display_name: 'Bridge Engineer',
      created_at: '2026-08-23T20:00:00Z',
    }
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockImplementation(async (input, init) => {
      const path = String(input)
      if (path.endsWith('/api/v1/auth/session')) {
        return new Response(JSON.stringify({ authenticated: false, user: null }), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (path.endsWith('/api/v1/auth/register')) {
        return new Response(JSON.stringify({ authenticated: true, user }), { status: 201, headers: { 'Content-Type': 'application/json' } })
      }
      if (path.endsWith('/api/v1/models') && init?.method === 'GET') {
        return new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (path.endsWith('/api/v1/models') && init?.method === 'POST') {
        const body = JSON.parse(String(init.body))
        return new Response(JSON.stringify({
          id: 'saved-1', name: body.name, model_family: body.model.model_family,
          saved_at: '2026-08-23T20:05:00Z', model: body.model,
        }), { status: 201, headers: { 'Content-Type': 'application/json' } })
      }
      throw new Error(`Unexpected request: ${path}`)
    })

    render(<ThemeProvider theme={studioTheme}><CssBaseline /><App /></ThemeProvider>)
    const guestAccount = await screen.findByRole('button', { name: 'Guest account' })
    await waitFor(() => expect((guestAccount as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(screen.getByText('Sign in or register to save the model currently open in the workbench.')).toBeTruthy()
    fireEvent.click(screen.getByRole('tab', { name: 'Register' }))
    fireEvent.change(screen.getByRole('textbox', { name: 'Display name' }), { target: { value: 'Bridge Engineer' } })
    fireEvent.change(screen.getByRole('textbox', { name: 'Email' }), { target: { value: 'engineer@example.com' } })
    const passwordFields = Array.from(document.querySelectorAll<HTMLInputElement>('input[autocomplete="new-password"]'))
    expect(passwordFields).toHaveLength(2)
    fireEvent.change(passwordFields[0], { target: { value: 'strong-password' } })
    fireEvent.change(passwordFields[1], { target: { value: 'strong-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByRole('button', { name: 'Account for Bridge Engineer', hidden: true })).toBeTruthy()
    expect(await screen.findByText('Saved “Shallow arch limit-point demo” to your model history.')).toBeTruthy()
    const saveCall = fetchMock.mock.calls.find(([path, init]) => String(path).endsWith('/api/v1/models') && init?.method === 'POST')
    expect(saveCall).toBeTruthy()
    expect(JSON.parse(String(saveCall?.[1]?.body)).model.model_id).toBe('p11-shallow-arch')
  })

  it('edits a Continuum load as a boundary distributed load', async () => {
    render(<ThemeProvider theme={studioTheme}><CssBaseline /><App /></ThemeProvider>)
    fireEvent.click(screen.getByRole('tab', { name: 'Continuum workspace' }))
    fireEvent.click(screen.getAllByText('Loads')[0])
    fireEvent.click(screen.getAllByText('Load 1')[0])
    fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Load type' }))
    fireEvent.click(await screen.findByRole('option', { name: 'Boundary distributed load' }))

    expect(screen.getByText(/Continuum · Boundary distributed load/)).toBeTruthy()
    expect(screen.getByRole('combobox', { name: 'Element' })).toBeTruthy()
    expect(screen.getByRole('combobox', { name: 'Local edge' })).toBeTruthy()
  })

  it('shows surface mesh nodes and elements as read-only entities', () => {
    render(<ThemeProvider theme={studioTheme}><CssBaseline /><App /></ThemeProvider>)
    fireEvent.click(screen.getByRole('tab', { name: 'Continuum workspace' }))
    expect((screen.getByRole('button', { name: 'Add nodes' }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: 'Add elements' }) as HTMLButtonElement).disabled).toBe(true)

    fireEvent.click(screen.getByRole('button', { name: /Nodes Visible read-only mesh entities/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Node 1' }))
    expect(screen.getByText('Mesh nodes are visible for inspection but cannot be edited directly. Edit the Geometry contour and generate a new mesh.')).toBeTruthy()
    expect((screen.getByRole('textbox', { name: 'Display name' }) as HTMLInputElement).disabled).toBe(true)
  })

  it('shows and reopens the six-step beginner guide', async () => {
    window.localStorage.removeItem('nonlinear-studio-guide-hidden-v2')
    render(<ThemeProvider theme={studioTheme}><CssBaseline /><App /></ThemeProvider>)

    expect(screen.getByRole('dialog', { name: 'Getting started with Nonlinear Studio' })).toBeTruthy()
    expect(screen.getByText('Step 1 of 6')).toBeTruthy()
    expect(screen.getByText('Choose a model workspace')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Use Frame example' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Use Continuum example' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Use Plate example' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Use Shell example' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Use Plate example' }))
    await waitFor(() => expect(screen.getByText('Step 2 of 6')).toBeTruthy())
    expect(screen.getByText('von Kármán MITC4 plate cantilever')).toBeTruthy()
    expect(screen.getByText('Review geometry and topology')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    expect(screen.getByText('Step 3 of 6')).toBeTruthy()
    expect(screen.getByText('Define materials and supports')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Close guide' }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Getting started with Nonlinear Studio' })).toBeNull())

    fireEvent.click(screen.getByRole('button', { name: 'Guide' }))
    expect(screen.getByText('Step 1 of 6')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Use Continuum example' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: "Don't show again" }))
    expect(window.localStorage.getItem('nonlinear-studio-guide-hidden-v2')).toBe('true')
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Getting started with Nonlinear Studio' })).toBeNull())
  }, 10_000)

  it('generates and applies a Gmsh Q4 mesh from model properties', async () => {
    const meshResponse = {
      engine: 'Gmsh', engine_version: '4.15.2', model_family: 'continuum',
      formulation: 'Q4-total-lagrangian', mesh_size: 0.5,
      nodes: [
        { id: 'N1', coordinates: [0, 0] }, { id: 'N2', coordinates: [2, 0] },
        { id: 'N3', coordinates: [2, 1] }, { id: 'N4', coordinates: [0, 1] },
      ],
      elements: [{
        id: 'E1', formulation: 'Q4-total-lagrangian', node_ids: ['N1', 'N2', 'N3', 'N4'],
        material_id: 'M1', properties: { thickness: 0.1 },
      }],
      boundaries: [
        { id: 'B1', label: 'Boundary 1', node_ids: ['N1', 'N2'], length: 2, segments: [{ element_id: 'E1', local_edge: 0, node_ids: ['N1', 'N2'] }] },
        { id: 'B2', label: 'Boundary 2', node_ids: ['N2', 'N3'], length: 1, segments: [{ element_id: 'E1', local_edge: 1, node_ids: ['N2', 'N3'] }] },
        { id: 'B3', label: 'Boundary 3', node_ids: ['N3', 'N4'], length: 2, segments: [{ element_id: 'E1', local_edge: 2, node_ids: ['N3', 'N4'] }] },
        { id: 'B4', label: 'Boundary 4', node_ids: ['N4', 'N1'], length: 1, segments: [{ element_id: 'E1', local_edge: 3, node_ids: ['N4', 'N1'] }] },
      ],
    }
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockImplementation(async (input) => {
      if (String(input).endsWith('/api/v1/auth/session')) {
        return new Response(JSON.stringify({ authenticated: false, user: null }), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (String(input).endsWith('/api/v1/meshes')) {
        return new Response(JSON.stringify(meshResponse), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      throw new Error(`Unexpected request: ${String(input)}`)
    })
    render(<ThemeProvider theme={studioTheme}><CssBaseline /><App /></ThemeProvider>)
    fireEvent.click(screen.getByRole('tab', { name: 'Continuum workspace' }))
    expect(screen.getByText('Finite element mesh: Current topology · 4 nodes · 1 Q4')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Open mesh settings' }))
    expect(screen.getByText(/Gmsh remeshing has not been run/)).toBeTruthy()
    const meshSize = screen.getByRole('spinbutton', { name: 'Target element size' }) as HTMLInputElement
    const generateButton = screen.getByRole('button', { name: 'Generate mesh with Gmsh' }) as HTMLButtonElement
    fireEvent.change(meshSize, { target: { value: '0' } })
    expect(meshSize.value).toBe('0')
    expect(generateButton.disabled).toBe(true)
    fireEvent.change(meshSize, { target: { value: '0.1' } })
    expect(meshSize.value).toBe('0.1')
    expect(generateButton.disabled).toBe(false)
    fireEvent.click(generateButton)

    expect(await screen.findByText('Gmsh mesh staged: 4 nodes / 1 Q4 elements. Apply changes to commit it.')).toBeTruthy()
    expect(screen.getByText('Finite element mesh: Gmsh 4.15.2 · 4 nodes · 1 Q4')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Apply changes' }) as HTMLButtonElement).disabled).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: 'Apply changes' }))
    expect(await screen.findByText('rev 1')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Apply changes' }) as HTMLButtonElement).disabled).toBe(true)
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/meshes', expect.objectContaining({ method: 'POST' }))
    const meshCall = fetchMock.mock.calls.find(([path]) => String(path).endsWith('/api/v1/meshes'))
    expect(JSON.parse(String(meshCall?.[1]?.body)).mesh_size).toBe(0.1)
  }, 10_000)

  it('stages form edits and supports both Cancel and Apply', () => {
    render(<ThemeProvider theme={studioTheme}><CssBaseline /><App /></ThemeProvider>)
    const name = screen.getByRole('textbox', { name: 'Display name' }) as HTMLInputElement
    fireEvent.change(name, { target: { value: 'Draft arch' } })
    expect(screen.getByText('Unapplied changes')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Run analysis' }) as HTMLButtonElement).disabled).toBe(true)

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect((screen.getByRole('textbox', { name: 'Display name' }) as HTMLInputElement).value).toBe('Shallow arch limit-point demo')

    fireEvent.change(screen.getByRole('textbox', { name: 'Display name' }), { target: { value: 'Applied arch' } })
    fireEvent.click(screen.getByRole('button', { name: 'Apply changes' }))
    expect(screen.getByText('Applied arch')).toBeTruthy()
    expect(screen.getByText('rev 1')).toBeTruthy()
  })

  it('guards workspace navigation and can apply staged edits before continuing', async () => {
    render(<ThemeProvider theme={studioTheme}><CssBaseline /><App /></ThemeProvider>)
    fireEvent.change(screen.getByRole('textbox', { name: 'Display name' }), { target: { value: 'Guarded arch' } })

    fireEvent.click(screen.getByRole('tab', { name: 'Continuum workspace' }))
    expect(screen.getByRole('dialog', { name: 'Unapplied changes' })).toBeTruthy()
    expect(screen.getByText(/before opening Continuum workspace/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Keep editing' }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Unapplied changes' })).toBeNull())
    expect(screen.getByRole('tab', { name: /^Frame workspace/ }).getAttribute('aria-selected')).toBe('true')

    fireEvent.click(screen.getByRole('tab', { name: 'Continuum workspace' }))
    fireEvent.click(screen.getByRole('button', { name: 'Apply and continue' }))
    await waitFor(() => expect(screen.getByRole('tab', { name: 'Continuum workspace' }).getAttribute('aria-selected')).toBe('true'))

    fireEvent.click(screen.getByRole('tab', { name: 'Frame workspace' }))
    expect((screen.getByRole('textbox', { name: 'Display name' }) as HTMLInputElement).value).toBe('Guarded arch')
    expect(screen.getByText('rev 1')).toBeTruthy()
  })
})
