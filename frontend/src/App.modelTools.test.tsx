// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
import { ThemeProvider } from '@mui/material/styles'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import App from './App'
import { studioTheme } from './theme'
import { cloneSampleModel } from './sampleModel'

beforeEach(() => {
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: { getItem: () => 'true', setItem: vi.fn() },
  })
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, init) => {
    if (String(url).endsWith('/api/v1/auth/session'))
      return Response.json({ authenticated: false, user: null })
    if (String(url).endsWith('/api/v1/projects/validate'))
      return Response.json(JSON.parse(String(init?.body)))
    throw new Error(`Unexpected request ${url}`)
  })
})
afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})
const mount = () =>
  render(
    <ThemeProvider theme={studioTheme}>
      <App />
    </ThemeProvider>,
  )

it('uses one fixed main action for Apply and Run and blocks unfinished scientific notation', () => {
  mount()
  const action = screen.getByRole('button', { name: 'Run analysis' })
  fireEvent.click(
    screen.getByRole('button', { name: 'Select Load 1 UY on canvas' }),
  )
  const input = screen.getByRole('textbox', { name: 'UY component' })
  fireEvent.change(input, { target: { value: '-2.5e' } })
  expect(screen.getByRole('button', { name: 'Apply changes' })).toBe(action)
  expect((action as HTMLButtonElement).disabled).toBe(true)
  expect(screen.queryByRole('button', { name: 'Run analysis' })).toBeNull()
  fireEvent.change(input, { target: { value: '-2.5e4' } })
  expect((action as HTMLButtonElement).disabled).toBe(false)
  fireEvent.click(action)
  expect(screen.getByRole('button', { name: 'Run analysis' })).toBe(action)
  expect(
    (screen.getByRole('textbox', { name: 'UY component' }) as HTMLInputElement)
      .value,
  ).toBe('-2.5e4')
})

it('opens independent analysis settings and preserves staged options on return to the model', async () => {
  mount()
  expect(screen.queryByRole('tab', { name: 'Analysis' })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Analysis settings' }))
  expect(screen.getByRole('dialog', { name: 'Analysis settings' })).toBeTruthy()
  fireEvent.change(
    screen.getByRole('spinbutton', { name: 'Target load factor' }),
    { target: { value: '0.5' } },
  )
  fireEvent.click(screen.getByRole('button', { name: 'Back to model' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Apply changes' }))
  fireEvent.click(screen.getByRole('button', { name: 'Analysis settings' }))
  expect(
    (
      screen.getByRole('spinbutton', {
        name: 'Target load factor',
      }) as HTMLInputElement
    ).value,
  ).toBe('0.5')
})

it('deletes selected loads/supports from the keyboard but protects text entry, and Cancel restores them', () => {
  mount()
  fireEvent.click(
    screen.getByRole('button', { name: 'Select Load 1 UY on canvas' }),
  )
  const name = screen.getByRole('textbox', { name: 'Display name' })
  fireEvent.keyDown(name, { key: 'Delete' })
  expect(
    screen.getByRole('button', { name: 'Select Load 1 UY on canvas' }),
  ).toBeTruthy()
  fireEvent.keyDown(window, { key: 'Delete', isComposing: true })
  expect(
    screen.getByRole('button', { name: 'Select Load 1 UY on canvas' }),
  ).toBeTruthy()
  fireEvent.keyDown(window, { key: 'Delete' })
  expect(
    screen.queryByRole('button', { name: 'Select Load 1 UY on canvas' }),
  ).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(
    screen.getByRole('button', { name: 'Select Load 1 UY on canvas' }),
  ).toBeTruthy()
  fireEvent.click(
    screen.getByRole('button', { name: 'Select Support 1 on canvas' }),
  )
  fireEvent.keyDown(window, { key: 'Backspace' })
  expect(
    screen.queryByRole('button', { name: 'Select Support 1 on canvas' }),
  ).toBeNull()
})

it('creates a rectangular section, applies it to every element and blocks invalid dimensions', () => {
  mount()
  fireEvent.click(screen.getByRole('button', { name: 'Browse sections' }))
  fireEvent.click(screen.getByRole('button', { name: 'Add sections' }))
  fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Section shape' }))
  fireEvent.click(screen.getByRole('option', { name: 'Rectangle' }))
  fireEvent.change(screen.getByRole('spinbutton', { name: 'Width b' }), {
    target: { value: '0.4' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Assign all' }))
  expect(screen.getByText('2 of 2 assigned')).toBeTruthy()
  fireEvent.change(screen.getByRole('spinbutton', { name: 'Height h' }), {
    target: { value: '' },
  })
  expect(
    (screen.getByRole('button', { name: 'Apply changes' }) as HTMLButtonElement)
      .disabled,
  ).toBe(true)
  expect(
    (screen.getByRole('button', { name: 'Cancel' }) as HTMLButtonElement)
      .disabled,
  ).toBe(false)
  fireEvent.change(screen.getByRole('spinbutton', { name: 'Height h' }), {
    target: { value: '0.3' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Apply changes' }))
  fireEvent.click(screen.getByRole('button', { name: 'Browse elements' }))
  fireEvent.click(
    within(
      screen.getByRole('complementary', { name: 'Model navigator' }),
    ).getByRole('button', { name: 'Select Element 1' }),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Element details' }))
  expect(
    (screen.getByRole('spinbutton', { name: 'Area A' }) as HTMLInputElement)
      .value,
  ).toBe('0.12')
})

it('splits a selected member into quarters and Cancel restores the original topology', () => {
  mount()
  fireEvent.click(screen.getByRole('button', { name: 'Select Element 1' }))
  fireEvent.click(screen.getByRole('button', { name: 'Split member' }))
  fireEvent.click(screen.getByRole('button', { name: 'Quarters' }))
  fireEvent.click(screen.getByRole('button', { name: 'Split element' }))
  expect(screen.getAllByText(/6 nodes · 5 elements/)[0]).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(
    screen.queryByRole('button', { name: 'Select Element 1 / 1' }),
  ).toBeNull()
  expect(screen.getByRole('button', { name: 'Select Element 1' })).toBeTruthy()
})

it('opens a project with saved result state instead of dropping the evidence', async () => {
  const { container } = mount()
  const model = cloneSampleModel('frame')
  const result = {
    schema_version: '1.0.0',
    model_id: model.model_id,
    model_sha256: 'a'.repeat(64),
    solver_version: '0.1.0',
    status: 'succeeded',
    failures: [],
    metadata: {},
    steps: [],
    post_result: null,
  }
  const record = {
    analysis_id: 'saved-analysis',
    status: 'succeeded',
    model_id: model.model_id,
    result,
    progress: { accepted_steps: 0, message: 'Restored' },
  }
  const project = {
    studio_project_version: '1.0.0',
    model,
    workspace: {
      run_options: { targetLoadFactor: 0.2, numberOfSteps: 4 },
      record,
      selected_step: 0,
      result_view: 'model',
      result_tab: 'curves',
    },
  }
  const file = new File([JSON.stringify(project)], 'saved-project.json', {
    type: 'application/json',
  })
  Object.defineProperty(file, 'text', {
    value: async () => JSON.stringify(project),
  })
  fireEvent.change(container.querySelector('input[type=file]')!, {
    target: { files: [file] },
  })
  await waitFor(() =>
    expect(
      screen
        .getByRole('button', { name: 'Results' })
        .getAttribute('aria-pressed'),
    ).toBe('true'),
  )
  expect(screen.getByText('Results current')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Save project' }))
  expect(
    (
      screen.getByRole('checkbox', {
        name: 'Include analysis results and current result view',
      }) as HTMLInputElement
    ).checked,
  ).toBe(true)
})

it('keeps canvas creation full-width and reveals an inspector only when requested', () => {
  mount()
  fireEvent.click(screen.getByRole('button', { name: 'Browse nodes' }))
  expect(
    screen.queryByRole('complementary', { name: 'Model properties' }),
  ).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Add nodes' }))
  fireEvent.click(
    screen.getByRole('group', { name: 'Frame 2D engineering projection' }),
    { clientX: 250, clientY: 350 },
  )
  expect(
    screen.queryByRole('complementary', { name: 'Model properties' }),
  ).toBeNull()
  expect(screen.getByText('4 nodes · 2 elements')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Expand Properties' }))
  expect(screen.getByRole('spinbutton', { name: 'X' })).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(screen.getByText('3 nodes · 2 elements')).toBeTruthy()
})

it('preserves unfinished scientific input when Properties is hidden and restored', () => {
  mount()
  fireEvent.click(
    screen.getByRole('button', { name: 'Select Load 1 UY on canvas' }),
  )
  const original = (
    screen.getByRole('textbox', { name: 'UY component' }) as HTMLInputElement
  ).value
  fireEvent.change(screen.getByRole('textbox', { name: 'UY component' }), {
    target: { value: '-2.5e' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Collapse Properties' }))
  expect(screen.queryByRole('textbox', { name: 'UY component' })).toBeNull()
  expect(
    (screen.getByRole('button', { name: 'Apply changes' }) as HTMLButtonElement)
      .disabled,
  ).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: 'Expand Properties' }))
  expect(
    (screen.getByRole('textbox', { name: 'UY component' }) as HTMLInputElement)
      .value,
  ).toBe('-2.5e')
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  fireEvent.click(
    screen.getByRole('button', { name: 'Select Load 1 UY on canvas' }),
  )
  expect(
    (screen.getByRole('textbox', { name: 'UY component' }) as HTMLInputElement)
      .value,
  ).toBe(original)
})

it('waits for the first canvas click from every Load entry and relocates line loads without losing values', () => {
  mount()
  fireEvent.click(screen.getByRole('button', { name: 'Load' }))
  expect(screen.queryByRole('button', { name: 'Apply changes' })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Select Element 2' }))
  expect(screen.getByRole('combobox', { name: 'Member' }).textContent).toBe(
    'Element 2',
  )
  fireEvent.change(
    screen.getByRole('textbox', { name: 'qy distributed intensity' }),
    { target: { value: '-2.5e4' } },
  )
  fireEvent.click(
    screen.getByRole('button', { name: 'Pick location on canvas' }),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Select Node 1' }))
  expect(
    screen.getByText('Click a member or a surface element for this load.'),
  ).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Select Element 1' }))
  expect(screen.getByRole('combobox', { name: 'Member' }).textContent).toBe(
    'Element 1',
  )
  expect(
    Number(
      (
        screen.getByRole('textbox', {
          name: 'qy distributed intensity',
        }) as HTMLInputElement
      ).value,
    ),
  ).toBe(-25000)
  fireEvent.click(screen.getByRole('button', { name: 'Add loads' }))
  fireEvent.click(screen.getByRole('button', { name: 'Select Node 3' }))
  expect(
    screen.getByRole('combobox', { name: 'Location' }).textContent,
  ).toContain('Node 3')
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(screen.queryByRole('button', { name: 'Select Load 2' })).toBeNull()
})
