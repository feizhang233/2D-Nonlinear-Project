import type { Dof, JsonValue, ModelFamily, ModelInput, ResultField, SolveResult, StepResult } from './domain'
import { dofsForModel, MODEL_FAMILIES } from './modelFamilies'

export const formatNumber = (value: unknown, digits = 4): string => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—'
  if (value === 0) return '0'
  if (Math.abs(value) >= 1e4 || Math.abs(value) < 1e-3) return value.toExponential(3)
  return value.toLocaleString('en-US', { maximumFractionDigits: digits })
}

export const getRawField = (result: SolveResult | null | undefined, name: string): ResultField | undefined =>
  result?.post_result?.raw_fields.find((field) => field.name === name)

export type DofValues = Partial<Record<Dof, number>>

const emptyDofValues = (dofs: Dof[]): DofValues => Object.fromEntries(dofs.map((dof) => [dof, 0])) as DofValues

export function displacementByNode(model: ModelInput, result: SolveResult | null | undefined, step?: StepResult) {
  const dofs = dofsForModel(model)
  const values = new Map<string, DofValues>()
  model.nodes.forEach((node) => values.set(node.id, emptyDofValues(dofs)))
  const finalStep = result?.steps.at(-1)
  if (step && (step !== finalStep || !getRawField(result, 'displacement')?.records.length) && Array.isArray(step.response.displacement)) {
    const vector = step.response.displacement as number[]
    model.nodes.forEach((node, nodeIndex) => {
      const record = emptyDofValues(dofs)
      dofs.forEach((dof, dofIndex) => { record[dof] = Number(vector[nodeIndex * dofs.length + dofIndex] ?? 0) })
      values.set(node.id, record)
    })
    return values
  }
  for (const record of getRawField(result, 'displacement')?.records ?? []) {
    const nodeId = String(record.node_id)
    const dof = String(record.dof) as Dof
    const current = values.get(nodeId)
    if (current && dofs.includes(dof)) current[dof] = Number(record.value ?? 0)
  }
  return values
}

export function reactionByNode(result: SolveResult | null | undefined) {
  const values = new Map<string, DofValues>()
  for (const record of getRawField(result, 'reaction')?.records ?? []) {
    const nodeId = String(record.node_id)
    const dof = String(record.dof) as Dof
    const current = values.get(nodeId) ?? {}
    current[dof] = Number(record.value ?? 0)
    values.set(nodeId, current)
  }
  return values
}

export const elementRecords = (result: SolveResult | null | undefined) =>
  getRawField(result, 'element_response')?.records ?? []

export function monitoredDofIndex(model: ModelInput): number {
  const dofs = dofsForModel(model)
  const target = model.analysis.displacement_control?.target
  if (target) {
    const nodeIndex = Math.max(0, model.nodes.findIndex((node) => node.id === target.node_id))
    const dofIndex = Math.max(0, dofs.indexOf(target.dof))
    return nodeIndex * dofs.length + dofIndex
  }
  for (const load of model.loads) {
    if (load.kind !== 'nodal' || !load.node_id) continue
    const dofIndex = dofs.findIndex((dof) => Math.abs(load.components[dof] ?? 0) > 0)
    if (dofIndex >= 0) {
      const nodeIndex = Math.max(0, model.nodes.findIndex((node) => node.id === load.node_id))
      return nodeIndex * dofs.length + dofIndex
    }
  }
  return Math.max(0, dofs.indexOf(MODEL_FAMILIES[model.model_family].primaryLoadDof))
}

export function loadDisplacementPoints(model: ModelInput, result: SolveResult | null | undefined) {
  const index = monitoredDofIndex(model)
  return (result?.steps ?? [])
    .filter((step) => step.status === 'accepted')
    .map((step) => {
      const vector = step.response.displacement
      const controlled = step.response.control_displacement
      return {
        x: Array.isArray(vector) ? Number(vector[index] ?? 0) : Number(controlled ?? 0),
        y: step.load_factor,
      }
    })
}

export const convergencePoints = (result: SolveResult | null | undefined) => {
  let sequence = 0
  return (result?.steps ?? []).flatMap((step) => step.iterations.map((iteration) => ({
    x: sequence++,
    y: Math.max(iteration.residual_norm, 1e-30),
    correction: Math.max(iteration.displacement_correction_norm, 1e-30),
    energy: Math.max(iteration.energy_norm, 1e-30),
  })))
}

const gaussVectors = (record: Record<string, JsonValue>, key: string): number[][] => {
  if (!Array.isArray(record.gauss_points)) return []
  return record.gauss_points.flatMap((point) => {
    if (!point || typeof point !== 'object' || Array.isArray(point)) return []
    const value = point[key]
    return Array.isArray(value) && value.every((item) => typeof item === 'number') ? [value as number[]] : []
  })
}

const averageComponent = (vectors: number[][], index: number) => vectors.length
  ? vectors.reduce((sum, vector) => sum + Number(vector[index] ?? 0), 0) / vectors.length
  : 0

const averageNorm = (vectors: number[][]) => vectors.length
  ? vectors.reduce((sum, vector) => sum + Math.hypot(...vector), 0) / vectors.length
  : 0

export const resultMetricLabels: Record<ModelFamily, string[]> = {
  frame: ['Axial force N', 'End moment Mᵢ', 'End moment Mⱼ'],
  continuum: ['σxx', 'σyy', 'τxy'],
  plate: ['‖N‖', '‖M‖', '‖Q‖'],
  shell: ['‖N‖', '‖M‖', '‖Q‖'],
}

export interface ElementResultSummary {
  elementId: string
  metrics: number[]
  energy: number
  qualifier?: string
}

export function elementResultSummary(family: ModelFamily, record: Record<string, JsonValue>): ElementResultSummary {
  if (family === 'frame') {
    const force = Array.isArray(record.local_end_forces) ? record.local_end_forces.map(Number) : []
    return { elementId: String(record.element_id), metrics: [force[3] ?? 0, force[2] ?? 0, force[5] ?? 0], energy: Number(record.energy ?? 0) }
  }
  if (family === 'continuum') {
    const cauchy = gaussVectors(record, 'cauchy')
    return {
      elementId: String(record.element_id),
      metrics: [averageComponent(cauchy, 0), averageComponent(cauchy, 1), averageComponent(cauchy, 2)],
      energy: Number(record.energy ?? 0),
      qualifier: 'Gauss average',
    }
  }
  const membrane = gaussVectors(record, 'membrane_resultant')
  const bending = gaussVectors(record, family === 'plate' ? 'bending_moment' : 'bending_resultant')
  const shear = gaussVectors(record, family === 'plate' ? 'shear_force' : 'shear_resultant')
  return {
    elementId: String(record.element_id),
    metrics: [averageNorm(membrane), averageNorm(bending), averageNorm(shear)],
    energy: Number(record.energy ?? 0),
    qualifier: 'Gauss average norm',
  }
}

export const elementResultScalar = (family: ModelFamily, record: Record<string, JsonValue>) =>
  Math.max(...elementResultSummary(family, record).metrics.map(Math.abs), 0)

export const elementInternalLabel = (family: ModelFamily, record: Record<string, JsonValue>) => {
  const summary = elementResultSummary(family, record)
  return resultMetricLabels[family].map((label, index) => `${label} ${formatNumber(summary.metrics[index])}`).join(' · ')
}

export function failureSuggestion(code?: string): string {
  switch (code) {
    case 'NONCONVERGENCE': return 'Reduce the step size, check supports and load directions, and compare residual, displacement-correction, and energy metrics.'
    case 'LINEAR_SOLVE_ERROR': return 'Check rigid-body DOFs, duplicate nodes, zero section/thickness parameters, and whether the model is sufficiently constrained.'
    case 'TANGENT_ERROR': return 'Check the current configuration, element geometry, material parameters, and whether the increment is too large.'
    case 'CONTROL_ERROR': return 'Check that the control DOF is valid and that the displacement increment or arc-length radius matches the target path.'
    case 'MODEL_ERROR': return 'Resolve entity references, units, or parameter issues reported by model validation first.'
    default: return 'Review the failure location, solver details, and last accepted step. Do not treat failed output as a valid solution.'
  }
}
