import type { EntityKind, ModelInput } from './domain'
import { supportNumber } from './supports'

const singular: Record<Exclude<EntityKind, 'model'>, string> = {
  nodes: 'Node',
  elements: 'Element',
  materials: 'Material',
  constraints: 'Support',
  loads: 'Load',
}

export const modelDisplayLabel = () => 'Model 1'

type EntityLabelKind = Exclude<EntityKind, 'model'>

const isRecord = (value: unknown): value is Record<string, unknown> => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
)

const customDisplayName = (model: ModelInput, kind: EntityLabelKind, id: string): string | null => {
  const ui = isRecord(model.extensions?.ui) ? model.extensions.ui : null
  const entityNames = isRecord(ui?.entity_names) ? ui.entity_names : null
  const namesForKind = isRecord(entityNames?.[kind]) ? entityNames[kind] : null
  const value = namesForKind?.[id]
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

export function withEntityDisplayName(
  model: ModelInput,
  kind: EntityLabelKind,
  id: string,
  displayName: string,
): ModelInput {
  const next = structuredClone(model)
  const extensions = isRecord(next.extensions) ? next.extensions : {}
  const ui = isRecord(extensions.ui) ? extensions.ui : {}
  const entityNames = isRecord(ui.entity_names) ? ui.entity_names : {}
  const namesForKind = isRecord(entityNames[kind]) ? entityNames[kind] : {}
  const normalized = displayName.slice(0, 80)

  if (normalized.trim()) namesForKind[id] = normalized
  else delete namesForKind[id]

  entityNames[kind] = namesForKind
  ui.entity_names = entityNames
  extensions.ui = ui
  next.extensions = extensions
  return next
}

const supportNodeIds = (model: ModelInput): string[] => {
  const constrained = new Set(model.constraints.map((item) => item.node_id))
  return [
    ...model.nodes.map((node) => node.id).filter((id) => constrained.has(id)),
    ...Array.from(constrained).filter((id) => !model.nodes.some((node) => node.id === id)),
  ]
}

const numericSuffix = (id: string): number | null => {
  const match = id.match(/(\d+)$/)
  if (!match) return null
  const value = Number(match[1])
  return Number.isInteger(value) && value > 0 ? value : null
}

export function entityDisplayLabel(
  model: ModelInput,
  kind: EntityLabelKind,
  id: string,
): string {
  const customName = customDisplayName(model, kind, id)
  if (customName) return customName
  if (kind === 'constraints') {
    const stored = supportNumber(model, id)
    if (stored !== null) return `${singular[kind]} ${stored}`
  }
  const fromId = numericSuffix(id)
  if (fromId !== null) return `${singular[kind]} ${fromId}`
  const ids = kind === 'constraints' ? supportNodeIds(model) : model[kind].map((item) => item.id)
  const index = ids.indexOf(id)
  return index >= 0 ? `${singular[kind]} ${index + 1}` : singular[kind]
}

export const nodeDisplayLabel = (model: ModelInput, id: string) => entityDisplayLabel(model, 'nodes', id)
export const elementDisplayLabel = (model: ModelInput, id: string) => entityDisplayLabel(model, 'elements', id)
export const materialDisplayLabel = (model: ModelInput, id: string) => entityDisplayLabel(model, 'materials', id)
export const supportDisplayLabel = (model: ModelInput, nodeId: string) => entityDisplayLabel(model, 'constraints', nodeId)
export const loadDisplayLabel = (model: ModelInput, id: string) => entityDisplayLabel(model, 'loads', id)
