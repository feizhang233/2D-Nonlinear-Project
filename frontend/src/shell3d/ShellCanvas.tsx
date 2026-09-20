import { SurfaceCanvas, type SurfaceSelection } from '../spatial/SurfaceCanvas'
import {
  facetBasis,
  type ShellModel,
  type ShellResult,
  type Vec,
} from './model'
export const quantities = {
  displacement: { label: 'Displacement |U|', unit: 'm' },
  nx: { label: 'Membrane Nx', unit: 'N/m' },
  ny: { label: 'Membrane Ny', unit: 'N/m' },
  nxy: { label: 'Membrane Nxy', unit: 'N/m' },
  mx: { label: 'Moment Mx', unit: 'N·m/m' },
  my: { label: 'Moment My', unit: 'N·m/m' },
  mxy: { label: 'Twisting moment Mxy', unit: 'N·m/m' },
  qx: { label: 'Shear Qx', unit: 'N/m' },
  qy: { label: 'Shear Qy', unit: 'N/m' },
  sxx: { label: 'Top stress XX', unit: 'Pa' },
  syy: { label: 'Top stress YY', unit: 'Pa' },
  txy: { label: 'Top shear XY', unit: 'Pa' },
  mesh: { label: 'Deformed mesh', unit: '' },
}
export type Quantity = keyof typeof quantities
export function ShellCanvas({
  model,
  result,
  quantity,
  scale,
  selection,
  onSelect,
  selectable = true,
}: {
  model: ShellModel
  result: ShellResult | null
  quantity: Quantity
  scale: number
  selection: SurfaceSelection
  onSelect: (s: SurfaceSelection) => void
  selectable?: boolean
}) {
  const displacements = new Map(
    result?.nodes.map((n) => [n.node_id, n.displacement]) ?? [],
  )
  const position = (id: number): Vec => {
    const n = model.nodes.find((n) => n.id === id)!,
      u = displacements.get(id) ?? [0, 0, 0]
    return [n.x + scale * u[0], n.y + scale * u[1], n.z + scale * u[2]]
  }
  const field = (p: ShellResult['elements'][number]['points'][number]) =>
    ({
      nx: p.membrane[0],
      ny: p.membrane[1],
      nxy: p.membrane[2],
      mx: p.moment[0],
      my: p.moment[1],
      mxy: p.moment[2],
      qx: p.shear[0],
      qy: p.shear[1],
      sxx: p.stress_top[0],
      syy: p.stress_top[1],
      txy: p.stress_top[2],
      displacement: 0,
      mesh: 0,
    })[quantity]
  const values = new Map(
    result?.elements.map((e) => [
      e.element_id,
      e.points.reduce((s, p) => s + field(p), 0) / e.points.length,
    ]) ?? [],
  )
  const loads = model.nodal_loads.map((l) => ({
    position: position(l.node_id),
    force: l.force,
  }))
  for (const p of model.pressures) {
    const e = model.elements.find((e) => e.id === p.element_id)!,
      normal = facetBasis(model, e.id)[2]
    loads.push({
      position: [0, 1, 2].map(
        (j) => e.nodes.reduce((s, id) => s + position(id)[j], 0) / 4,
      ) as Vec,
      force: normal.map((v) => v * p.value) as Vec,
    })
  }
  const basis =
    selection?.kind === 'element' ? facetBasis(model, selection.id) : null
  return (
    <SurfaceCanvas
      model={model}
      boundaries={model.elements.map((e) => ({
        element: e.id,
        face: 0,
        nodes: e.nodes,
      }))}
      displacementRows={
        result?.nodes.map((n) => ({
          node_id: n.node_id,
          value: n.displacement,
        })) ?? []
      }
      values={values}
      loads={loads}
      moments={model.nodal_loads
        .filter((l) => l.moment.some((v) => v !== 0))
        .map((l) => ({ position: position(l.node_id), value: l.moment }))}
      localFrame={basis ? { ex: basis[0], ey: basis[1] } : undefined}
      hasResult={!!result}
      showContour={!!result && quantity !== 'mesh'}
      displacementContour={quantity === 'displacement'}
      quantityLabel={quantities[quantity].label}
      unit={quantities[quantity].unit}
      meshLabel="Shell Q4 facets"
      contourCaption={
        quantity === 'displacement'
          ? 'Element mean of nodal displacement magnitudes'
          : 'Raw Gauss-point mean · each element local axes'
      }
      scale={scale}
      selection={selection}
      onSelect={onSelect}
      selectable={selectable}
    />
  )
}
