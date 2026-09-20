import type { Vec3, Plane } from './model'
export type Camera = { azimuth: number; elevation: number }
export type Basis = [Vec3, Vec3, Vec3]
export function basis(camera: Camera, plane?: Plane): Basis {
  if (plane === 'XY') return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
  if (plane === 'XZ') return [[1, 0, 0], [0, 0, 1], [0, -1, 0]]
  if (plane === 'YZ') return [[0, 1, 0], [0, 0, 1], [1, 0, 0]]
  const a = camera.azimuth; const e = camera.elevation
  return [[Math.cos(a), Math.sin(a), 0], [-Math.sin(a) * Math.sin(e), Math.cos(a) * Math.sin(e), Math.cos(e)], [Math.sin(a) * Math.cos(e), -Math.cos(a) * Math.cos(e), Math.sin(e)]]
}
export function project(p: Vec3, axes: Basis): Vec3 { return axes.map(row => row.reduce((s, v, i) => s + v * p[i], 0)) as Vec3 }
export function unproject(a: number, b: number, axes: Basis, plane: Plane, offset: number): Vec3 | null {
  const indices = plane === 'XY' ? [0, 1, 2] : plane === 'XZ' ? [0, 2, 1] : [1, 2, 0]
  const [i, j, k] = indices; const [u, v] = axes
  const det = u[i] * v[j] - u[j] * v[i]
  if (Math.abs(det) < .015) return null
  const aa = a - u[k] * offset; const bb = b - v[k] * offset
  const p: Vec3 = [0, 0, 0]; p[k] = offset; p[i] = (aa * v[j] - bb * u[j]) / det; p[j] = (bb * u[i] - aa * v[i]) / det
  return p
}
