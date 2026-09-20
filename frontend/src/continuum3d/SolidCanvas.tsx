import { SurfaceCanvas } from '../spatial/SurfaceCanvas'
import {
  boundaryFaces,
  type SolidModel,
  type SolidResult,
  type Vec,
} from './model'
export type SolidSelection = { kind: 'node' | 'element'; id: number } | null
export type Quantity =
  | 'mesh'
  | 'displacement'
  | 'von_mises'
  | 'sxx'
  | 'syy'
  | 'szz'
  | 'txy'
  | 'tyz'
  | 'tzx'
export const quantityLabels: Record<Quantity, string> = {
  mesh: 'Deformed mesh',
  displacement: 'Displacement magnitude',
  von_mises: 'von Mises stress',
  sxx: 'Stress XX',
  syy: 'Stress YY',
  szz: 'Stress ZZ',
  txy: 'Shear XY',
  tyz: 'Shear YZ',
  tzx: 'Shear ZX',
}

export function SolidCanvas({
  model,
  result,
  quantity,
  scale,
  selection,
  onSelect,
}: {
  model: SolidModel
  result: SolidResult | null
  quantity: Quantity
  scale: number
  selection: SolidSelection
  onSelect: (s: SolidSelection) => void
}) {
  const boundaries = boundaryFaces(model)
  const displacements = new Map(
    result?.nodal_displacements.map((n) => [n.node_id, n.value]) ?? [],
  )
  const stressIndex = ['sxx', 'syy', 'szz', 'txy', 'tyz', 'tzx'].indexOf(
    quantity,
  )
  const values = new Map(
    result?.elements.map((e) => [
      e.element_id,
      e.points.reduce(
        (v, p) =>
          v +
          (quantity === 'von_mises'
            ? p.von_mises
            : (p.stress[stressIndex] ?? 0)),
        0,
      ) / e.points.length,
    ]) ?? [],
  )
  const loads = model.nodal_loads.map((l) => {
    const n = model.nodes.find((n) => n.id === l.node_id)!
    const u = displacements.get(n.id) ?? [0, 0, 0]
    return {
      position: [
        n.x + scale * u[0],
        n.y + scale * u[1],
        n.z + scale * u[2],
      ] as Vec,
      force: l.force,
    }
  })
  for (const l of model.tractions) {
    const face = boundaries.find(
      (f) => f.element === l.element_id && f.face === l.face,
    )
    if (face) {
      const position = [0, 1, 2].map(
        (j) =>
          face.nodes.reduce((sum, id) => {
            const n = model.nodes.find((n) => n.id === id)!
            return (
              sum +
              [n.x, n.y, n.z][j] +
              scale * (displacements.get(id)?.[j] ?? 0)
            )
          }, 0) / face.nodes.length,
      ) as Vec
      loads.push({ position, force: l.traction })
    }
  }
  return (
    <SurfaceCanvas
      model={model}
      boundaries={boundaries}
      displacementRows={result?.nodal_displacements ?? []}
      values={values}
      loads={loads}
      hasResult={!!result}
      showContour={quantity !== 'mesh'}
      quantityLabel={quantityLabels[quantity]}
      meshLabel="Solid mesh"
      unit={quantity === 'displacement' ? 'm' : 'Pa'}
      contourCaption={
        quantity === 'displacement'
          ? 'Face mean of nodal magnitudes'
          : 'Element mean · raw points in tables'
      }
      scale={scale}
      selection={selection}
      onSelect={onSelect}
      displacementContour={quantity === 'displacement'}
    />
  )
}
