// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { SpatialCanvas } from './SpatialCanvas'
import { SurfaceCanvas, type SurfaceFace } from './SurfaceCanvas'
import { emptySelection, example3D } from './model'
import * as projection from './projection'

beforeEach(() => {
  vi.stubGlobal('PointerEvent', MouseEvent)
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue({
    x: 0, y: 0, left: 0, top: 0, width: 600, height: 600,
    right: 600, bottom: 600, toJSON: () => ({}),
  })
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

const frameProps = () => ({
  model: example3D(), selection: emptySelection(), tool: 'select' as const,
  plane: 'XY' as const, offset: 0, grid: 1, snap: true, spatial: false,
  chain: null, fitKey: 0, result: null, display: 'model' as const,
  deformationScale: 1, labels: true,
  onSelect: vi.fn(), onPoint: vi.fn(), onEnd: vi.fn(), onMessage: vi.fn(),
})

it('tracks selection-mode coordinates without recalculating the frame projection', () => {
  const calculateAxes = vi.spyOn(projection, 'basis')
  const { container } = render(<SpatialCanvas {...frameProps()} />)
  const canvas = screen.getByRole('img')
  const readout = container.querySelector('.canvas-coordinate-readout')!
  const initialCalculations = calculateAxes.mock.calls.length
  expect(readout.textContent).toContain('0 selected')
  fireEvent.pointerMove(canvas, { clientX: 100, clientY: 200 })
  const firstCoordinates = readout.textContent
  expect(firstCoordinates).toMatch(/X .*Y .*Z /)
  fireEvent.pointerMove(canvas, { clientX: 500, clientY: 400 })
  expect(readout.textContent).not.toBe(firstCoordinates)
  expect(calculateAxes).toHaveBeenCalledTimes(initialCalculations)
  fireEvent.pointerLeave(canvas)
  expect(readout.textContent).toContain('0 selected')
})

it('keeps live member previews and clears them when returning to selection', () => {
  const config = frameProps()
  const { container, rerender } = render(
    <SpatialCanvas {...config} tool="member" chain={1} />,
  )
  fireEvent.pointerMove(screen.getByRole('img'), { clientX: 400, clientY: 200 })
  expect(container.querySelector('.spatial-preview path')).toBeTruthy()
  expect(container.querySelector('.canvas-coordinate-readout')!.textContent).toMatch(/X .*Y .*Z /)
  rerender(<SpatialCanvas {...config} />)
  expect(container.querySelector('.spatial-preview')).toBeNull()
})

it('keeps undeformed reference faces correct for sparse node IDs and model edits', () => {
  const config = {
    model: {
      nodes: [{ id: 10, x: 0, y: 0, z: 0 }, { id: 30, x: 2, y: 0, z: 0 },
        { id: 50, x: 2, y: 1, z: 0 }, { id: 90, x: 0, y: 1, z: 0 }],
      elements: [{ id: 7 }], constraints: [],
    },
    boundaries: [{ element: 7, face: 0, nodes: [10, 30, 50, 90] }] satisfies SurfaceFace[],
    displacementRows: [], values: new Map<number, number>(), loads: [],
    hasResult: true, showContour: false, quantityLabel: 'Mesh', meshLabel: 'Test mesh',
    unit: 'm', contourCaption: '', scale: 1, selection: null, onSelect: vi.fn(),
  }
  const { container, rerender } = render(<SurfaceCanvas {...config} />)
  const reference = () => container.querySelector('polygon[stroke-dasharray="4 4"]')!
  const initialPoints = reference().getAttribute('points')!
  expect(initialPoints).not.toMatch(/NaN|undefined/)
  expect(initialPoints.split(' ')).toHaveLength(4)
  rerender(<SurfaceCanvas {...config} model={{ ...config.model,
    nodes: config.model.nodes.map(node => node.id === 30 ? { ...node, z: 1 } : node),
  }} />)
  expect(reference().getAttribute('points')).not.toBe(initialPoints)
  expect(reference().getAttribute('points')).not.toMatch(/NaN|undefined/)
})
