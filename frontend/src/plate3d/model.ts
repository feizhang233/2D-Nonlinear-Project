import type { ApiSchemas } from '../generated/api'
import type { Vec3 as Vec } from '../spatial/vector'
export type { Vec }
export type PlateDof = ApiSchemas['PlateConstraint-Output']['dof']
export type PlateModel = ApiSchemas['PlateModel-Output']
export type PlateResult = ApiSchemas['PlateResult']
import { dot } from '../spatial/vector'
export { cross, dot } from '../spatial/vector'

export function localNodes(m: PlateModel) {
  return m.nodes.map((n) => {
    const v = [
      n.x - m.plane.origin[0],
      n.y - m.plane.origin[1],
      n.z - m.plane.origin[2],
    ] as Vec
    return { id: n.id, x: dot(v, m.plane.ex), y: dot(v, m.plane.ey) }
  })
}
export function edgeNodes(m: PlateModel, edge: string): number[] {
  const nodes = localNodes(m)
  const axis = edge[0] as 'x' | 'y'
  const values = nodes.map((n) => n[axis])
  const low = Math.min(...values),
    high = Math.max(...values)
  const at = edge[1] === '+' ? high : low
  return nodes
    .filter((n) => Math.abs(n[axis] - at) <= Math.max(high - low, 1e-20) * 1e-8)
    .map((n) => n.id)
}
export function rectangularPlate(
  a = 2,
  b = 1,
  nx = 8,
  ny = 4,
  tilt = 25,
  yaw = 15,
  origin: Vec = [0, 0, 0],
): PlateModel {
  if (
    ![a, b, nx, ny, tilt, yaw, ...origin].every(Number.isFinite) ||
    a <= 0 ||
    b <= 0 ||
    !Number.isInteger(nx) ||
    !Number.isInteger(ny) ||
    nx < 1 ||
    ny < 1
  )
    throw new Error('Enter positive dimensions and whole-number divisions.')
  if ((nx + 1) * (ny + 1) > 200)
    throw new Error('Use at most 200 nodes. Reduce mesh divisions.')
  const t = (tilt * Math.PI) / 180,
    z = (yaw * Math.PI) / 180
  const ex: Vec = [Math.cos(z), Math.sin(z), 0],
    ey: Vec = [
      -Math.sin(z) * Math.cos(t),
      Math.cos(z) * Math.cos(t),
      Math.sin(t),
    ]
  const nodes: PlateModel['nodes'] = [],
    elements: PlateModel['elements'] = []
  for (let j = 0; j <= ny; j++)
    for (let i = 0; i <= nx; i++) {
      const v = ex.map(
        (v, k) => origin[k] + (v * a * i) / nx + (ey[k] * b * j) / ny,
      )
      nodes.push({ id: j * (nx + 1) + i + 1, x: v[0], y: v[1], z: v[2] })
    }
  for (let j = 0; j < ny; j++)
    for (let i = 0; i < nx; i++) {
      const k = j * (nx + 1) + i + 1
      elements.push({
        id: elements.length + 1,
        nodes: [k, k + 1, k + nx + 2, k + nx + 1],
      })
    }
  return {
    schema_version: 'plate3d-1',
    name: 'Spatial plate',
    plane: { origin: [...origin], ex, ey },
    material: { E: 210e9, nu: 0.3, thickness: 0.05, shear_factor: 5 / 6 },
    nodes,
    elements,
    constraints: [],
    nodal_loads: [],
    pressures: [],
  }
}
function setEdgeSupport(
  m: PlateModel,
  edge: string,
  kind: 'clamped' | 'hard' | 'soft' | 'free',
  value = 0,
): PlateModel {
  const ids = edgeNodes(m, edge)
  const constraints = m.constraints.filter((c) => !ids.includes(c.node_id))
  const dofs: PlateDof[] =
    kind === 'clamped'
      ? ['w', 'theta_x', 'theta_y']
      : kind === 'hard'
        ? ['w', edge[0] === 'x' ? 'theta_y' : 'theta_x']
        : kind === 'soft'
          ? ['w']
          : []
  ids.forEach((node_id) =>
    dofs.forEach((dof) =>
      constraints.push({ node_id, dof, value: dof === 'w' ? value : 0 }),
    ),
  )
  return { ...m, constraints }
}
export function examplePlate(): PlateModel {
  let m = rectangularPlate()
  m.name = 'Inclined cantilever plate'
  m = setEdgeSupport(m, 'x-', 'clamped')
  m.pressures = m.elements.map((e) => ({ element_id: e.id, value: -1000 }))
  return m
}
/** Defensive local import/storage check. Host validation additionally checks every Q4 mapping. */
export function parsePlate(value: unknown): PlateModel {
  const m = value as PlateModel
  const finite = (v: unknown): v is number =>
    typeof v === 'number' && Number.isFinite(v)
  const vec = (v: unknown): v is Vec =>
    Array.isArray(v) && v.length === 3 && v.every(finite)
  const id = (v: unknown) =>
    typeof v === 'number' && Number.isInteger(v) && v > 0
  if (
    !m ||
    m.schema_version !== 'plate3d-1' ||
    typeof m.name !== 'string' ||
    !m.name.trim() ||
    m.name.length > 120 ||
    !Array.isArray(m.nodes) ||
    m.nodes.length < 4 ||
    m.nodes.length > 200 ||
    !Array.isArray(m.elements) ||
    !m.elements.length ||
    m.elements.length > 400 ||
    !Array.isArray(m.constraints) ||
    m.constraints.length > 600 ||
    !Array.isArray(m.nodal_loads) ||
    m.nodal_loads.length > 1200 ||
    !Array.isArray(m.pressures) ||
    m.pressures.length > 1200
  )
    throw new Error('Open a plate3d-1 project with a coplanar Q4 mesh.')
  if (
    !m.plane ||
    ![m.plane.origin, m.plane.ex, m.plane.ey].every(vec) ||
    Math.abs(dot(m.plane.ex, m.plane.ex) - 1) > 1e-10 ||
    Math.abs(dot(m.plane.ey, m.plane.ey) - 1) > 1e-10 ||
    Math.abs(dot(m.plane.ex, m.plane.ey)) > 1e-10
  )
    throw new Error('Plate axes must be orthogonal unit vectors.')
  const mat = m.material
  if (
    !mat ||
    ![mat.E, mat.nu, mat.thickness, mat.shear_factor].every(finite) ||
    mat.E <= 0 ||
    mat.nu <= -1 ||
    mat.nu >= 0.5 ||
    mat.thickness <= 0 ||
    mat.shear_factor <= 0
  )
    throw new Error('Check material, thickness and shear factor.')
  if (
    m.nodes.some((n) => !n || !id(n.id) || ![n.x, n.y, n.z].every(finite)) ||
    m.elements.some((e) => !e || !id(e.id))
  )
    throw new Error('Each entity needs a positive ID and finite coordinates.')
  const ns = new Set(m.nodes.map((n) => n.id)),
    es = new Set(m.elements.map((e) => e.id)),
    used = new Set<number>(),
    cells = new Set<string>()
  if (ns.size !== m.nodes.length || es.size !== m.elements.length)
    throw new Error('Node and element IDs must be unique.')
  for (const e of m.elements) {
    if (
      !Array.isArray(e.nodes) ||
      e.nodes.length !== 4 ||
      new Set(e.nodes).size !== 4 ||
      e.nodes.some((n) => !ns.has(n))
    )
      throw new Error('Each element needs four distinct existing nodes.')
    e.nodes.forEach((n) => used.add(n))
    const key = [...e.nodes].sort((a, b) => a - b).join(',')
    if (cells.has(key))
      throw new Error('Duplicate plate elements are not allowed.')
    cells.add(key)
  }
  if (used.size !== ns.size) throw new Error('Remove unused nodes.')
  const cs = new Map<string, number>()
  for (const c of m.constraints) {
    if (
      !c ||
      !ns.has(c.node_id) ||
      !['w', 'theta_x', 'theta_y'].includes(c.dof) ||
      !finite(c.value)
    )
      throw new Error('Check support nodes and values.')
    const key = `${c.node_id}.${c.dof}`
    if (cs.has(key) && cs.get(key) !== c.value)
      throw new Error('Conflicting prescribed values.')
    cs.set(key, c.value)
  }
  if (
    m.nodal_loads.some((l) => !l || !ns.has(l.node_id) || !vec(l.value)) ||
    m.pressures.some((p) => !p || !es.has(p.element_id) || !finite(p.value))
  )
    throw new Error('Check load references and finite values.')
  return structuredClone(m)
}
