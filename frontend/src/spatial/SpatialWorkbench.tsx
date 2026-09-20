import { WorkspaceSwitcher } from '../components/WorkspaceSwitcher'
import type { ModelFamily } from '../domain'
import { SpatialNavigator } from './SpatialNavigator'
import { LinearProgress, Menu } from '@mui/material'
import AccountTreeRoundedIcon from '@mui/icons-material/AccountTreeRounded'
import KeyboardArrowDownRoundedIcon from '@mui/icons-material/KeyboardArrowDownRounded'
import './spatial.css'
import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import { Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Divider, Drawer, IconButton, InputBase, MenuItem, Snackbar, Switch, TextField, ToggleButton, ToggleButtonGroup, Tooltip, Typography, useMediaQuery } from '@mui/material'
import FolderOpenIcon from '@mui/icons-material/FolderOpen'
import SaveAltIcon from '@mui/icons-material/SaveAlt'
import UndoIcon from '@mui/icons-material/Undo'
import RedoIcon from '@mui/icons-material/Redo'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import HelpOutlineIcon from '@mui/icons-material/HelpOutlineRounded'
import CloseIcon from '@mui/icons-material/Close'
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import { solveSpatialFrame } from '../api'
import { useConfirm } from './ConfirmProvider'
import { readBrowserStorage, writeBrowserStorage } from './browserStorage'
import { blankModel, defaultSection, deleteSelected, emptySelection, example3D, insertMember, insertNode, modelIssues, parseModel3D, planeCoords, planeLabels, toSpatialPayload, xyz, type Model3D, type Plane, type Result3D, type Selection, type Tool, type Vec3 } from './model'
import { SpatialCanvas, displayNames, type Display } from './SpatialCanvas'
import { Inspector, toolNames } from './Inspector'
import { SpatialResults } from './SpatialResults'

const STORAGE = 'nonlinear-studio.frame3d.model.v1'
function initialWorkspace() {
  const value = readBrowserStorage(STORAGE)
  if (!value) return { model: example3D(), warning: '' }
  try { return { model: parseModel3D(JSON.parse(value)), warning: '' } } catch { return { model: example3D(), warning: 'The saved 3D draft could not be read. An example is shown. Your saved draft is unchanged until you edit this model.' } }
}
const shortcuts: Record<string, Tool> = { v: 'select', n: 'node', e: 'member', m: 'material', s: 'support', c: 'section', l: 'load', h: 'tables' }
export function SpatialWorkbench({ active, onWorkspaceChange, onShellSpatial, onPlateSpatial, onContinuumSpatial, onDimensionChange, draftFamilies, resultFamilies }: { active: boolean; onWorkspaceChange: (family: ModelFamily) => void; onShellSpatial?: () => void; onPlateSpatial?: () => void; onContinuumSpatial?: () => void; onDimensionChange?: (dimension: '2d' | '3d') => void; draftFamilies: Set<ModelFamily>; resultFamilies: Set<ModelFamily> }) {
  const [menu, setMenu] = useState<HTMLElement | null>(null); const [mode, setMode] = useState<'model' | 'results'>('model')
  const [initial] = useState(initialWorkspace); const [model, setModel] = useState(initial.model)
  const [selection, setSelection] = useState<Selection>(emptySelection); const [tool, setTool] = useState<Tool>('select')
  const [defaults, setDefaults] = useState(defaultSection); const [templates, setTemplates] = useState(defaultSection); const [propertiesCollapsed, setPropertiesCollapsed] = useState(true); const [chain, setChain] = useState<number | null>(null)
  const [past, setPast] = useState<Model3D[]>([]); const [future, setFuture] = useState<Model3D[]>([])
  const [plane, setPlane] = useState<Plane>('XZ'); const [offset, setOffset] = useState(0); const [offsetDraft, setOffsetDraft] = useState('0'); const [offsetError, setOffsetError] = useState(false)
  const [grid, setGrid] = useState(1); const [gridDraft, setGridDraft] = useState('1'); const [gridError, setGridError] = useState(false)
  const [snap, setSnap] = useState(true); const [labels, setLabels] = useState(true); const [view, setView] = useState<'split' | 'plane' | '3d'>('split')
  const [fitKey, setFitKey] = useState(0); const [drawer, setDrawer] = useState(false); const [help, setHelp] = useState(false)
  const [message, setMessage] = useState(''); const [storageWarning, setStorageWarning] = useState(initial.warning); const [saved, setSaved] = useState(false)
  const [result, setResult] = useState<Result3D | null>(null); const [running, setRunning] = useState(false); const [error, setError] = useState<string | null>(null)
  const [resultsOpen, setResultsOpen] = useState(false); const [display, setDisplay] = useState<Display>('model'); const [deformationScale, setDeformationScale] = useState(100)
  const abort = useRef<AbortController | null>(null); const revision = useRef(0); const input = useRef<HTMLInputElement>(null); const importToken = useRef(0)
  const compact = useMediaQuery('(max-width: 1050px)'); const small = useMediaQuery('(max-width: 700px)'); const confirm = useConfirm()
  const activeView = small && view === 'split' ? 'plane' : view
  const persist = (next: Model3D) => { const ok = writeBrowserStorage(STORAGE, JSON.stringify(next)); setSaved(ok); setStorageWarning(ok ? '' : 'Local saving is unavailable. Export JSON to keep this model.') }
  const invalidate = () => { importToken.current++; setMode('model'); abort.current?.abort(); abort.current = null; revision.current++; setRunning(false); setError(null); setResult(null); setDisplay('model') }
  const change = (next: Model3D, toast?: string) => {
    const checked = parseModel3D(next)
    if (JSON.stringify(model) === JSON.stringify(checked)) { if (toast) setMessage(toast); return }
    invalidate(); setPast(p => [...p.slice(-49), model]); setFuture([]); setModel(checked); persist(checked)
    if (toast) setMessage(toast)
  }
  const select = (kind: 'nodes' | 'elements', id: number | null, extend: boolean) => {
    setSelection(current => id === null ? emptySelection() : extend ? { ...current, [kind]: current[kind].includes(id) ? current[kind].filter(v => v !== id) : [...current[kind], id] } : { ...emptySelection(), [kind]: [id] })
  }
  const chooseTool = (next: Tool) => { setMode('model'); setTool(next); setChain(null); if (next !== 'select') { setPropertiesCollapsed(false); if (compact) setDrawer(true) } }
  const toggleProperties = () => { if (compact) setDrawer(v => !v); else setPropertiesCollapsed(v => !v) }
  const undo = () => { if (!past.length) return; const next = past.at(-1)!; invalidate(); setFuture(f => [model, ...f]); setPast(p => p.slice(0, -1)); setModel(next); persist(next); setSelection(emptySelection()); setChain(null) }
  const redo = () => { if (!future.length) return; const next = future[0]; invalidate(); setPast(p => [...p, model]); setFuture(f => f.slice(1)); setModel(next); persist(next); setSelection(emptySelection()); setChain(null) }
  const remove = async () => {
    if (!selection.nodes.length && !selection.elements.length) return
    if (!await confirm(`Delete ${selection.nodes.length} selected node(s) and ${selection.elements.length} selected member(s)? Members connected to deleted nodes and their assignments will also be removed. You can undo this change.`, 'Delete objects')) return
    change(deleteSelected(model, selection), 'Selected objects deleted'); setSelection(emptySelection()); setChain(null)
  }
  const point = (p: Vec3) => {
    try {
      if (tool === 'node' || chain === null) {
        const inserted = insertNode(model, p); change(inserted.model); select('nodes', inserted.id, false)
        if (tool === 'member') setChain(inserted.id)
      } else {
        const inserted = insertMember(model, xyz(model.nodes[chain - 1]), p, defaults); change(inserted.model, 'Member added'); setChain(inserted.id); select('nodes', inserted.id, false)
      }
    } catch (e) { setMessage(e instanceof Error ? e.message : 'Unable to draw this member.') }
  }
  const replace = async (next: Model3D) => {
    const version = revision.current, token = importToken.current
    if (model.nodes.length && !await confirm('Replace the current 3D model? The replacement is saved locally. Undo can restore this model.', 'Replace model')) return
    if (version !== revision.current || token !== importToken.current) return
    change(next); setSelection(emptySelection()); setChain(null); setFitKey(k => k + 1); setResultsOpen(false)
  }
  const openFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]; event.target.value = ''; if (!file) return
    const token = ++importToken.current
    try {
      if (file.size > 10 * 1024 * 1024) throw new Error('The maximum JSON file size is 10 MB.')
      const contents = await file.text(); if (token !== importToken.current) return
      const next = parseModel3D(JSON.parse(contents))
      if (next.name === 'Imported space frame') next.name = file.name.replace(/\.json$/i, '')
      await replace(next)
    } catch (e) { if (token === importToken.current) setMessage(e instanceof Error ? e.message : 'Unable to read this 3D model.') }
  }
  const exportFile = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(toSpatialPayload(model), null, 2)], { type: 'application/json' }))
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `${model.name.trim().replace(/[^\p{L}\p{N}._-]+/gu, '-') || 'space-frame'}.json`; anchor.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    persist(model); setMessage('3D model exported as JSON')
  }
  const run = async () => {
    if (running) return
    setMode('results'); setResultsOpen(true); setError(null); setResult(null); setDisplay('model'); setChain(null)
    const issues = modelIssues(model)
    if (issues.length) { setError(issues.slice(0, 8).join(' ')); return }
    const controller = new AbortController(); abort.current?.abort(); abort.current = controller; const version = revision.current
    setRunning(true)
    try {
      const response = await solveSpatialFrame(model, controller.signal)
      if (controller.signal.aborted || version !== revision.current) return
      setResult(response); setDisplay('deformed'); setMessage(response.validation.passed ? 'Analysis complete · equilibrium and energy checks passed' : 'Analysis complete · review numerical checks')
    } catch (e) { if (!controller.signal.aborted && version === revision.current) setError(e instanceof Error ? e.message : 'Analysis failed. Check the model and try again.') }
    finally { if (abort.current === controller) { abort.current = null; setRunning(false) } }
  }
  const cancel = () => { abort.current?.abort(); abort.current = null; setRunning(false); setError('Stopped waiting for the result. The server may still be finishing this analysis.'); setMessage('Stopped waiting for analysis') }
  useEffect(() => { if (active) document.title = 'Frame 3D workspace — Nonlinear Studio'; if (!active) { importToken.current++; abort.current?.abort(); abort.current = null; setRunning(false); setChain(null); setDrawer(false) } }, [active])
  useEffect(() => () => { importToken.current++; abort.current?.abort() }, [])
  useEffect(() => {
    if (!active) return
    const keydown = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.isComposing || (e.target as HTMLElement)?.closest('input,textarea,select,[contenteditable="true"]') || document.querySelector('[role="dialog"]')) return
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); exportFile(); return }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); if (e.shiftKey) redo(); else undo(); return }
      if (e.key === 'Escape') { setChain(null); setTool('select'); return }
      if (mode === 'model' && (e.key === 'Delete' || e.key === 'Backspace')) { e.preventDefault(); void remove(); return }
      if (e.key === '?') { setHelp(true); return }
      if (e.metaKey || e.ctrlKey || e.altKey) return
      const match = shortcuts[e.key.toLowerCase()]; if (match) chooseTool(match)
    }
    window.addEventListener('keydown', keydown); return () => window.removeEventListener('keydown', keydown)
  })
  const setLevel = (value: number) => { setOffset(value); setOffsetDraft(String(value)); setOffsetError(false); setChain(null) }
  const stepPlane = (direction: number) => {
    const levels = [...new Set(model.nodes.map(n => planeCoords(plane, xyz(n))[2]))].sort((a, b) => a - b)
    const next = direction > 0 ? levels.find(v => v > offset + 1e-8) : [...levels].reverse().find(v => v < offset - 1e-8)
    setLevel(next ?? offset + grid * direction)
  }
  const inspector = <><Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 2, minHeight: 48, borderBottom: '1px solid', borderColor: 'divider' }}><Typography variant="subtitle2">{toolNames[tool]}</Typography><IconButton size="small" aria-label="Close properties" onClick={toggleProperties}><CloseIcon fontSize="small" /></IconButton></Box>
    <Inspector key={tool} revision={revision.current} model={model} selection={selection} tool={tool} defaults={defaults} templates={templates} onTemplates={setTemplates} onExample={() => void replace(example3D())} onDefaults={setDefaults} onChange={change} onSelect={select} onDelete={() => void remove()} onTool={chooseTool} onMessage={setMessage} /></>
  const canvasProps = { model, selection, tool: mode === 'results' ? 'select' as const : tool, plane, offset, grid, snap, chain, fitKey, result, display: mode === 'results' ? display : 'model' as const, deformationScale, labels, onSelect: select, onPoint: mode === 'model' ? point : () => {}, onEnd: () => setChain(null), onMessage: setMessage }
  return <div className="spatial-shell">
    <header className="spatial-topbar">
      <Typography variant="h6" sx={{ fontSize: 16 }}>Nonlinear Studio</Typography>
      <Button color="inherit" aria-label="More actions" startIcon={<AccountTreeRoundedIcon />} endIcon={<KeyboardArrowDownRoundedIcon />} onClick={e => setMenu(e.currentTarget)} aria-haspopup="menu" aria-expanded={!!menu}>Project</Button>
      <ToggleButtonGroup size="small" exclusive value={mode} aria-label="Workbench mode" onChange={(_, value) => { if (value) { setMode(value); setTool('select'); setChain(null) } }}><ToggleButton value="model">Model</ToggleButton><ToggleButton value="results">Results</ToggleButton></ToggleButtonGroup>
      <div className="spatial-spacer" />
      <Tooltip title="Undo (⌘ / Ctrl Z)"><span><IconButton disabled={!past.length} aria-label="Undo 3D change" onClick={undo}><UndoIcon fontSize="small" /></IconButton></span></Tooltip>
      <Tooltip title="Redo (⌘ / Ctrl Shift Z)"><span><IconButton disabled={!future.length} aria-label="Redo 3D change" onClick={redo}><RedoIcon fontSize="small" /></IconButton></span></Tooltip>
      <Button color="inherit" startIcon={<SaveAltIcon />} onClick={exportFile}>Save project</Button>
      <Button color="inherit" onClick={() => chooseTool('tables')}>Analysis</Button>
      <IconButton aria-label="3D workflow help" onClick={() => setHelp(true)}><HelpOutlineIcon fontSize="small" /></IconButton>
      <Button className="spatial-run" variant="contained" startIcon={running ? <CloseIcon /> : <PlayArrowIcon />} onClick={() => running ? cancel() : void run()}>{running ? 'Cancel' : 'Run analysis'}</Button>
      <Menu anchorEl={menu} open={!!menu} onClose={() => setMenu(null)}>
        <MenuItem onClick={() => { setMenu(null); void replace(blankModel()) }}>New 3D model</MenuItem>
        <MenuItem onClick={() => { setMenu(null); input.current?.click() }}><FolderOpenIcon fontSize="small" sx={{ mr: 1 }} />Open 3D JSON</MenuItem>
        <MenuItem onClick={() => { setMenu(null); exportFile() }}>Export 3D JSON</MenuItem>
        <MenuItem onClick={() => { setMenu(null); void replace(example3D()) }}>Reset 3D example</MenuItem>
        <MenuItem onClick={() => { setMenu(null); setHelp(true) }}>Guide</MenuItem>
      </Menu>
      <input ref={input} type="file" accept="application/json,.json" hidden onChange={openFile} />
    </header>
    <Box sx={{ display: 'flex', alignItems: 'center', minHeight: 38, px: 1, borderBottom: '1px solid', borderColor: 'divider', bgcolor: 'background.paper' }}>
      <WorkspaceSwitcher activeFamily="frame3d" draftFamilies={draftFamilies} resultFamilies={resultFamilies} onSpatial={() => {}} onShellSpatial={onShellSpatial} onPlateSpatial={onPlateSpatial} onContinuumSpatial={onContinuumSpatial} onDimensionChange={onDimensionChange} onChange={onWorkspaceChange} />
      <Divider orientation="vertical" flexItem sx={{ mx: 2, my: 1 }} />
      <InputBase sx={{ flex: 1, fontSize: 13, minWidth: 80 }} key={model.name} defaultValue={model.name} onBlur={e => { const name = e.target.value.trim(); if (name && name !== model.name) change({ ...model, name }); else e.target.value = model.name }} inputProps={{ 'aria-label': '3D model name', maxLength: 120 }} />
      <Typography variant="caption" color="text.secondary" sx={{ px: 1.5 }}>{saved ? 'Saved locally' : 'Local workspace'} · Linear static</Typography>
    </Box>
    <Box sx={{ height: 2, flexShrink: 0 }}>{running && <LinearProgress />}</Box>
    {storageWarning && <Alert severity="warning">{storageWarning}</Alert>}
    <main className="spatial-main">
      {mode === 'model' && <SpatialNavigator model={model} selection={selection} activeTool={tool} onTool={chooseTool} onCreate={kind => { setSelection(emptySelection()); chooseTool(kind === 'nodes' ? 'node' : 'member') }} onSelect={(kind, id, context) => { select(kind, id, false); chooseTool(context); setPropertiesCollapsed(false); if (compact) setDrawer(true) }} />}
      <div className="spatial-stage">
        <Box sx={{ alignItems: 'center', gap: .5, px: 1.5, minHeight: 48, borderBottom: '1px solid', borderColor: 'divider', bgcolor: 'background.paper', display: mode === 'model' ? 'flex' : 'none' }}>
          {mode === 'model' && (['select', 'node', 'member', 'support', 'load'] as Tool[]).map(value => <Button key={value} size="small" variant={tool === value ? 'outlined' : 'text'} color={tool === value ? 'primary' : 'inherit'} onClick={() => chooseTool(value)}>{value === 'select' ? 'Select' : toolNames[value]}</Button>)}
          <div className="spatial-spacer" /><Button size="small" color="inherit" onClick={toggleProperties} disabled={mode === 'results'}>Properties</Button>
        </Box>
    <div className="spatial-commandbar">
      <div className="plane-controls"><Typography variant="caption" className="command-label">WORK PLANE</Typography>
        <ToggleButtonGroup exclusive size="small" value={plane} onChange={(_, value) => { if (value) { setPlane(value); setChain(null) } }} aria-label="Working plane">{(['XY', 'XZ', 'YZ'] as Plane[]).map(p => <ToggleButton value={p} key={p} aria-label={`${p} plane`}>{p}</ToggleButton>)}</ToggleButtonGroup>
        <IconButton size="small" aria-label="Previous model plane" onClick={() => stepPlane(-1)}><ChevronLeftIcon /></IconButton>
        <TextField label={`${planeLabels(plane)[2]} (m)`} value={offsetDraft} error={offsetError} helperText={offsetError ? 'Finite number required' : undefined} onChange={e => setOffsetDraft(e.target.value)} onBlur={() => { if (!offsetDraft.trim() || !Number.isFinite(Number(offsetDraft))) setOffsetError(true); else setLevel(Number(offsetDraft)) }} onKeyDown={e => { if (e.key === 'Enter' && !e.nativeEvent.isComposing) (e.target as HTMLInputElement).blur() }} slotProps={{ htmlInput: { inputMode: 'decimal', 'aria-label': 'Working plane offset' } }} sx={{ width: 96 }} />
        <IconButton size="small" aria-label="Next model plane" onClick={() => stepPlane(1)}><ChevronRightIcon /></IconButton>
      </div>
      <Divider orientation="vertical" flexItem />
      <TextField label="Grid (m)" value={gridDraft} error={gridError} helperText={gridError ? 'Enter a positive number' : undefined} onChange={e => setGridDraft(e.target.value)} onBlur={() => { const value = Number(gridDraft); if (!gridDraft.trim() || !Number.isFinite(value) || value <= 0) setGridError(true); else { setGrid(value); setGridError(false) } }} onKeyDown={e => { if (e.key === 'Enter' && !e.nativeEvent.isComposing) (e.target as HTMLInputElement).blur() }} sx={{ width: 84 }} />
      <label className="compact-switch"><Switch size="small" checked={snap} onChange={(_, value) => setSnap(value)} />Snap</label>
      <label className="compact-switch"><Switch size="small" checked={labels} onChange={(_, value) => setLabels(value)} />Labels</label>
      <div className="spatial-spacer" />
      <ToggleButtonGroup exclusive size="small" value={activeView} onChange={(_, value) => value && setView(value)} aria-label="View layout"><ToggleButton value="plane">2D plane</ToggleButton><ToggleButton value="3d">3D view</ToggleButton>{!small && <ToggleButton value="split">Split view</ToggleButton>}</ToggleButtonGroup>
    </div>
        <div className="spatial-displaybar"><span className="spatial-muted">{tool === 'member' || tool === 'node' ? 'Right-click: end chain · Esc: select' : 'Shift + click: multi-select · Drag: orbit / pan'}</span><div className="spatial-spacer" />
          {compact && <Button size="small" onClick={() => setDrawer(true)}>Properties</Button>}
          {mode === 'results' && result && <><TextField select size="small" label="Display" value={display} onChange={e => setDisplay(e.target.value as Display)} sx={{ minWidth: 180 }}>{Object.entries(displayNames).map(([key, label]) => <MenuItem key={key} value={key}>{label}</MenuItem>)}</TextField>{display === 'deformed' && <TextField label="Scale ×" type="number" value={deformationScale} onChange={e => { const n = Number(e.target.value); if (Number.isFinite(n) && n >= 0 && n <= 1e8) setDeformationScale(n) }} sx={{ width: 95 }} />}</>}
        </div>
        <div className={`spatial-canvases layout-${activeView}`}>{activeView !== '3d' && <SpatialCanvas {...canvasProps} spatial={false} />}{activeView !== 'plane' && <SpatialCanvas {...canvasProps} spatial />}</div>
        <SpatialResults result={result} running={running} error={error} expanded={mode === 'results' && resultsOpen} onExpand={() => { setMode('results'); setResultsOpen(mode === 'model' || !resultsOpen) }} onRun={() => void run()} onCancel={cancel} selection={selection} onSelect={select} />
      </div>
      {!compact && <aside aria-label="3D properties" className="spatial-inspector" style={{ display: propertiesCollapsed || mode === 'results' ? 'none' : 'flex' }}>{inspector}</aside>}
    </main>
    <footer className="spatial-status"><span className="status-dot" />{running ? 'Analysis running' : 'Ready'}<span>{plane} · {planeLabels(plane)[2]} = {offset} m</span><span>{snap ? `Snap ${grid} m` : 'Snap off'}</span><div className="spatial-spacer" /><span>m · kN · GPa</span><span>Linear elastic / small displacement</span></footer>
    <Drawer anchor="left" open={active && compact && drawer} onClose={() => setDrawer(false)} slotProps={{ paper: { sx: { width: 'min(340px, 92vw)' } } }}>{inspector}</Drawer>
    <Snackbar open={active && !!message} autoHideDuration={4000} onClose={(_, reason) => { if (reason !== 'clickaway') setMessage('') }} message={message} action={<IconButton aria-label="Dismiss message" size="small" color="inherit" onClick={() => setMessage('')}><CloseIcon fontSize="small" /></IconButton>} />
    <Dialog open={active && help} onClose={() => setHelp(false)} maxWidth="sm" fullWidth aria-labelledby="spatial-help-title"><DialogTitle id="spatial-help-title">A familiar structural modeling workflow</DialogTitle><DialogContent dividers>
      <Box component="ol" sx={{ pl: 2.5, m: 0, '& li': { mb: 2 } }}><li><strong>Choose a work plane.</strong> Select XY, XZ, or YZ and enter its position. The arrow buttons move between existing model levels.</li><li><strong>Draw nodes and members.</strong> N places nodes; E starts a member chain. Snap to grid points and existing joints. Right-click ends the chain; Esc returns to selection. Use exact coordinates for points outside the current plane.</li><li><strong>Select and assign.</strong> V selects objects; Shift adds to the selection. M edits material, C edits section, S assigns supports, L assigns loads. Each property definition has its own Apply to elements list. Use Properties to hide or show the inspector. H opens model tables with selectable rows.</li><li><strong>Inspect in 3D.</strong> Drag to orbit, Shift-drag to pan, and scroll to zoom. View buttons provide the same rotate, tilt, zoom and fit controls.</li><li><strong>Analyze and review.</strong> Run the 3D solver, inspect displacement and force diagrams, and open the numeric tables. Model edits invalidate previous results.</li></Box>
      <Alert severity="info">All workspaces have independent models. Switching keeps both workspaces; it does not convert a model. 3D edits save locally in this browser. Export JSON for a portable copy. The 3D core supports linear static beam analysis, with optional Timoshenko members for nodal loads.</Alert>
    </DialogContent><DialogActions><Button onClick={() => setHelp(false)}>Start modeling</Button></DialogActions></Dialog>
  </div>
}
