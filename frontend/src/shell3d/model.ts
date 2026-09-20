import type { ApiSchemas } from '../generated/api'
import { cross, type Vec3 as Vec } from '../spatial/vector'
export type { Vec }
export const dofs = ['ux', 'uy', 'uz', 'rx', 'ry', 'rz'] as const
export type ShellDof = ApiSchemas['ShellConstraint-Output']['dof']
export type ShellEnergy = ApiSchemas['ShellEnergy']
export type ShellModel = ApiSchemas['ShellModel-Output']
export type ShellResult = ApiSchemas['ShellResult']

export type MeshSettings = {
  length: number
  width: number
  nx: number
  ny: number
  fold: number
}
export const defaultMesh: MeshSettings = {
  length: 2,
  width: 1,
  nx: 4,
  ny: 4,
  fold: 45,
}
export function shellMesh(g: MeshSettings = defaultMesh): ShellModel {
  if (
    !Object.values(g).every(Number.isFinite) ||
    g.length <= 0 ||
    g.width <= 0 ||
    !Number.isInteger(g.nx) ||
    !Number.isInteger(g.ny) ||
    g.nx < 1 ||
    g.ny < 2 ||
    g.ny % 2 ||
    Math.abs(g.fold) >= 170 ||
    (g.nx + 1) * (g.ny + 1) > 100
  )
    throw new Error(
      'Use positive dimensions, an even transverse division count, a fold below 170°, and at most 100 nodes.',
    )
  const m: ShellModel = {
    schema_version: 'shell3d-1',
    name: 'Folded cantilever shell',
    material: {
      E: 210e9,
      nu: 0.3,
      thickness: 0.02,
      shear_factor: 5 / 6,
      alpha_d: 1e-4,
    },
    nodes: [],
    elements: [],
    constraints: [],
    nodal_loads: [],
    pressures: [],
  }
  const angle = (g.fold * Math.PI) / 180
  for (let j = 0; j <= g.ny; j++)
    for (let i = 0; i <= g.nx; i++) {
      const y = (g.width * j) / g.ny,
        beyond = Math.max(0, y - g.width / 2)
      m.nodes.push({
        id: j * (g.nx + 1) + i + 1,
        x: (g.length * i) / g.nx,
        y: y - beyond + beyond * Math.cos(angle),
        z: beyond * Math.sin(angle),
      })
    }
  for (let j = 0; j < g.ny; j++)
    for (let i = 0; i < g.nx; i++) {
      const n = j * (g.nx + 1) + i + 1
      m.elements.push({
        id: m.elements.length + 1,
        nodes: [n, n + 1, n + g.nx + 2, n + g.nx + 1],
      })
    }
  return m
}
export function targetNodes(
  m: ShellModel,
  target: string,
  selected?: number,
): number[] {
  if (target === 'selected') return selected ? [selected] : []
  if (target === 'boundary') {
    const counts = new Map<string, { a: number; b: number; count: number }>()
    m.elements.forEach((e) =>
      e.nodes.forEach((a, i) => {
        const b = e.nodes[(i + 1) % 4],
          key = [a, b].sort((x, y) => x - y).join(',')
        const v = counts.get(key)
        counts.set(key, { a, b, count: (v?.count ?? 0) + 1 })
      }),
    )
    return [
      ...new Set(
        [...counts.values()]
          .filter((v) => v.count === 1)
          .flatMap((v) => [v.a, v.b]),
      ),
    ]
  }
  const xs = m.nodes.map((n) => n.x),
    lo = Math.min(...xs),
    hi = Math.max(...xs),
    at = target === 'x+' ? hi : lo
  return m.nodes
    .filter((n) => Math.abs(n.x - at) <= Math.max(hi - lo, 1e-20) * 1e-8)
    .map((n) => n.id)
}
export function exampleShell(): ShellModel {
  const m = shellMesh()
  m.constraints = targetNodes(m, 'x-').flatMap((node_id) =>
    dofs.map((dof) => ({ node_id, dof, value: 0 })),
  )
  m.pressures = m.elements.map((e) => ({ element_id: e.id, value: -1000 }))
  return m
}
export function facetBasis(m: ShellModel, id: number): [Vec, Vec, Vec] {
  const e = m.elements.find((e) => e.id === id)!,
    p = e.nodes.map((id) => m.nodes.find((n) => n.id === id)!)
  const sub = (a: (typeof p)[number], b: (typeof p)[number]): Vec => [
    a.x - b.x,
    a.y - b.y,
    a.z - b.z,
  ]
  const unit = (a: Vec) => a.map((v) => v / Math.hypot(...a)) as Vec
  const ex = unit(sub(p[1], p[0])),
    ez = unit(cross(ex, sub(p[3], p[0])))
  return [ex, cross(ez, ex), ez]
}
/** Local structural checks; server validates planar facets and every Q4 mapping before import. */
export function parseShell(value: unknown): ShellModel {
  const m = value as ShellModel
  const finite = (v: unknown): v is number =>
    typeof v === 'number' && Number.isFinite(v)
  const vec = (v: unknown): v is Vec =>
    Array.isArray(v) && v.length === 3 && v.every(finite)
  const id = (v: unknown) =>
    typeof v === 'number' && Number.isInteger(v) && v > 0
  if (
    !m ||
    m.schema_version !== 'shell3d-1' ||
    typeof m.name !== 'string' ||
    !m.name.trim() ||
    m.name.length > 120 ||
    !Array.isArray(m.nodes) ||
    m.nodes.length < 4 ||
    m.nodes.length > 100 ||
    !Array.isArray(m.elements) ||
    !m.elements.length ||
    m.elements.length > 200 ||
    !Array.isArray(m.constraints) ||
    m.constraints.length > 600 ||
    !Array.isArray(m.nodal_loads) ||
    m.nodal_loads.length > 1200 ||
    !Array.isArray(m.pressures) ||
    m.pressures.length > 600
  )
    throw new Error(
      'Open a shell3d-1 project with a planar Q4 facet mesh (up to 100 nodes).',
    )
  const mat = m.material
  if (
    !mat ||
    ![mat.E, mat.nu, mat.thickness, mat.shear_factor, mat.alpha_d].every(
      finite,
    ) ||
    mat.E <= 0 ||
    mat.nu <= -1 ||
    mat.nu >= 0.5 ||
    mat.thickness <= 0 ||
    mat.shear_factor <= 0 ||
    mat.alpha_d < 1e-6 ||
    mat.alpha_d > 1e-2
  )
    throw new Error(
      'Check material, thickness and drilling factor (1e-6 to 1e-2).',
    )
  if (
    m.nodes.some((n) => !n || !id(n.id) || ![n.x, n.y, n.z].every(finite)) ||
    m.elements.some((e) => !e || !id(e.id))
  )
    throw new Error('Use positive IDs and finite node coordinates.')
  const ns = new Set(m.nodes.map((n) => n.id)),
    es = new Set(m.elements.map((e) => e.id)),
    used = new Set<number>(),
    cells = new Set<string>()
  if (ns.size !== m.nodes.length || es.size !== m.elements.length)
    throw new Error('Entity IDs must be unique.')
  for (const e of m.elements) {
    if (
      !Array.isArray(e.nodes) ||
      e.nodes.length !== 4 ||
      new Set(e.nodes).size !== 4 ||
      e.nodes.some((n) => !ns.has(n))
    )
      throw new Error('Each Q4 needs four distinct existing nodes.')
    e.nodes.forEach((n) => used.add(n))
    const key = [...e.nodes].sort((a, b) => a - b).join(',')
    if (cells.has(key))
      throw new Error('Duplicate shell facets are not allowed.')
    cells.add(key)
  }
  if (used.size !== ns.size) throw new Error('Remove unused nodes.')
  const cs = new Map<string, number>()
  for (const c of m.constraints) {
    if (!c || !ns.has(c.node_id) || !dofs.includes(c.dof) || !finite(c.value))
      throw new Error('Check support references and values.')
    const key = `${c.node_id}.${c.dof}`
    if (cs.has(key) && cs.get(key) !== c.value)
      throw new Error('Conflicting prescribed values.')
    cs.set(key, c.value)
  }
  if (
    m.nodal_loads.some(
      (l) => !l || !ns.has(l.node_id) || !vec(l.force) || !vec(l.moment),
    ) ||
    m.pressures.some((p) => !p || !es.has(p.element_id) || !finite(p.value))
  )
    throw new Error('Check load references and finite values.')
  return structuredClone(m)
}
