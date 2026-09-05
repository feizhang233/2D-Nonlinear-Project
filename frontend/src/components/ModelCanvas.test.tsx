// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cloneSampleModel } from '../sampleModel'
import { ModelCanvas } from './ModelCanvas'

const props = () => ({
  model: cloneSampleModel('frame'), result: null, selectedStep: 0, view: 'model' as const,
  selection: { kind: 'model' as const }, cadTool: 'select' as const, placement: null, pendingMember: null,
  onViewChange: vi.fn(), onSelection: vi.fn(), onModelChange: vi.fn(), onPlace: vi.fn(), onPendingMember: vi.fn(),
})

describe('canvas direct manipulation', () => {
  beforeEach(() => {
    vi.stubGlobal('PointerEvent', MouseEvent)
    vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue({ x: 0, y: 0, left: 0, top: 0, width: 1000, height: 560, bottom: 560, right: 1000, toJSON: () => ({}) })
  })
  afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

  it('ignores pointer jitter, previews a drag, and commits once on release', () => {
    const config = props()
    render(<ModelCanvas {...config} />)
    const svg = screen.getByRole('group', { name: 'Frame 2D engineering projection' })
    const node = screen.getByRole('button', { name: 'Select Node 2' })
    const x = Number(node.getAttribute('cx')), y = Number(node.getAttribute('cy'))
    fireEvent.pointerDown(node, { clientX: x, clientY: y, button: 0 })
    fireEvent.pointerMove(svg, { clientX: x + 1, clientY: y + 1 })
    expect(config.onModelChange).not.toHaveBeenCalled()
    fireEvent.pointerMove(svg, { clientX: x + 84, clientY: y - 42 })
    expect(config.onModelChange).not.toHaveBeenCalled()
    expect(Number(node.getAttribute('cx'))).toBeCloseTo(x + 84)
    fireEvent.pointerUp(svg, { clientX: x + 84, clientY: y - 42 })
    expect(config.onModelChange).toHaveBeenCalledTimes(1)
    expect(config.onModelChange.mock.calls[0][0].nodes[1].coordinates[0]).toBeCloseTo(config.model.nodes[1].coordinates[0] + 0.2)
  })

  it('rolls back a cancelled drag and supports zoom and fit without changing the model', () => {
    const config = props()
    render(<ModelCanvas {...config} />)
    const svg = screen.getByRole('group', { name: 'Frame 2D engineering projection' })
    const node = screen.getByRole('button', { name: 'Select Node 2' })
    fireEvent.pointerDown(node, { clientX: 500, clientY: 280, button: 0 })
    fireEvent.pointerMove(svg, { clientX: 560, clientY: 260 })
    fireEvent.pointerCancel(svg)
    expect(config.onModelChange).not.toHaveBeenCalled()
    const left = screen.getByRole('button', { name: 'Select Node 1' })
    const initialX = Number(left.getAttribute('cx'))
    fireEvent.click(screen.getByRole('button', { name: 'Zoom in' }))
    expect(Number(left.getAttribute('cx'))).toBeLessThan(initialX)
    fireEvent.click(screen.getByRole('button', { name: 'Fit model' }))
    expect(Number(left.getAttribute('cx'))).toBeCloseTo(initialX)
  })

  it('keeps result meshes selectable without editable geometry overlays', () => {
    const config = { ...props(), model: cloneSampleModel('plate'), readOnly: true }
    render(<ModelCanvas {...config} />)
    expect(screen.queryByRole('button', { name: /Geometry vertex/ })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Select Node 1' }))
    expect(config.onSelection).toHaveBeenCalledWith({ kind: 'nodes', id: config.model.nodes[0].id })
    expect(config.onModelChange).not.toHaveBeenCalled()
  })
})
