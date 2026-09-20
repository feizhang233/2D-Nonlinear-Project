import { useRef, useState } from 'react'
import { Box, Button, ButtonBase, Divider, IconButton, InputAdornment, List, ListItemButton, Stack, TextField, Tooltip, Typography } from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded'
import ArrowForwardRoundedIcon from '@mui/icons-material/ArrowForwardRounded'
import CheckRoundedIcon from '@mui/icons-material/CheckRounded'
import CloseRoundedIcon from '@mui/icons-material/CloseRounded'
import HubOutlinedIcon from '@mui/icons-material/HubOutlined'
import HorizontalRuleRoundedIcon from '@mui/icons-material/HorizontalRuleRounded'
import LayersOutlinedIcon from '@mui/icons-material/LayersOutlined'
import CropSquareRoundedIcon from '@mui/icons-material/CropSquareRounded'
import FoundationOutlinedIcon from '@mui/icons-material/FoundationOutlined'
import SouthRoundedIcon from '@mui/icons-material/SouthRounded'
import TableChartOutlinedIcon from '@mui/icons-material/TableChartOutlined'
import SearchRoundedIcon from '@mui/icons-material/SearchRounded'
import StopRoundedIcon from '@mui/icons-material/StopRounded'
import { dofs, norm, sub, xyz, type Model3D, type Selection, type Tool } from './model'

type Group = 'nodes' | 'elements' | 'material' | 'section' | 'support' | 'load' | 'tables'
type EntityRow = { key: string; id: number; kind: 'nodes' | 'elements'; title: string; detail: string }
const groups = [
  { id: 'nodes', label: 'Nodes', icon: HubOutlinedIcon },
  { id: 'elements', label: 'Members', icon: HorizontalRuleRoundedIcon },
  { id: 'material', label: 'Materials', icon: LayersOutlinedIcon },
  { id: 'section', label: 'Sections', icon: CropSquareRoundedIcon },
  { id: 'support', label: 'Supports', icon: FoundationOutlinedIcon },
  { id: 'load', label: 'Loads', icon: SouthRoundedIcon },
  { id: 'tables', label: 'Tables & analysis', icon: TableChartOutlinedIcon },
] as const
const number = (value: number) => Number(value.toPrecision(4)).toString()

function entityRows(model: Model3D, group: Group): EntityRow[] {
  if (group === 'nodes') return model.nodes.map(n => ({ key: `n${n.id}`, id: n.id, kind: 'nodes', title: `Node ${n.id}`, detail: `X ${number(n.x)} · Y ${number(n.y)} · Z ${number(n.z)} m` }))
  if (group === 'support') return model.supports.map(s => ({ key: `s${s.node_id}`, id: s.node_id, kind: 'nodes', title: `Node ${s.node_id}`, detail: `${dofs.filter(d => s[d]).join(' · ').toUpperCase()}${s.axes ? ' · inclined' : ''}` }))
  if (group === 'load') {
    // The editor replaces assignments per object; aggregate repeated load records accordingly.
    const nodes = [...new Set(model.nodal_loads.map(l => l.node_id))]
    const members = [...new Set(model.distributed_loads.map(l => l.element_id))]
    return [
      ...nodes.map(id => ({ key: `ln${id}`, id, kind: 'nodes' as const, title: `Node ${id}`, detail: 'Nodal force / moment' })),
      ...members.map(id => ({ key: `le${id}`, id, kind: 'elements' as const, title: `Member ${id}`, detail: 'Distributed load' })),
    ]
  }
  if (group === 'tables') return []
  const nodes = new Map(model.nodes.map(n => [n.id, n]))
  return model.elements.map(e => {
    const a = nodes.get(e.node_i); const b = nodes.get(e.node_j)
    const detail = group === 'material' ? `E ${number(e.E / 1e9)} · G ${number(e.G / 1e9)} GPa`
      : group === 'section' ? `A ${number(e.A)} m² · ${e.theory}`
        : `N${e.node_i} → N${e.node_j}${a && b ? ` · ${number(norm(sub(xyz(b), xyz(a))))} m` : ''}`
    return { key: `e${e.id}`, id: e.id, kind: 'elements', title: `Member ${e.id}`, detail }
  })
}

/** Fixed category rail with a bounded, independently scrolling object explorer. */
export function SpatialNavigator({ model, selection, activeTool, onTool, onCreate, onSelect }: {
  model: Model3D; selection: Selection; activeTool: Tool; onTool: (tool: Tool) => void
  onCreate: (kind: 'nodes' | 'elements') => void
  onSelect: (kind: 'nodes' | 'elements', id: number, context: Tool) => void
}) {
  const [browse, setBrowse] = useState<'nodes' | 'elements'>('elements')
  const [expanded, setExpanded] = useState(true)
  const [searches, setSearches] = useState<Partial<Record<Group, string>>>({})
  const [limits, setLimits] = useState<Partial<Record<Group, number>>>({})
  const searchRef = useRef<HTMLInputElement>(null)
  const group: Group = activeTool === 'select' ? browse : activeTool === 'node' ? 'nodes' : activeTool === 'member' ? 'elements' : activeTool
  const label = groups.find(g => g.id === group)!.label
  const query = searches[group] ?? ''; const limit = limits[group] ?? 60
  const rows = entityRows(model, group)
  const matches = rows.filter(row => `${row.title} ${row.detail}`.toLowerCase().includes(query.trim().toLowerCase()))
  const selected = (row: EntityRow) => selection[row.kind].includes(row.id)
  const visible = matches.filter((row, i) => i < limit || selected(row))
  const remaining = matches.length - visible.length
  const geometry = group === 'nodes' || group === 'elements'
  const drawing = activeTool === 'node' || activeTool === 'member'
  const selectionCount = selection.nodes.length + selection.elements.length
  const chooseGroup = (next: Group) => {
    setExpanded(true)
    if (next === 'nodes' || next === 'elements') { setBrowse(next); onTool('select') }
    else onTool(next)
  }
  const setQuery = (value: string) => { setSearches(current => ({ ...current, [group]: value })); setLimits(current => ({ ...current, [group]: 60 })) }

  return <Box component="aside" aria-label="3D model navigator" sx={{ width: expanded ? 288 : 68, flexShrink: 0, display: 'flex', bgcolor: 'background.paper', borderRight: '1px solid', borderColor: 'divider', minHeight: 0 }}>
    <Box component="nav" aria-label="Model categories" sx={{ width: 68, flexShrink: 0, display: 'flex', flexDirection: 'column', bgcolor: 'background.containerLow', borderRight: expanded ? '1px solid' : 0, borderColor: 'divider', overflowY: 'auto' }}>
      <Box sx={{ minHeight: 48, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Tooltip title={expanded ? 'Collapse object list' : 'Expand object list'} placement="right">
          <IconButton aria-label={expanded ? 'Collapse object list' : 'Expand object list'} aria-expanded={expanded} aria-controls="spatial-object-explorer" size="small" onClick={() => setExpanded(value => !value)}>{expanded ? <ArrowBackRoundedIcon fontSize="small" /> : <ArrowForwardRoundedIcon fontSize="small" />}</IconButton>
        </Tooltip>
      </Box>
      {groups.map(({ id, label: name, icon: Icon }, index) => <Box key={id} sx={{ mt: id === 'tables' ? 'auto' : 0 }}>
        {(index === 2 || id === 'tables') && <Divider sx={{ mx: 1.5, my: 1 }} />}
        <Tooltip title={name} placement="right" enterDelay={600}>
          <ButtonBase aria-label={name} aria-pressed={group === id} onClick={() => chooseGroup(id)} sx={{ width: 56, minHeight: 58, mx: .75, mb: .5, px: .25, gap: .5, borderRadius: 1, display: 'flex', flexDirection: 'column', color: group === id ? 'primary.dark' : 'text.secondary', bgcolor: group === id ? 'action.selected' : 'transparent', '&:hover': { bgcolor: group === id ? 'action.selected' : 'action.hover' }, '&.Mui-focusVisible': { outline: '2px solid', outlineColor: 'primary.main', outlineOffset: -2 } }}>
            <Icon sx={{ fontSize: 21 }} /><Typography component="span" sx={{ fontSize: 10, lineHeight: 1.3, fontWeight: group === id ? 600 : 500 }}>{id === 'tables' ? 'Tables' : name}</Typography>
          </ButtonBase>
        </Tooltip>
      </Box>)}
    </Box>
    <Box id="spatial-object-explorer" hidden={!expanded} sx={{ display: expanded ? 'flex' : 'none', flexDirection: 'column', minWidth: 0, flex: 1 }}>
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', minHeight: 48, px: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>{label}</Typography>
        {group !== 'tables' && <Typography variant="caption" color="text.secondary" sx={{ bgcolor: 'background.container', borderRadius: 1, px: .75, fontVariantNumeric: 'tabular-nums' }}>{rows.length}</Typography>}
      </Stack>
      {group === 'tables' ? <Box sx={{ p: 1.5 }}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>Review model data and analysis settings in Properties.</Typography>
        {[['Nodes', model.nodes.length], ['Members', model.elements.length], ['Supports', model.supports.length], ['Load records', model.nodal_loads.length + model.distributed_loads.length]].map(([name, count]) => <Stack key={name} direction="row" sx={{ justifyContent: 'space-between', py: 1, borderBottom: '1px solid', borderColor: 'divider' }}><Typography variant="body2">{name}</Typography><Typography variant="body2">{count}</Typography></Stack>)}
        <Button fullWidth variant="outlined" size="small" sx={{ mt: 2 }} onClick={() => onTool('tables')}>Open model tables</Button>
      </Box> : <>
        <Box sx={{ p: 1.5, pb: 1 }}>
          {geometry ? <Button fullWidth size="small" variant={drawing ? 'outlined' : 'contained'} disableElevation startIcon={drawing ? <StopRoundedIcon /> : <AddRoundedIcon />} onClick={() => { setBrowse(group); if (drawing) onTool('select'); else onCreate(group) }}>{drawing ? 'Finish drawing' : `New ${group === 'nodes' ? 'node' : 'member'}`}</Button>
            : <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: .5 }}>{group === 'material' || group === 'section' ? 'Member assignments · select to edit' : 'Select an assignment to edit in Properties.'}</Typography>}
          <TextField inputRef={searchRef} fullWidth size="small" value={query} placeholder={geometry ? `Find ${label.toLowerCase()}` : 'Find assignments'} onChange={event => setQuery(event.target.value)} sx={{ mt: 1.5 }} slotProps={{ htmlInput: { 'aria-label': `Find ${label.toLowerCase()}` }, input: { startAdornment: <InputAdornment position="start"><SearchRoundedIcon sx={{ fontSize: 17, color: 'text.secondary' }} /></InputAdornment>, endAdornment: query ? <InputAdornment position="end"><IconButton size="small" aria-label="Clear entity search" onClick={() => { setQuery(''); searchRef.current?.focus() }}><CloseRoundedIcon sx={{ fontSize: 16 }} /></IconButton></InputAdornment> : undefined } }} />
        </Box>
        <Box sx={{ flex: 1, minHeight: 0, overflowY: 'auto', px: .75, pb: 1 }}>
          <List dense disablePadding aria-label={`${label} objects`}>
            {visible.map(row => <ListItemButton key={row.key} aria-label={row.title} aria-pressed={selected(row)} selected={selected(row)} onClick={() => { if (geometry) setBrowse(row.kind); onSelect(row.kind, row.id, geometry ? 'select' : group) }} sx={{ alignItems: 'center', py: 1, px: 1, mb: .25, borderRadius: 1, borderLeft: '2px solid', borderLeftColor: selected(row) ? 'primary.main' : 'transparent' }}>
              <Box sx={{ minWidth: 0, flex: 1 }}><Typography variant="body2" sx={{ fontWeight: selected(row) ? 600 : 500 }}>{row.title}</Typography><Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: .25, fontSize: 10.5, overflowWrap: 'anywhere', fontVariantNumeric: 'tabular-nums' }}>{row.detail}</Typography></Box>
              {selected(row) && <CheckRoundedIcon sx={{ ml: .5, fontSize: 15, color: 'primary.main', flexShrink: 0 }} />}
            </ListItemButton>)}
          </List>
          {!matches.length && <Box sx={{ p: 1.5 }}><Typography variant="body2">{query ? 'No matches' : `No ${label.toLowerCase()} yet`}</Typography><Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: .5 }}>{query ? 'Try a different ID or clear the search.' : geometry ? `Create a ${group === 'nodes' ? 'node' : 'member'} to get started.` : group === 'support' || group === 'load' ? 'Select objects in the canvas, then apply an assignment in Properties.' : 'Create members, then assign their properties.'}</Typography>{query && <Button size="small" onClick={() => { setQuery(''); searchRef.current?.focus() }}>Clear search</Button>}</Box>}
          {remaining > 0 && <Button fullWidth size="small" onClick={() => setLimits(current => ({ ...current, [group]: limit + 60 }))}>Show more ({remaining})</Button>}
        </Box>
        {query && <Typography role="status" variant="caption" color="text.secondary" sx={{ px: 1.5, pb: 1 }}>{matches.length} of {rows.length} matching</Typography>}
      </>}
      <Box sx={{ mt: 'auto', p: 1.5, borderTop: '1px solid', borderColor: 'divider', bgcolor: 'background.containerLow' }}>
        <Typography variant="caption" color={selectionCount ? 'primary.main' : 'text.secondary'} sx={{ display: 'block', fontWeight: 500 }}>{drawing ? 'Drawing mode · Esc to select' : selectionCount ? `${selectionCount} ${selectionCount === 1 ? 'object' : 'objects'} selected` : 'Select an object to inspect'}</Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: 10.5, mt: .25 }}>{model.nodes.length} nodes · {model.elements.length} members</Typography>
      </Box>
    </Box>
  </Box>
}
