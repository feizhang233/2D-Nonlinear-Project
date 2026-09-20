import { SurfaceCanvas, type SurfaceSelection } from '../spatial/SurfaceCanvas'
import { cross, type PlateModel, type PlateResult, type Vec } from './model'
export type Quantity =
  | 'w'
  | 'mx'
  | 'my'
  | 'mxy'
  | 'qx'
  | 'qy'
  | 'sxx'
  | 'syy'
  | 'txy'
  | 'mesh'
export const quantities: Record<Quantity, { label: string; unit: string }> = {
  w: { label: 'Normal displacement |w|', unit: 'm' },
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
export function PlateCanvas({
  model,
  result,
  quantity,
  scale,
  selection,
  onSelect,
  selectable = true,
}: {
  selectable?: boolean
  model: PlateModel
  result: PlateResult | null
  quantity: Quantity
  scale: number
  selection: SurfaceSelection
  onSelect: (s: SurfaceSelection) => void
}) {
  const normal = cross(model.plane.ex, model.plane.ey),
    displacements = new Map(
      result?.nodes.map((n) => [n.node_id, n.displacement]) ?? [],
    )
  const position = (id: number): Vec => {
    const n = model.nodes.find((n) => n.id === id)!
    const u = displacements.get(id) ?? [0, 0, 0]
    return [n.x + scale * u[0], n.y + scale * u[1], n.z + scale * u[2]]
  }
  const values = new Map(
    result?.elements.map((e) => [
      e.element_id,
      e.points.reduce(
        (s, p) =>
          s +
          (quantity === 'mx'
            ? p.moment[0]
            : quantity === 'my'
              ? p.moment[1]
              : quantity === 'mxy'
                ? p.moment[2]
                : quantity === 'qx'
                  ? p.shear[0]
                  : quantity === 'qy'
                    ? p.shear[1]
                    : quantity === 'sxx'
                      ? p.stress_top[0]
                      : quantity === 'syy'
                        ? p.stress_top[1]
                        : quantity === 'txy'
                          ? p.stress_top[2]
                          : 0),
        0,
      ) / e.points.length,
    ]) ?? [],
  )
  const loads = model.nodal_loads
    .filter((l) => l.value[0] !== 0)
    .map((l) => ({
      position: position(l.node_id),
      force: normal.map((v) => v * l.value[0]) as Vec,
    }))
  for (const p of model.pressures) {
    const e = model.elements.find((e) => e.id === p.element_id)!
    loads.push({
      position: [0, 1, 2].map(
        (j) => e.nodes.reduce((s, id) => s + position(id)[j], 0) / 4,
      ) as Vec,
      force: normal.map((v) => v * p.value) as Vec,
    })
  }
  const moments = model.nodal_loads
    .filter((l) => l.value[1] !== 0 || l.value[2] !== 0)
    .map((l) => ({
      position: position(l.node_id),
      value: model.plane.ex.map(
        (v, k) => v * l.value[2] - model.plane.ey[k] * l.value[1],
      ) as Vec,
    }))
  return (
    <SurfaceCanvas
      selectable={selectable}
      localFrame={model.plane}
      moments={moments}
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
      hasResult={!!result}
      showContour={quantity !== 'mesh'}
      quantityLabel={quantities[quantity].label}
      meshLabel="Spatial plate · MITC4"
      unit={quantities[quantity].unit}
      contourCaption={
        quantity === 'w'
          ? 'Element mean of nodal |w|'
          : 'Local axes · element mean · raw points in tables'
      }
      scale={scale}
      selection={selection}
      onSelect={onSelect}
      displacementContour={quantity === 'w'}
    />
  )
}
