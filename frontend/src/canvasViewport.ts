export interface Point { x: number; y: number }
export interface Viewport { width: number; height: number }
export interface Camera extends Point { scale: number }

export function fitCamera(points: Point[], viewport: Viewport): Camera {
  const valid = points.filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y))
  if (!valid.length) return { x: 0, y: 0, scale: 100 }
  const xs = valid.map((point) => point.x)
  const ys = valid.map((point) => point.y)
  const minX = Math.min(...xs), maxX = Math.max(...xs)
  const minY = Math.min(...ys), maxY = Math.max(...ys)
  const span = Math.max(maxX - minX, maxY - minY, 1)
  return {
    x: (minX + maxX) / 2,
    y: (minY + maxY) / 2,
    scale: Math.min(
      Math.max(80, viewport.width - 160) / Math.max(maxX - minX, span * 0.05),
      Math.max(80, viewport.height - 180) / Math.max(maxY - minY, span * 0.05),
    ),
  }
}

export const projectPoint = (point: Point, camera: Camera, viewport: Viewport): Point => ({
  x: viewport.width / 2 + (point.x - camera.x) * camera.scale,
  y: viewport.height / 2 - (point.y - camera.y) * camera.scale,
})

export const unprojectPoint = (point: Point, camera: Camera, viewport: Viewport): Point => ({
  x: camera.x + (point.x - viewport.width / 2) / camera.scale,
  y: camera.y - (point.y - viewport.height / 2) / camera.scale,
})

// SVG defaults to xMidYMid meet: do not treat letterboxing as drawable coordinates.
export function clientToSvg(point: Point, rect: { left: number; top: number; width: number; height: number }, viewport: Viewport): Point {
  const scale = Math.min(rect.width / viewport.width, rect.height / viewport.height) || 1
  return {
    x: (point.x - rect.left - (rect.width - viewport.width * scale) / 2) / scale,
    y: (point.y - rect.top - (rect.height - viewport.height * scale) / 2) / scale,
  }
}

export function zoomCamera(camera: Camera, factor: number, anchor: Point, viewport: Viewport): Camera {
  const world = unprojectPoint(anchor, camera, viewport)
  const scale = Math.min(1e9, Math.max(1e-6, camera.scale * factor))
  return {
    x: world.x - (anchor.x - viewport.width / 2) / scale,
    y: world.y + (anchor.y - viewport.height / 2) / scale,
    scale,
  }
}

export function gridInterval(scale: number): number {
  const raw = 60 / scale
  const power = 10 ** Math.floor(Math.log10(raw))
  return [1, 2, 5, 10].find((value) => value * power >= raw)! * power
}
