import AddRoundedIcon from '@mui/icons-material/AddRounded'
import ArchitectureRoundedIcon from '@mui/icons-material/ArchitectureRounded'
import ArrowDownwardRoundedIcon from '@mui/icons-material/ArrowDownwardRounded'
import BlurOnRoundedIcon from '@mui/icons-material/BlurOnRounded'
import CategoryRoundedIcon from '@mui/icons-material/CategoryRounded'
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded'
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded'
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded'
import FolderOpenRoundedIcon from '@mui/icons-material/FolderOpenRounded'
import GridOnRoundedIcon from '@mui/icons-material/GridOnRounded'
import LockRoundedIcon from '@mui/icons-material/LockRounded'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import Collapse from '@mui/material/Collapse'
import Divider from '@mui/material/Divider'
import IconButton from '@mui/material/IconButton'
import List from '@mui/material/List'
import ListItemButton from '@mui/material/ListItemButton'
import ListItemIcon from '@mui/material/ListItemIcon'
import ListItemText from '@mui/material/ListItemText'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import { useEffect, useMemo, useState, type MouseEvent } from 'react'
import type { EntityKind, ModelInput, Selection } from '../domain'
import { entityDisplayLabel, loadDisplayLabel, modelDisplayLabel, supportDisplayLabel } from '../entityLabels'
import { editablePlacementNodes, firstFreePlacementNodeId, isSurfaceFamily } from '../geometrySketch'
import { meshStatusForModel } from '../meshing'
import { dofsForModel, MODEL_FAMILIES } from '../modelFamilies'
import { addNodalLoadAtNode, addSupportAtNode, groupedSupports, nextPrefixedId } from '../supports'

interface ModelNavigatorProps {
  model: ModelInput
  selection: Selection
  onSelection: (selection: Selection) => void
  onModelChange: (model: ModelInput, selection?: Selection) => void
  onEntityDoubleClick?: () => void
}

interface EntityDefinition {
  kind: Exclude<EntityKind, 'model'>
  label: string
  description: string
  section: 'setup' | 'topology'
  icon: typeof BlurOnRoundedIcon
}

const definitions: EntityDefinition[] = [
  { kind: 'materials', label: 'Materials', description: 'Constitutive models', section: 'setup', icon: CategoryRoundedIcon },
  { kind: 'constraints', label: 'Supports', description: 'Boundary conditions', section: 'setup', icon: LockRoundedIcon },
  { kind: 'loads', label: 'Loads', description: 'Nodal and distributed', section: 'setup', icon: ArrowDownwardRoundedIcon },
  { kind: 'nodes', label: 'Nodes', description: 'Coordinates and DOFs', section: 'topology', icon: BlurOnRoundedIcon },
  { kind: 'elements', label: 'Elements', description: 'Connectivity and formulation', section: 'topology', icon: ArchitectureRoundedIcon },
]

const idsFor = (model: ModelInput, kind: Exclude<EntityKind, 'model'>): string[] => model[kind].map((item) => item.id)

export function ModelNavigator({ model, selection, onSelection, onModelChange, onEntityDoubleClick }: ModelNavigatorProps) {
  const family = MODEL_FAMILIES[model.model_family]
  const familyDofs = dofsForModel(model)
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({})
  const supports = useMemo(() => groupedSupports(model, familyDofs), [model, familyDofs])
  const meshStatus = meshStatusForModel(model)
  const surfaceTopologyReadOnly = isSurfaceFamily(model)
  const meshDescription = model.model_family === 'frame'
    ? `Line topology · ${meshStatus.nodeCount} nodes · ${meshStatus.elementCount} elements`
    : `${meshStatus.sourceLabel} · ${meshStatus.nodeCount} nodes · ${meshStatus.elementCount} Q4`

  useEffect(() => {
    const selected = document.querySelector('[data-selected-entity="true"]')
    if (selected && 'scrollIntoView' in selected && typeof selected.scrollIntoView === 'function') {
      selected.scrollIntoView({ block: 'nearest' })
    }
  }, [selection])

  const add = (kind: EntityKind) => {
    const next = structuredClone(model)
    if (kind === 'nodes') {
      const id = nextPrefixedId('N', next.nodes.map((item) => item.id))
      next.nodes.push({ id, coordinates: model.model_family === 'shell' ? [0, 0, 0] : [0, 0] })
      onModelChange(next, { kind, id })
    } else if (kind === 'elements') {
      const id = nextPrefixedId('E', next.elements.map((item) => item.id))
      next.elements.push({
        id,
        formulation: family.formulation,
        node_ids: next.nodes.slice(0, family.elementNodeCount).map((item) => item.id),
        material_id: next.materials[0]?.id ?? '',
        properties: structuredClone(family.defaultElementProperties),
      })
      onModelChange(next, { kind, id })
    } else if (kind === 'materials') {
      const id = nextPrefixedId('M', next.materials.map((item) => item.id))
      next.materials.push({ id, model: family.defaultMaterial.model, parameters: structuredClone(family.defaultMaterial.parameters) })
      onModelChange(next, { kind, id })
    } else if (kind === 'constraints') {
      const nodeId = firstFreePlacementNodeId(next)
      if (!nodeId) return
      onModelChange(addSupportAtNode(next, nodeId, familyDofs), { kind, id: nodeId })
    } else if (kind === 'loads') {
      const nodeId = editablePlacementNodes(next)[0]?.id ?? next.nodes[0]?.id ?? ''
      const added = addNodalLoadAtNode(next, nodeId, family.primaryLoadDof, family.primaryLoadDof === 'UX' ? 1 : -1)
      onModelChange(added.model, { kind, id: added.id })
    }
    setOpenGroups((current) => ({ ...current, [kind]: true }))
  }

  const removeLoad = (id: string) => {
    const next = structuredClone(model)
    next.loads = next.loads.filter((item) => item.id !== id)
    onModelChange(next, { kind: 'loads' })
  }

  const removeSupport = (nodeId: string) => {
    const next = structuredClone(model)
    next.constraints = next.constraints.filter((item) => item.node_id !== nodeId)
    onModelChange(next, { kind: 'constraints' })
  }

  const groups = useMemo(() => definitions.map((definition) => {
    const ids = idsFor(model, definition.kind)
    return {
      ...definition,
      ids,
      visibleIds: ids,
      readOnly: surfaceTopologyReadOnly && (definition.kind === 'nodes' || definition.kind === 'elements'),
      supportGroups: definition.kind === 'constraints' ? supports.groups : [],
    }
  }), [model, supports.groups, surfaceTopologyReadOnly])

  const handleEntityDoubleClick = (event: MouseEvent<HTMLElement>) => {
    if ((event.target as HTMLElement).closest('[data-navigator-action="true"]')) return
    onEntityDoubleClick?.()
  }

  const renderGroup = ({ kind, label, description, icon: Icon, ids, visibleIds, readOnly, supportGroups }: typeof groups[number]) => {
    const active = selection.kind === kind
    const open = kind in openGroups ? Boolean(openGroups[kind]) : active
    const count = kind === 'constraints' ? supports.nodeCount : ids.length
    const placementCount = editablePlacementNodes(model).length
    const addDisabled = (kind === 'nodes' && surfaceTopologyReadOnly)
      || (kind === 'elements' && (surfaceTopologyReadOnly || model.nodes.length < family.elementNodeCount))
      || (kind === 'constraints' && (placementCount === 0 || !firstFreePlacementNodeId(model)))
      || (kind === 'loads' && placementCount === 0)

    return (
      <Box key={kind} sx={{ mt: 0.5 }}>
        <ListItemButton
          selected={active && !selection.id}
          onDoubleClick={handleEntityDoubleClick}
          onClick={() => {
            onSelection({ kind })
            setOpenGroups((current) => ({ ...current, [kind]: true }))
          }}
          sx={{ minHeight: 52, '&.Mui-selected::before': { content: '""', position: 'absolute', left: 0, top: 8, bottom: 8, width: 3, bgcolor: 'primary.main', borderRadius: '0 3px 3px 0' } }}
        >
          <ListItemIcon><Icon fontSize="small" /></ListItemIcon>
          <ListItemText
            primary={label}
            secondary={readOnly ? 'Visible read-only mesh entities' : description}
            slotProps={{ primary: { sx: { fontWeight: 600 } }, secondary: { variant: 'caption', noWrap: true } }}
          />
          <Chip label={count} size="small" variant="outlined" sx={{ height: 22, mr: 0.25 }} />
          <Tooltip title={kind === 'constraints' && addDisabled && model.nodes.length ? 'Every node already has a support' : `Add ${label.toLowerCase()}`}>
            <span>
              <IconButton
                data-navigator-action="true"
                size="small"
                aria-label={`Add ${label.toLowerCase()}`}
                disabled={addDisabled}
                onClick={(event) => { event.stopPropagation(); add(kind) }}
              >
                <AddRoundedIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <IconButton
            data-navigator-action="true"
            size="small"
            aria-label={open ? `Collapse ${label.toLowerCase()}` : `Expand ${label.toLowerCase()}`}
            onClick={(event) => {
              event.stopPropagation()
              setOpenGroups((current) => ({ ...current, [kind]: !open }))
            }}
          >
            <ExpandMoreRoundedIcon sx={{ fontSize: 20, transform: open ? 'rotate(180deg)' : undefined, transition: 'transform .18s' }} />
          </IconButton>
        </ListItemButton>
        <Collapse in={open} timeout={180} unmountOnExit>
          {kind === 'constraints' ? (
            supportGroups.length === 0 ? (
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', pl: 6, py: 0.75 }}>No supports yet</Typography>
            ) : supportGroups.map((group) => (
              <Box key={group.class} sx={{ pt: 0.25 }}>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', pl: 6, py: 0.5, fontWeight: 600 }}>
                  {group.label}
                </Typography>
                {group.items.map((item) => (
                  <ListItemButton
                    key={item.nodeId}
                    selected={selection.kind === 'constraints' && selection.id === item.nodeId}
                    data-selected-entity={selection.kind === 'constraints' && selection.id === item.nodeId ? 'true' : undefined}
                    onClick={() => onSelection({ kind: 'constraints', id: item.nodeId })}
                    onDoubleClick={handleEntityDoubleClick}
                    sx={{ pl: 6, minHeight: 36, pr: 0.5 }}
                  >
                    <ListItemText
                      primary={supportDisplayLabel(model, item.nodeId)}
                      secondary={item.dofs.join(' · ')}
                      slotProps={{
                        primary: { variant: 'body2', sx: { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' } },
                        secondary: { variant: 'caption' },
                      }}
                    />
                    <Tooltip title={`Delete ${supportDisplayLabel(model, item.nodeId)}`}>
                      <IconButton data-navigator-action="true" size="small" aria-label={`Delete ${supportDisplayLabel(model, item.nodeId)}`} onClick={(event) => { event.stopPropagation(); removeSupport(item.nodeId) }}>
                        <DeleteOutlineRoundedIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </ListItemButton>
                ))}
              </Box>
            ))
          ) : visibleIds.length === 0 ? (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', pl: 6, py: 0.75 }}>
              No {label.toLowerCase()} yet
            </Typography>
          ) : visibleIds.map((id) => (
            <ListItemButton
              key={id}
              selected={selection.kind === kind && selection.id === id}
              data-selected-entity={selection.kind === kind && selection.id === id ? 'true' : undefined}
              onClick={() => onSelection({ kind, id })}
              onDoubleClick={handleEntityDoubleClick}
              sx={{ pl: 6, minHeight: 34, pr: 0.5 }}
            >
              <ListItemText primary={entityDisplayLabel(model, kind, id)} slotProps={{ primary: { variant: 'body2' } }} />
              {readOnly && <LockRoundedIcon aria-label="Read-only mesh entity" sx={{ fontSize: 15, color: 'text.disabled', mr: 0.75 }} />}
              {kind === 'loads' && (
                <Tooltip title={`Delete ${loadDisplayLabel(model, id)}`}>
                  <IconButton data-navigator-action="true" size="small" aria-label={`Delete ${loadDisplayLabel(model, id)}`} onClick={(event) => { event.stopPropagation(); removeLoad(id) }}>
                    <DeleteOutlineRoundedIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              )}
            </ListItemButton>
          ))}
        </Collapse>
      </Box>
    )
  }

  return (
    <Box sx={{ height: '100%', overflow: 'auto', display: 'flex', flexDirection: 'column', scrollbarGutter: 'stable' }}>
      <List dense disablePadding sx={{ px: 0.75, py: 1.5 }}>
        <Typography variant="overline" color="text.secondary" sx={{ display: 'block', px: 1.25, pb: 0.5 }}>Setup</Typography>
        <ListItemButton
          selected={selection.kind === 'model'}
          data-selected-entity={selection.kind === 'model' ? 'true' : undefined}
          onClick={() => onSelection({ kind: 'model' })}
          onDoubleClick={handleEntityDoubleClick}
          sx={{ minHeight: 52, '&.Mui-selected::before': { content: '""', position: 'absolute', left: 0, top: 8, bottom: 8, width: 3, bgcolor: 'primary.main', borderRadius: '0 3px 3px 0' } }}
        >
          <ListItemIcon><FolderOpenRoundedIcon fontSize="small" /></ListItemIcon>
          <ListItemText
            primary="Model information"
            secondary={modelDisplayLabel()}
            slotProps={{ primary: { sx: { fontWeight: 600 } }, secondary: { variant: 'caption', noWrap: true } }}
          />
        </ListItemButton>
        {groups.filter((group) => group.section === 'setup').map(renderGroup)}

        <Divider sx={{ my: 1.25 }} />
        <Typography variant="overline" color="text.secondary" sx={{ display: 'block', px: 1.25, pb: 0.5 }}>Topology</Typography>
        <ListItemButton
          selected={selection.kind === 'mesh'}
          data-selected-entity={selection.kind === 'mesh' ? 'true' : undefined}
          aria-label="Open mesh settings"
          onClick={() => onSelection({ kind: 'mesh' })}
          onDoubleClick={handleEntityDoubleClick}
          sx={{ minHeight: 54, '&.Mui-selected::before': { content: '""', position: 'absolute', left: 0, top: 8, bottom: 8, width: 3, bgcolor: 'primary.main', borderRadius: '0 3px 3px 0' } }}
        >
          <ListItemIcon><GridOnRoundedIcon fontSize="small" /></ListItemIcon>
          <ListItemText
            primary="Mesh"
            secondary={meshDescription}
            slotProps={{ primary: { sx: { fontWeight: 600 } }, secondary: { variant: 'caption', noWrap: true } }}
          />
          {meshStatus.generatedByGmsh && <CheckCircleRoundedIcon color="success" sx={{ fontSize: 18, mr: 1 }} />}
        </ListItemButton>
        {groups.filter((group) => group.section === 'topology').map(renderGroup)}
      </List>
    </Box>
  )
}
