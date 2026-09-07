import type { JsonValue, ModelInput, SolveResult } from './domain'
import { elementRecords } from './resultUtils'

export type FrameQuantity = 'moment' | 'shear' | 'axial'
export interface FrameStation { ratio: number; x: number; axial: number; shear: number; moment: number }
export interface FrameDiagram { elementId: string; stations: FrameStation[]; memberLoads: boolean }
export const frameQuantityLabels = { moment: 'Moment M', shear: 'Shear V', axial: 'Axial N' }

/** Basic corotational end actions. Distributed-load recovery is in reference local axes. */
export function frameDiagrams(model: ModelInput, result: SolveResult | null): FrameDiagram[] {
  if (model.model_family !== 'frame' || !result) return []
  const records = new Map(elementRecords(result).map(record => [String(record.element_id), record]))
  const accepted = result.steps.filter(step => step.status === 'accepted').at(-1)
  if (!accepted) return []
  return model.elements.flatMap(element => {
    const record = records.get(element.id)
    const forces = record?.local_end_forces
    if (!Array.isArray(forces) || forces.length !== 6 || !forces.every(v => typeof v === 'number' && Number.isFinite(v))) return []
    const [a, b] = element.node_ids.map(id => model.nodes.find(node => node.id === id))
    if (!a || !b) return []
    const referenceLength = Math.hypot(b.coordinates[0] - a.coordinates[0], b.coordinates[1] - a.coordinates[1])
    const memberLoads = model.loads.filter(load => (load.kind === 'element' || load.kind === 'edge') && load.element_id === element.id)
    const current = record?.current_configuration as Record<string, JsonValue> | undefined
    const length = memberLoads.length ? referenceLength : Number(current?.length ?? referenceLength)
    if (!(length > 0) || !Number.isFinite(length)) return []
    let qx0 = 0, qx1 = 0, qy0 = 0, qy1 = 0
    for (const load of memberLoads) {
      const factor = (load.scale ?? 1) * accepted.load_factor
      qx0 += factor * Number(load.components.qx_i ?? load.components.UX ?? 0)
      qx1 += factor * Number(load.components.qx_j ?? load.components.qx_i ?? load.components.UX ?? 0)
      qy0 += factor * Number(load.components.qy_i ?? load.components.UY ?? 0)
      qy1 += factor * Number(load.components.qy_j ?? load.components.qy_i ?? load.components.UY ?? 0)
    }
    // Subtract the consistent member-load vector, not any attached nodal load.
    const axialI = Number(forces[0]) - length * (2 * qx0 + qx1) / 6
    const momentI = Number(forces[2]) - length ** 2 * (3 * qy0 + 2 * qy1) / 60
    const momentJ = Number(forces[5]) + length ** 2 * (2 * qy0 + 3 * qy1) / 60
    const slope = (momentI + momentJ) / length
    const at = (ratio: number): FrameStation => {
      const x = ratio * length
      return { ratio, x,
        axial: -axialI - qx0 * x - (qx1 - qx0) * x ** 2 / (2 * length),
        shear: slope + qy0 * (x - length / 2) + (qy1 - qy0) * (3 * x ** 2 - length ** 2) / (6 * length),
        moment: -momentI + slope * x + qy0 * (x ** 2 - length * x) / 2 + (qy1 - qy0) * (x ** 3 - length ** 2 * x) / (6 * length),
      }
    }
    const ratios = new Set(Array.from({ length: 25 }, (_, index) => index / 24))
    // Include exact interior bending extrema (V = 0), not only uniform samples.
    const c = at(0).shear, qa = (qy1 - qy0) / (2 * length)
    const roots = Math.abs(qa) < 1e-14 ? (qy0 ? [-c / qy0] : []) : (() => {
      const disc = qy0 ** 2 - 4 * qa * c
      return disc < 0 ? [] : [(-qy0 + Math.sqrt(disc)) / (2 * qa), (-qy0 - Math.sqrt(disc)) / (2 * qa)]
    })()
    for (const x of roots) if (x > 0 && x < length) ratios.add(x / length)
    const stations = [...ratios].sort((a, b) => a - b).map(at)
    return stations.every(point => Object.values(point).every(Number.isFinite))
      ? [{ elementId: element.id, stations, memberLoads: memberLoads.length > 0 }] : []
  })
}
