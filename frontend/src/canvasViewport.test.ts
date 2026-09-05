import { describe, expect, it } from 'vitest'
import { clientToSvg, fitCamera, gridInterval, projectPoint, unprojectPoint, zoomCamera } from './canvasViewport'

describe('engineering viewport', () => {
  const viewport = { width: 1000, height: 560 }
  it('accounts for tall and wide SVG letterboxing', () => {
    expect(clientToSvg({ x: 250, y: 388 }, { left: 0, top: 0, width: 500, height: 720 }, viewport)).toEqual({ x: 500, y: 336 })
    expect(clientToSvg({ x: 500, y: 140 }, { left: 0, top: 0, width: 1000, height: 280 }, viewport)).toEqual({ x: 500, y: 280 })
  })
  it('round trips physical coordinates and keeps zoom anchored to the pointer', () => {
    const camera = fitCamera([{ x: -2, y: -1 }, { x: 2, y: 3 }], viewport)
    const world = { x: -0.42, y: 1.23 }
    const screen = projectPoint(world, camera, viewport)
    const zoomed = zoomCamera(camera, 1.5, screen, viewport)
    expect(unprojectPoint(screen, zoomed, viewport).x).toBeCloseTo(world.x)
    expect(unprojectPoint(screen, zoomed, viewport).y).toBeCloseTo(world.y)
    expect(projectPoint(world, zoomed, viewport).x).toBeCloseTo(screen.x)
  })
  it('fits empty and degenerate models without infinities', () => {
    for (const points of [[], [{ x: 4, y: 4 }], [{ x: NaN, y: 2 }]]) {
      const camera = fitCamera(points, viewport)
      expect(Number.isFinite(camera.scale)).toBe(true)
      expect(camera.scale).toBeGreaterThan(0)
    }
    expect(gridInterval(100)).toBe(1)
    expect(gridInterval(1000)).toBe(0.1)
  })
})
