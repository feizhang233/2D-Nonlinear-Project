// @vitest-environment jsdom
import { useState } from 'react'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { afterEach, expect, it, vi } from 'vitest'
import { ThemeProvider } from '@mui/material/styles'
import { studioTheme } from '../theme'
import { SpatialNavigator } from './SpatialNavigator'
import { blankModel, example3D, type Model3D, type Selection, type Tool } from './model'

afterEach(cleanup)
function setup(model = example3D(), initialSelection: Selection = { nodes: [], elements: [] }) {
  const create = vi.fn(); const select = vi.fn()
  function Harness() {
    const [tool, setTool] = useState<Tool>('select')
    const [selection, setSelection] = useState(initialSelection)
    return <ThemeProvider theme={studioTheme}><SpatialNavigator model={model} selection={selection} activeTool={tool} onTool={setTool}
      onCreate={kind => { create(kind); setSelection({ nodes: [], elements: [] }); setTool(kind === 'nodes' ? 'node' : 'member') }}
      onSelect={(kind, id, context) => { select(kind, id, context); setSelection({ nodes: [], elements: [], [kind]: [id] }); setTool(context) }} /></ThemeProvider>
  }
  render(<Harness />)
  return { create, select }
}
it('separates category browsing, object selection and new geometry', () => {
  const { create, select } = setup()
  fireEvent.click(screen.getByRole('button', { name: 'Nodes' }))
  expect(create).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Node 1' }))
  expect(select).toHaveBeenLastCalledWith('nodes', 1, 'select')
  expect(screen.getByRole('button', { name: 'Node 1' })).toHaveAttribute('aria-pressed', 'true')
  fireEvent.click(screen.getByRole('button', { name: 'New node' }))
  expect(create).toHaveBeenCalledWith('nodes')
  expect(screen.getByRole('button', { name: 'Node 1' })).toHaveAttribute('aria-pressed', 'false')
  expect(screen.getByText('Drawing mode · Esc to select')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Finish drawing' }))
  expect(screen.getByRole('button', { name: 'New node' })).toBeVisible()
})
it('searches object details, retains category filters and restores focus after clearing', () => {
  setup()
  fireEvent.change(screen.getByRole('textbox', { name: 'Find members' }), { target: { value: 'N1 → N5' } })
  expect(screen.getByRole('button', { name: 'Member 1' })).toBeVisible()
  expect(screen.queryByRole('button', { name: 'Member 2' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Nodes' }))
  fireEvent.click(screen.getByRole('button', { name: 'Members' }))
  expect(screen.getByRole('textbox', { name: 'Find members' })).toHaveValue('N1 → N5')
  fireEvent.change(screen.getByRole('textbox', { name: 'Find members' }), { target: { value: 'missing' } })
  expect(screen.getByText('No matches')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Clear entity search' }))
  expect(screen.getByRole('textbox', { name: 'Find members' })).toHaveFocus()
  expect(screen.getByRole('button', { name: 'Member 8' })).toBeVisible()
})
it('keeps categories usable when collapsed and reopens the selected group', () => {
  setup()
  fireEvent.click(screen.getByRole('button', { name: 'Collapse object list' }))
  expect(screen.queryByRole('textbox', { name: 'Find members' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Materials' }))
  expect(screen.getByRole('textbox', { name: 'Find materials' })).toBeVisible()
  expect(screen.getByRole('button', { name: 'Materials' })).toHaveAttribute('aria-pressed', 'true')
})
it('opens material, support and distributed-load assignments in the correct editor context', () => {
  const model = example3D()
  model.distributed_loads = [{ element_id: 1, coordinate_system: 'global', qx_i: 0, qy_i: 0, qz_i: -1000, mx_i: 0, qx_j: 0, qy_j: 0, qz_j: -1000, mx_j: 0 }]
  const { select } = setup(model)
  fireEvent.click(screen.getByRole('button', { name: 'Materials' }))
  fireEvent.click(screen.getByRole('button', { name: 'Member 1' }))
  expect(select).toHaveBeenLastCalledWith('elements', 1, 'material')
  fireEvent.click(screen.getByRole('button', { name: 'Supports' }))
  fireEvent.click(screen.getByRole('button', { name: 'Node 1' }))
  expect(select).toHaveBeenLastCalledWith('nodes', 1, 'support')
  fireEvent.click(screen.getByRole('button', { name: 'Loads' }))
  fireEvent.click(screen.getByRole('button', { name: 'Member 1' }))
  expect(select).toHaveBeenLastCalledWith('elements', 1, 'load')
})
it('bounds long lists while keeping selected rows reachable and expands without duplicates', () => {
  const model: Model3D = { ...blankModel(), nodes: Array.from({ length: 130 }, (_, index) => ({ id: index + 1, x: index, y: 0, z: 0 })) }
  setup(model, { nodes: [130], elements: [] })
  fireEvent.click(screen.getByRole('button', { name: 'Nodes' }))
  const list = screen.getByRole('list', { name: 'Nodes objects' })
  expect(within(list).getAllByRole('button')).toHaveLength(61)
  expect(screen.getByRole('button', { name: 'Node 130' })).toHaveAttribute('aria-pressed', 'true')
  fireEvent.click(screen.getByRole('button', { name: 'Show more (69)' }))
  expect(within(list).getAllByRole('button')).toHaveLength(121)
  fireEvent.click(screen.getByRole('button', { name: 'Show more (9)' }))
  expect(within(list).getAllByRole('button')).toHaveLength(130)
})
it('gives useful empty states and table entry for an empty document', () => {
  setup(blankModel())
  expect(screen.getByText('No members yet')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Supports' }))
  expect(screen.getByText('No supports yet')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Tables & analysis' }))
  expect(screen.getByRole('button', { name: 'Open model tables' })).toBeVisible()
})
