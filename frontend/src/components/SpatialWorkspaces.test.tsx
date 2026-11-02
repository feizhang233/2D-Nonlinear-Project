// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { SpatialWorkspaces } from './SpatialWorkspaces'
import type { SpatialFamily } from '../workspaces'

const modules = vi.hoisted(() => ({ frame: vi.fn(), solid: vi.fn(), plate: vi.fn(), shell: vi.fn(), fail: false }))
function DocumentProbe({ family }: { family: string }) {
  const [value, setValue] = useState('')
  return <input aria-label={`${family} unfinished field`} value={value} onChange={event => setValue(event.target.value)} />
}
vi.mock('../spatial/ConfirmProvider', () => ({ ConfirmProvider: ({ children }: { children: React.ReactNode }) => children }))
vi.mock('../spatial/SpatialWorkbench', () => {
  modules.frame()
  return { SpatialWorkbench: () => <DocumentProbe family="frame" /> }
})
vi.mock('../continuum3d/SolidWorkbench', () => {
  modules.solid()
  return { SolidWorkbench: () => {
    if (modules.fail) throw new Error('Workspace unavailable')
    return <DocumentProbe family="solid" />
  } }
})
vi.mock('../plate3d/PlateWorkbench', () => { modules.plate(); return { PlateWorkbench: () => null } })
vi.mock('../shell3d/ShellWorkbench', () => { modules.shell(); return { ShellWorkbench: () => null } })

afterEach(() => { cleanup(); modules.fail = false; vi.restoreAllMocks() })
const props = {
  onOpen: vi.fn(), on2D: vi.fn(),
  draftFamilies: new Set<never>(), resultFamilies: new Set<never>(),
}

it('loads only visited families and retains unfinished fields through dimension changes', async () => {
  const view = render(<SpatialWorkspaces {...props} active={false} visited={new Set()} />)
  expect(modules.frame).not.toHaveBeenCalled()
  expect(modules.solid).not.toHaveBeenCalled()
  const visited = new Set<SpatialFamily>(['frame3d'])
  view.rerender(<SpatialWorkspaces {...props} active="frame3d" visited={visited} />)
  const field = await screen.findByRole('textbox', { name: 'frame unfinished field' })
  fireEvent.change(field, { target: { value: '1.2e-' } })
  view.rerender(<SpatialWorkspaces {...props} active={false} visited={visited} />)
  view.rerender(<SpatialWorkspaces {...props} active="frame3d" visited={visited} />)
  expect(screen.getByRole('textbox', { name: 'frame unfinished field' })).toHaveValue('1.2e-')
  expect(modules.frame).toHaveBeenCalledTimes(1)
  expect(modules.solid).not.toHaveBeenCalled()
  expect(modules.plate).not.toHaveBeenCalled()
  expect(modules.shell).not.toHaveBeenCalled()
})

it('keeps dimension navigation reachable after load failure and permits retry', async () => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
  modules.fail = true
  render(<SpatialWorkspaces {...props} active="continuum3d" visited={new Set(['continuum3d'])} />)
  expect(await screen.findByRole('alert')).toHaveTextContent('workspace could not be loaded')
  fireEvent.click(screen.getByRole('button', { name: '2D' }))
  expect(props.on2D).toHaveBeenCalledWith('continuum')
  modules.fail = false
  fireEvent.click(screen.getByRole('button', { name: 'Retry loading workspace' }))
  expect(await screen.findByRole('textbox', { name: 'solid unfinished field' })).toBeVisible()
})
