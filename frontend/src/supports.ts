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
  let index = ids.length + 1
  while (ids.includes(`${prefix}${index}`)) index += 1
  return `${prefix}${index}`
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
