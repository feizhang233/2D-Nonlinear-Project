import ChevronRightRoundedIcon from '@mui/icons-material/ChevronRightRounded'
import SettingsOutlinedIcon from '@mui/icons-material/SettingsOutlined'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import CloseRoundedIcon from '@mui/icons-material/CloseRounded'
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded'
import SearchRoundedIcon from '@mui/icons-material/SearchRounded'
import {
  Box,
  Button,
  IconButton,
  InputAdornment,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import type {
  EntityKind,
  ModelInput,
  Selection,
  SelectionKind,
} from '../domain'
import { entityDisplayLabel } from '../entityLabels'
import {
  editablePlacementNodes,
  firstFreePlacementNodeId,
  isSurfaceFamily,
} from '../geometrySketch'
import { dofsForModel, MODEL_FAMILIES } from '../modelFamilies'
import { addSection, sectionLibrary } from '../sections'
import { addSupportAtNode, nextPrefixedId } from '../supports'

const GROUPS: Array<{ kind: SelectionKind; label: string }> = [
  { kind: 'geometry', label: 'Geometry' },
  { kind: 'nodes', label: 'Nodes' },
  { kind: 'elements', label: 'Elements' },
  { kind: 'materials', label: 'Materials' },
  { kind: 'sections', label: 'Sections' },
  { kind: 'constraints', label: 'Supports' },
  { kind: 'loads', label: 'Loads' },
  { kind: 'mesh', label: 'Mesh' },
]

interface Props {
  model: ModelInput
  selection: Selection
  onSelection: (selection: Selection) => void
  onModelChange: (model: ModelInput, selection?: Selection) => void
  onDelete: () => void
  onInspectModel: () => void
  onAddLoad: () => void
  onDraw: (tool: 'add-node' | 'add-member') => void
  children?: ReactNode
}

export function ModelNavigator({
  model,
  selection,
  onSelection,
  onModelChange,
  onDelete,
  onDraw,
  onAddLoad,
  onInspectModel,
  children,
}: Props) {
  const [query, setQuery] = useState('')
  const [visible, setVisible] = useState(60)
  const searchRef = useRef<HTMLInputElement>(null)
  useEffect(() => {
    setQuery('')
    setVisible(60)
  }, [selection.kind, model.model_id])
  const count = (kind: SelectionKind): number | undefined => {
    if (kind === 'sections') return sectionLibrary(model).definitions.length
    if (kind === 'constraints')
      return new Set(model.constraints.map((item) => item.node_id)).size
    if (kind === 'geometry' || kind === 'mesh' || kind === 'model')
      return undefined
    return model[kind].length
  }
  const kind = selection.kind
  const group = GROUPS.find((item) => item.kind === kind)
  const items =
    kind === 'sections'
      ? sectionLibrary(model).definitions.map((s) => ({
          id: s.id,
          label: s.name,
        }))
      : kind === 'model' || kind === 'geometry' || kind === 'mesh'
        ? []
        : (kind === 'constraints'
            ? [...new Set(model.constraints.map((item) => item.node_id))]
            : model[kind].map((item) => item.id)
          ).map((id) => ({
            id,
            label: entityDisplayLabel(
              model,
              kind as Exclude<EntityKind, 'model'>,
              id,
            ),
          }))
  const filtered = items.filter((item) =>
    `${item.label} ${item.id}`.toLowerCase().includes(query.toLowerCase()),
  )
  const selectedIndex = filtered.findIndex((item) => item.id === selection.id)
  const displayed = filtered.slice(0, Math.max(visible, selectedIndex + 1))
  const readonly =
    isSurfaceFamily(model) && (kind === 'nodes' || kind === 'elements')
  const noAdd =
    readonly ||
    !group ||
    kind === 'geometry' ||
    kind === 'mesh' ||
    (kind === 'elements' && !model.materials.length) ||
    (kind === 'constraints' && !firstFreePlacementNodeId(model)) ||
    (kind === 'loads' && !editablePlacementNodes(model).length)

  const add = () => {
    const family = MODEL_FAMILIES[model.model_family]
    const next = structuredClone(model)
    if (kind === 'sections') {
      const added = addSection(model)
      onModelChange(added.model, { kind, id: added.id })
    }
    if (kind === 'nodes') onDraw('add-node')
    if (kind === 'elements') onDraw('add-member')
    if (kind === 'materials') {
      const id = nextPrefixedId(
        'M',
        next.materials.map((item) => item.id),
      )
      next.materials.push({
        id,
        model: family.defaultMaterial.model,
        parameters: structuredClone(family.defaultMaterial.parameters),
      })
      onModelChange(next, { kind, id })
    }
    if (kind === 'constraints') {
      const id = firstFreePlacementNodeId(model)
      if (id)
        onModelChange(addSupportAtNode(model, id, dofsForModel(model)), {
          kind,
          id,
        })
    }
    if (kind === 'loads') onAddLoad()
  }
  return (
    <Stack sx={{ height: '100%', minHeight: 0 }}>
      <Stack
        direction="row"
        sx={{
          height: 52,
          px: 2,
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
          Model
        </Typography>
        <Tooltip title="Model name and units">
          <IconButton
            size="small"
            aria-label="Model information"
            onClick={onInspectModel}
          >
            <SettingsOutlinedIcon sx={{ fontSize: 17 }} />
          </IconButton>
        </Tooltip>
      </Stack>
      <Box sx={{ flex: 1, minHeight: 0, overflow: 'auto', px: 1, pb: 2 }}>
        {GROUPS.map((item) => (
          <Box key={item.kind}>
            <Button
              fullWidth
              aria-label={
                item.kind === 'mesh'
                  ? 'Open mesh settings'
                  : `Browse ${item.label.toLowerCase()}`
              }
              aria-expanded={kind === item.kind}
              aria-pressed={kind === item.kind}
              onClick={() =>
                onSelection({ kind: kind === item.kind ? 'model' : item.kind })
              }
              sx={{
                justifyContent: 'flex-start',
                height: 38,
                px: 1,
                gap: 1,
                color: kind === item.kind ? 'primary.main' : 'text.primary',
                bgcolor: kind === item.kind ? 'action.selected' : 'transparent',
                fontSize: 13,
              }}
            >
              <ChevronRightRoundedIcon
                sx={{
                  fontSize: 16,
                  color: 'text.secondary',
                  transform: kind === item.kind ? 'rotate(90deg)' : 'none',
                }}
              />
              {item.label}
              <Typography
                component="span"
                variant="caption"
                color="text.secondary"
                sx={{ ml: 'auto', fontVariantNumeric: 'tabular-nums' }}
              >
                {count(item.kind)}
              </Typography>
            </Button>
            {kind === item.kind &&
              (kind === 'geometry' ? (
                <Box sx={{ mt: 1 }}>{children}</Box>
              ) : (
                <Box sx={{ pt: 0.5, pb: 1, pl: 1.75 }}>
                  {!['mesh', 'geometry'].includes(kind) && (
                    <Button
                      size="small"
                      startIcon={<AddRoundedIcon />}
                      disabled={noAdd}
                      onClick={add}
                      aria-label={`Add ${item.label.toLowerCase()}`}
                      sx={{ justifyContent: 'flex-start', mb: 0.5 }}
                    >
                      New{' '}
                      {kind === 'constraints'
                        ? 'support'
                        : kind === 'elements'
                          ? 'member'
                          : item.label.toLowerCase().slice(0, -1)}
                    </Button>
                  )}
                  {(items.length > 8 || query) && (
                    <TextField
                      inputRef={searchRef}
                      label={`Find ${item.label.toLowerCase()}`}
                      value={query}
                      onChange={(event) => {
                        setQuery(event.target.value)
                        setVisible(60)
                      }}
                      sx={{ mb: 1, mr: 1 }}
                      slotProps={{
                        input: {
                          startAdornment: (
                            <InputAdornment position="start">
                              <SearchRoundedIcon fontSize="small" />
                            </InputAdornment>
                          ),
                          endAdornment: query && (
                            <InputAdornment position="end">
                              <IconButton
                                size="small"
                                aria-label="Clear entity search"
                                onClick={() => {
                                  setQuery('')
                                  searchRef.current?.focus()
                                }}
                              >
                                <CloseRoundedIcon fontSize="small" />
                              </IconButton>
                            </InputAdornment>
                          ),
                        },
                      }}
                    />
                  )}
                  {displayed.map((entry) => (
                    <Button
                      key={entry.id}
                      aria-label={`Select ${entry.label}`}
                      aria-pressed={selection.id === entry.id}
                      onClick={() => onSelection({ kind, id: entry.id })}
                      sx={{
                        width: '100%',
                        justifyContent: 'flex-start',
                        textAlign: 'left',
                        px: 1.5,
                        minHeight: 32,
                        color:
                          selection.id === entry.id
                            ? 'primary.main'
                            : 'text.secondary',
                        bgcolor:
                          selection.id === entry.id
                            ? 'action.selected'
                            : 'transparent',
                        borderLeft: '2px solid',
                        borderLeftColor:
                          selection.id === entry.id
                            ? 'primary.main'
                            : 'transparent',
                        borderRadius: 1,
                        overflowWrap: 'anywhere',
                      }}
                    >
                      <Typography
                        variant="body2"
                        sx={{
                          fontWeight: selection.id === entry.id ? 600 : 400,
                        }}
                      >
                        {entry.label}
                      </Typography>
                    </Button>
                  ))}
                  {!displayed.length && !['model', 'mesh'].includes(kind) && (
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ display: 'block', px: 1, py: 1 }}
                    >
                      {query
                        ? 'No matching items. Clear the search to see all items.'
                        : `No ${item.label.toLowerCase()} yet.`}
                    </Typography>
                  )}
                  {kind === 'mesh' && (
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ display: 'block', px: 1, py: 1 }}
                    >
                      Mesh settings are open in Properties.
                    </Typography>
                  )}
                  {filtered.length > displayed.length && (
                    <Button
                      size="small"
                      fullWidth
                      onClick={() => setVisible((n) => n + 60)}
                    >
                      Show 60 more · {filtered.length} total
                    </Button>
                  )}
                </Box>
              ))}
          </Box>
        ))}
      </Box>
      {selection.id && !['geometry', 'mesh', 'model'].includes(kind) && (
        <Box
          sx={{
            borderTop: '1px solid',
            borderColor: 'divider',
            px: 2,
            py: 0.5,
          }}
        >
          <Button
            size="small"
            startIcon={<DeleteOutlineRoundedIcon />}
            color="error"
            disabled={readonly}
            onClick={onDelete}
          >
            Delete selected
          </Button>
          {readonly && (
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: 'block' }}
            >
              Generated topology · read-only
            </Typography>
          )}
        </Box>
      )}
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ px: 2, py: 1.25, borderTop: '1px solid', borderColor: 'divider' }}
      >
        {model.nodes.length} nodes · {model.elements.length} elements
      </Typography>
    </Stack>
  )
}
