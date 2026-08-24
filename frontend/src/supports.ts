import type { ConstraintInput, Dof, ModelInput } from './domain'

export type SupportClass = 'fixed' | 'pinned' | 'roller' | 'prescribed' | 'custom'

export const SUPPORT_CLASS_ORDER: SupportClass[] = ['fixed', 'pinned', 'roller', 'prescribed', 'custom']

export const SUPPORT_CLASS_LABEL: Record<SupportClass, string> = {
  fixed: 'Fixed',
  pinned: 'Pinned',
  roller: 'Roller',
  prescribed: 'Prescribed displacement',
  custom: 'Custom',
}

export const nextPrefixedId = (prefix: string, ids: string[]) => {
  const numbers = ids.map((id) => {
    if (id === prefix) return 1
    if (!id.startsWith(prefix)) return 0
    const rest = id.slice(prefix.length)
    if (!/^\d+$/.test(rest)) return 0
    const value = Number(rest)
    return Number.isInteger(value) && value > 0 ? value : 0
  })
  let index = Math.max(0, ...numbers) + 1
  while (ids.includes(`${prefix}${index}`)) index += 1
  return `${prefix}${index}`
}

const nodeNumericSuffix = (id: string): number => {
  const match = id.match(/(\d+)$/)
  if (!match) return 0
  const value = Number(match[1])
  return Number.isInteger(value) && value > 0 ? value : 0
}

export function supportNumber(model: ModelInput, nodeId: string): number | null {
  for (const item of model.constraints) {
    if (item.node_id !== nodeId) continue
    const value = Number(item.extensions?.support_number)
    if (Number.isInteger(value) && value > 0) return value
  }
  return null
}

export function nextSupportNumber(model: ModelInput): number {
  const seen = new Set<string>()
  const numbers: number[] = []
  for (const item of model.constraints) {
    if (seen.has(item.node_id)) continue
    seen.add(item.node_id)
    numbers.push(supportNumber(model, item.node_id) ?? nodeNumericSuffix(item.node_id))
  }
  return Math.max(0, ...numbers) + 1
}

export function addSupportAtNode(model: ModelInput, nodeId: string, familyDofs: Dof[]): ModelInput {
  if (!nodeId || model.constraints.some((item) => item.node_id === nodeId)) return model
  const number = nextSupportNumber(model)
  const used = model.constraints.map((item) => item.id)
  const created: ConstraintInput[] = familyDofs.map((dof) => {
    const id = nextPrefixedId('C', used)
    used.push(id)
    return { id, node_id: nodeId, dof, value: 0, extensions: { support_number: number } }
  })
  return { ...model, constraints: [...model.constraints, ...created] }
}

export function moveSupportToNode(model: ModelInput, fromNodeId: string, toNodeId: string): ModelInput {
  if (!fromNodeId || !toNodeId || fromNodeId === toNodeId) return model
  const moving = model.constraints.filter((item) => item.node_id === fromNodeId)
  if (!moving.length) return model
  const number = supportNumber(model, fromNodeId) ?? nextSupportNumber(model)
  const remaining = model.constraints.filter((item) => item.node_id !== fromNodeId)
  const existingDofs = new Set(remaining.filter((item) => item.node_id === toNodeId).map((item) => item.dof))
  const relocated = moving
    .filter((item) => !existingDofs.has(item.dof))
    .map((item) => ({
      ...item,
      node_id: toNodeId,
      extensions: { ...(item.extensions ?? {}), support_number: number },
    }))
  return { ...model, constraints: [...remaining, ...relocated] }
}

export function addNodalLoadAtNode(
  model: ModelInput,
  nodeId: string,
  dof: Dof,
  value: number,
): { model: ModelInput; id: string } {
  const id = nextPrefixedId('P', model.loads.map((item) => item.id))
  return {
    id,
    model: {
      ...model,
      loads: [
        ...model.loads,
        {
          id,
          kind: 'nodal',
          node_id: nodeId,
          components: { [dof]: value },
          coordinate_system: 'global',
        },
      ],
    },
  }
}

const translational = (dofs: Dof[]) => dofs.filter((dof) => dof.startsWith('U'))
const rotational = (dofs: Dof[]) => dofs.filter((dof) => dof.startsWith('R'))

export function classifySupport(familyDofs: Dof[], constrained: Array<{ dof: Dof; value?: number }>): SupportClass {
  if (!constrained.length) return 'custom'
  if (constrained.some((item) => (item.value ?? 0) !== 0)) return 'prescribed'
  const locked = new Set(constrained.map((item) => item.dof))
  const trans = translational(familyDofs)
  const rot = rotational(familyDofs)
  if (familyDofs.every((dof) => locked.has(dof))) return 'fixed'
  if (trans.length > 0 && trans.every((dof) => locked.has(dof)) && rot.every((dof) => !locked.has(dof))) return 'pinned'
  if (locked.size === 1 && trans.some((dof) => locked.has(dof))) return 'roller'
  return 'custom'
}

export interface SupportItem {
  nodeId: string
  records: ConstraintInput[]
  class: SupportClass
  dofs: Dof[]
}

export interface SupportGroup {
  class: SupportClass
  label: string
  items: SupportItem[]
}

export function groupedSupports(model: ModelInput, familyDofs: Dof[]): { groups: SupportGroup[]; nodeCount: number; recordCount: number } {
  const constrainedNodes = new Set(model.constraints.map((item) => item.node_id))
  const nodeIds = [
    ...model.nodes.map((node) => node.id).filter((id) => constrainedNodes.has(id)),
    ...Array.from(constrainedNodes).filter((id) => !model.nodes.some((node) => node.id === id)),
  ]
  const items: SupportItem[] = nodeIds.map((nodeId) => {
    const records = model.constraints.filter((item) => item.node_id === nodeId)
    return {
      nodeId,
      records,
      class: classifySupport(familyDofs, records),
      dofs: familyDofs.filter((dof) => records.some((item) => item.dof === dof)),
    }
  })
  return {
    nodeCount: items.length,
    recordCount: model.constraints.length,
    groups: SUPPORT_CLASS_ORDER
      .map((item) => ({ class: item, label: SUPPORT_CLASS_LABEL[item], items: items.filter((support) => support.class === item) }))
      .filter((group) => group.items.length > 0),
  }
}

export function constraintsForClass(
  nodeId: string,
  supportClass: SupportClass,
  familyDofs: Dof[],
  existing: ConstraintInput[],
  rollerDof: Dof,
): ConstraintInput[] {
  const others = existing.filter((item) => item.node_id !== nodeId)
  const previous = existing.filter((item) => item.node_id === nodeId)
  const wanted: Dof[] = supportClass === 'fixed' ? [...familyDofs]
    : supportClass === 'pinned' ? translational(familyDofs)
      : supportClass === 'roller' ? [rollerDof]
        : supportClass === 'prescribed' ? (previous.length ? previous.map((item) => item.dof) : [...familyDofs])
          : previous.map((item) => item.dof)
  const used = others.map((item) => item.id)
  const created: ConstraintInput[] = []
  for (const dof of wanted) {
    const keep = previous.find((item) => item.dof === dof)
    if (keep) {
      created.push(supportClass === 'prescribed' ? keep : { ...keep, value: 0 })
      continue
    }
    const id = nextPrefixedId('C', [...used, ...created.map((item) => item.id)])
    created.push({ id, node_id: nodeId, dof, value: 0 })
  }
  return [...others, ...created]
}

export function toggleConstraintDof(
  nodeId: string,
  dof: Dof,
  enabled: boolean,
  existing: ConstraintInput[],
): ConstraintInput[] {
  if (!enabled) return existing.filter((item) => !(item.node_id === nodeId && item.dof === dof))
  if (existing.some((item) => item.node_id === nodeId && item.dof === dof)) return existing
  return [...existing, { id: nextPrefixedId('C', existing.map((item) => item.id)), node_id: nodeId, dof, value: 0 }]
}

export function supportNodeId(model: ModelInput, selectionId?: string): string | undefined {
  if (!selectionId) return undefined
  if (model.constraints.some((item) => item.node_id === selectionId)) return selectionId
  return model.constraints.find((item) => item.id === selectionId)?.node_id
}
