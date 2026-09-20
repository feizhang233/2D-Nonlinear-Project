import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  InputBase,
  LinearProgress,
  Menu,
  MenuItem,
  Snackbar,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import AccountTreeRoundedIcon from '@mui/icons-material/AccountTreeRounded'
import PlayArrowRoundedIcon from '@mui/icons-material/PlayArrowRounded'
import KeyboardArrowDownRoundedIcon from '@mui/icons-material/KeyboardArrowDownRounded'
import { WorkspaceSwitcher } from '../components/WorkspaceSwitcher'
import { ScientificField } from '../components/ScientificField'
import { DataTable } from '../spatial/DataTable'
import type { SurfaceSelection } from '../spatial/SurfaceCanvas'
import { useSpatialDocument } from '../spatial/useSpatialDocument'
import { solvePlate3D, validatePlate3D } from '../api'
import {
  edgeNodes,
  examplePlate,
  localNodes,
  parsePlate,
  rectangularPlate,
  type PlateDof,
  type PlateModel,
  type Vec,
} from './model'
import { PlateCanvas, quantities, type Quantity } from './PlateCanvas'
import '../spatial/spatial.css'

const STORAGE = 'nonlinear-studio.plate3d.model.v1'
const families = new Set<never>()
const categories = [
  'Geometry',
  'Material',
  'Supports',
  'Loads',
  'Nodes',
  'Elements',
] as const
type Category = (typeof categories)[number]
const edges = [
  ['all', 'All boundary edges'],
  ['x-', 'Local X minimum'],
  ['x+', 'Local X maximum'],
  ['y-', 'Local Y minimum'],
  ['y+', 'Local Y maximum'],
  ['selected', 'Selected node'],
]
const fmt = (v: number) => (v === 0 ? '0' : v.toExponential(5))
function geometryFields(m: PlateModel) {
  const ns = localNodes(m)
  const divisions = (axis: 'x' | 'y') => {
    const values = ns.map((n) => n[axis]).sort((a, b) => a - b)
    const tolerance =
      Math.max(values.at(-1)! - values[0], Number.MIN_VALUE) * 1e-8
    let groups = 1,
      previous = values[0]
    for (const value of values)
      if (value - previous > tolerance) {
        groups++
        previous = value
      }
    return Math.max(1, groups - 1)
  }
  return {
    ox: m.plane.origin[0],
    oy: m.plane.origin[1],
    oz: m.plane.origin[2],
    a: Math.max(...ns.map((n) => n.x)) - Math.min(...ns.map((n) => n.x)),
    b: Math.max(...ns.map((n) => n.y)) - Math.min(...ns.map((n) => n.y)),
    nx: divisions('x'),
    ny: divisions('y'),
    tilt: (Math.asin(Math.max(-1, Math.min(1, m.plane.ey[2]))) * 180) / Math.PI,
    yaw: (Math.atan2(m.plane.ex[1], m.plane.ex[0]) * 180) / Math.PI,
  }
}

export function PlateWorkbench({
  active,
  onFrame,
  onContinuum,
  onShell,
  on2D,
}: {
  active: boolean
  onFrame: () => void
  onContinuum: () => void
  onShell?: () => void
  on2D: () => void
}) {
  const doc = useSpatialDocument({ storage: STORAGE, example: examplePlate, parse: parsePlate,
    solve: solvePlate3D, validate: validatePlate3D, active })
  const { model, result, warning, error, message, setError, setMessage, cancel } = doc
  const running = doc.busy === 'solve'
  const importing = doc.busy === 'import'
  const busy = doc.busy !== null
  const [mode, setMode] = useState<'model' | 'results'>('model'),
    [category, setCategory] = useState<Category>('Geometry'),
    [properties, setProperties] = useState(false)
  const [selection, setSelection] = useState<SurfaceSelection>(null)
  const [dirty, setDirty] = useState(false), [formKey, setFormKey] = useState(0)
  const [menu, setMenu] = useState<HTMLElement | null>(null),
    [help, setHelp] = useState(false)
  const [geometry, setGeometry] = useState(() => geometryFields(model)),
    [material, setMaterial] = useState(model.material)
  const [supportTarget, setSupportTarget] = useState('x-'),
    [supportKind, setSupportKind] = useState('clamped'),
    [settlement, setSettlement] = useState(0)
  const [loadType, setLoadType] = useState('pressure'),
    [loadTarget, setLoadTarget] = useState('all'),
    [pressure, setPressure] = useState(-1000),
    [nodal, setNodal] = useState<Vec>([0, 0, 0])
  const [quantity, setQuantity] = useState<Quantity>('w'),
    [scale, setScale] = useState(10),
    [tables, setTables] = useState(true),
    [table, setTable] = useState('displacements')
  const input = useRef<HTMLInputElement>(null)
  const form = useRef<HTMLDivElement>(null)
  const resetFields = (m = model) => {
    setGeometry(geometryFields(m))
    setMaterial(m.material)
    setSettlement(0)
    setNodal([0, 0, 0])
    setPressure(m.pressures[0]?.value ?? -1000)
    setDirty(false)
    setFormKey((k) => k + 1)
  }
  const change = (next: PlateModel, text: string) => {
    doc.change(next, text)
    setMode('model')
    setDirty(false)
  }
  const restore = (next: PlateModel | undefined) => {
    if (!next) return
    setMode('model')
    resetFields(next)
    setSelection(null)
  }
  const undo = () => restore(doc.undo())
  const redo = () => restore(doc.redo())
  const openCategory = (c: Category) => {
    if (dirty && c !== category) return
    if (c === 'Loads' && !dirty) {
      setNodal(
        model.nodal_loads.find(
          (l) => selection?.kind === 'node' && l.node_id === selection.id,
        )?.value ?? [0, 0, 0],
      )
      setPressure(
        model.pressures.find(
          (p) => selection?.kind === 'element' && p.element_id === selection.id,
        )?.value ??
          model.pressures[0]?.value ??
          0,
      )
    }
    setCategory(c)
    setProperties(true)
    setMode('model')
  }
  const select = (s: SurfaceSelection) => {
    if (dirty || busy || mode === 'results') return
    setSelection(s)
    setCategory(s?.kind === 'node' ? 'Nodes' : 'Elements')
    setProperties(true)
  }
  const exportFile = () => doc.exportFile(`${model.name}.plate3d.json`)
  const openFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file || dirty || busy) return
    restore(await doc.importFile(file))
  }
  const run = () => {
    if (dirty || busy) return
    setMode('results')
    setTables(true)
    void doc.run()
  }
  useEffect(() => {
    if (active) document.title = 'Plate 3D workspace — Nonlinear Studio'
    else { setMenu(null); setHelp(false) }
  }, [active])
  useEffect(() => {
    if (!dirty || !active) return
    const guard = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', guard)
    return () => window.removeEventListener('beforeunload', guard)
  }, [active, dirty])
  const supportIds = () =>
    supportTarget === 'selected'
      ? selection?.kind === 'node'
        ? [selection.id]
        : []
      : [
          ...new Set(
            (supportTarget === 'all'
              ? ['x-', 'x+', 'y-', 'y+']
              : [supportTarget]
            ).flatMap((edge) => edgeNodes(model, edge)),
          ),
        ]
  const apply = () => {
    try {
      if (category === 'Geometry') {
        const g = geometry
        const next = rectangularPlate(g.a, g.b, g.nx, g.ny, g.tilt, g.yaw, [
          g.ox,
          g.oy,
          g.oz,
        ])
        change(
          { ...next, name: model.name, material: model.material },
          'Plate mesh replaced; supports and loads cleared. Undo restores the previous model.',
        )
        setSelection(null)
      } else if (category === 'Material')
        change({ ...model, material }, 'Plate material updated')
      else if (category === 'Supports') {
        const ids = supportIds()
        if (!ids.length)
          throw new Error('Select a node or boundary edge first.')
        const constraints = model.constraints.filter(
          (c) => !ids.includes(c.node_id),
        )
        const add = (node_id: number, dof: PlateDof) => {
          if (!constraints.some((c) => c.node_id === node_id && c.dof === dof))
            constraints.push({
              node_id,
              dof,
              value: dof === 'w' ? settlement : 0,
            })
        }
        if (supportKind !== 'free')
          for (const id of ids) {
            add(id, 'w')
            if (supportKind === 'clamped') {
              add(id, 'theta_x')
              add(id, 'theta_y')
            }
          }
        if (supportKind === 'hard')
          for (const edge of supportTarget === 'all'
            ? ['x-', 'x+', 'y-', 'y+']
            : [supportTarget])
            for (const id of edgeNodes(model, edge))
              add(id, edge[0] === 'x' ? 'theta_y' : 'theta_x')
        change(
          { ...model, constraints },
          'Supports updated on the selected target',
        )
      } else if (category === 'Loads') {
        if (loadType === 'nodal') {
          if (selection?.kind !== 'node')
            throw new Error('Select a mesh node first.')
          change(
            {
              ...model,
              nodal_loads: [
                ...model.nodal_loads.filter((l) => l.node_id !== selection.id),
                { node_id: selection.id, value: nodal },
              ],
            },
            'Nodal load updated',
          )
        } else {
          const ids =
            loadTarget === 'all'
              ? model.elements.map((e) => e.id)
              : selection?.kind === 'element'
                ? [selection.id]
                : []
          if (!ids.length) throw new Error('Select a plate element first.')
          change(
            {
              ...model,
              pressures: [
                ...model.pressures.filter((p) => !ids.includes(p.element_id)),
                ...ids.map((element_id) => ({ element_id, value: pressure })),
              ],
            },
            'Normal pressure updated',
          )
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Check the highlighted fields.')
      form.current
        ?.querySelector<HTMLInputElement>('[aria-invalid="true"]')
        ?.focus()
    }
  }
  const valid =
    category === 'Geometry'
      ? Object.values(geometry).every(Number.isFinite) &&
        geometry.a > 0 &&
        geometry.b > 0 &&
        Number.isInteger(geometry.nx) &&
        Number.isInteger(geometry.ny) &&
        geometry.nx > 0 &&
        geometry.ny > 0 &&
        (geometry.nx + 1) * (geometry.ny + 1) <= 200
      : category === 'Material'
        ? Object.values(material).every(Number.isFinite) &&
          material.E > 0 &&
          material.nu > -1 &&
          material.nu < 0.5 &&
          material.thickness > 0 &&
          material.shear_factor > 0
        : category === 'Supports'
          ? Number.isFinite(settlement) &&
            !(supportKind === 'hard' && supportTarget === 'selected')
          : category === 'Loads'
            ? loadType === 'pressure'
              ? Number.isFinite(pressure)
              : nodal.every(Number.isFinite)
            : true
  const numeric = (
    label: string,
    value: number,
    set: (v: number) => void,
    options: {
      unit?: string
      exclusiveMin?: number
      exclusiveMax?: number
      min?: number
      max?: number
      integer?: boolean
    } = {},
  ) => (
    <ScientificField
      label={label}
      value={value}
      {...options}
      onValueChange={(v) => {
        set(v)
        setDirty(true)
      }}
    />
  )
  const selectField = (
    label: string,
    value: string,
    set: (s: string) => void,
    options: string[][],
  ) => (
    <TextField
      select
      fullWidth
      label={label}
      value={value}
      onChange={(e) => {
        set(e.target.value)
        setDirty(true)
      }}
    >
      {options.map(([v, label]) => (
        <MenuItem key={v} value={v}>
          {label}
        </MenuItem>
      ))}
    </TextField>
  )
  const selectedNode = model.nodes.find(
      (n) => selection?.kind === 'node' && n.id === selection.id,
    ),
    selectedElement = model.elements.find(
      (e) => selection?.kind === 'element' && e.id === selection.id,
    )
  const rows: Record<string, string | number>[] = !result
    ? []
    : table === 'moments' || table === 'stress'
      ? result.elements.flatMap((e) =>
          e.points.map((p, i) => ({
            id: `${e.element_id}.${i + 1}`,
            element: e.element_id,
            point: i + 1,
            ...Object.fromEntries(
              (table === 'moments'
                ? [...p.moment, ...p.shear]
                : [...p.stress_top, ...p.stress_bottom]
              ).map((v, j) => [`v${j}`, fmt(v)]),
            ),
          })),
        )
      : result.nodes.map((n) => ({
          id: n.node_id,
          ...Object.fromEntries(
            (table === 'reactions'
              ? n.reaction
              : [...n.local, ...n.displacement]
            ).map((v, i) => [`v${i}`, fmt(v)]),
          ),
        }))
  const labels =
    table === 'moments'
      ? ['Mx (N)', 'My (N)', 'Mxy (N)', 'Qx (N/m)', 'Qy (N/m)']
      : table === 'stress'
        ? [
            'Top XX (Pa)',
            'Top YY (Pa)',
            'Top XY (Pa)',
            'Bottom XX (Pa)',
            'Bottom YY (Pa)',
            'Bottom XY (Pa)',
          ]
        : table === 'reactions'
          ? ['Rw (N)', 'Rθx (N·m)', 'Rθy (N·m)']
          : ['w (m)', 'θx (rad)', 'θy (rad)', 'UX (m)', 'UY (m)', 'UZ (m)']
  const columns = [
    ...(table === 'moments' || table === 'stress'
      ? [
          { key: 'element', label: 'Element' },
          { key: 'point', label: 'Point' },
        ]
      : [{ key: 'id', label: 'Node' }]),
    ...labels.map((label, i) => ({ key: `v${i}`, label, numeric: true })),
  ]

  return (
    <Box
      sx={{
        height: '100dvh',
        minWidth: 1120,
        display: 'flex',
        flexDirection: 'column',
        bgcolor: 'background.default',
      }}
    >
      <Stack
        direction="row"
        sx={{
          height: 56,
          flexShrink: 0,
          alignItems: 'center',
          gap: 1,
          px: 2,
          bgcolor: 'background.paper',
          borderBottom: '1px solid',
          borderColor: 'divider',
        }}
      >
        <AccountTreeRoundedIcon color="primary" />
        <Typography variant="h6" sx={{ fontSize: 16, mr: 2 }}>
          Nonlinear Studio
        </Typography>
        <Button
          color="inherit"
          endIcon={<KeyboardArrowDownRoundedIcon />}
          onClick={(e) => setMenu(e.currentTarget)}
          aria-haspopup="menu"
          aria-expanded={!!menu}
        >
          Project
        </Button>
        <ToggleButtonGroup
          size="small"
          exclusive
          value={mode}
          aria-label="Workbench mode"
          onChange={(_, v) => {
            if (v) setMode(v)
          }}
        >
          <ToggleButton value="model" disabled={busy}>
            Model
          </ToggleButton>
          <ToggleButton
            value="results"
            disabled={dirty || (!result && !error && !running)}
          >
            Results
          </ToggleButton>
        </ToggleButtonGroup>
        <Box sx={{ flex: 1 }} />
        <Button disabled={!doc.canUndo || dirty || busy} onClick={undo}>
          Undo
        </Button>
        <Button disabled={!doc.canRedo || dirty || busy} onClick={redo}>
          Redo
        </Button>
        <Button color="inherit" disabled={dirty || busy} onClick={exportFile}>
          Save project
        </Button>
        <Button color="inherit" onClick={() => setHelp(true)}>
          Guide
        </Button>
        <Button
          variant="contained"
          startIcon={<PlayArrowRoundedIcon />}
          sx={{ width: 158 }}
          disabled={importing || (dirty && !valid)}
          onClick={() => (dirty ? apply() : running ? cancel() : void run())}
        >
          {dirty ? 'Apply changes' : running ? 'Cancel' : 'Run analysis'}
        </Button>
      </Stack>
      <Menu anchorEl={menu} open={!!menu} onClose={() => setMenu(null)}>
        <MenuItem
          disabled={dirty || busy}
          onClick={() => {
            setMenu(null)
            input.current?.click()
          }}
        >
          Open plate JSON
        </MenuItem>
        <MenuItem
          disabled={dirty || busy}
          onClick={() => {
            setMenu(null)
            exportFile()
          }}
        >
          Export plate JSON
        </MenuItem>
        <MenuItem
          disabled={dirty || busy}
          onClick={() => {
            setMenu(null)
            const next = examplePlate()
            change(next, 'Example restored. Undo recovers the previous model.')
            resetFields(next)
            setSelection(null)
          }}
        >
          Reset plate example
        </MenuItem>
      </Menu>
      <input
        ref={input}
        hidden
        type="file"
        accept="application/json,.json"
        aria-label="Open plate project file"
        onChange={openFile}
      />
      <Stack
        direction="row"
        sx={{
          height: 38,
          flexShrink: 0,
          alignItems: 'center',
          px: 1,
          bgcolor: 'background.paper',
          borderBottom: '1px solid',
          borderColor: 'divider',
        }}
      >
        <WorkspaceSwitcher
          activeFamily="plate3d"
          draftFamilies={families}
          resultFamilies={families}
          onChange={() => {}}
          onSpatial={onFrame}
          onContinuumSpatial={onContinuum}
          onShellSpatial={onShell}
          onPlateSpatial={() => {}}
          onDimensionChange={(d) => {
            if (d === '2d') on2D()
          }}
        />
        <Divider orientation="vertical" flexItem sx={{ mx: 2, my: 1 }} />
        <InputBase
          key={model.name}
          defaultValue={model.name}
          disabled={dirty || busy}
          inputProps={{ 'aria-label': 'Plate model name', maxLength: 120 }}
          sx={{ flex: 1, fontSize: 13 }}
          onBlur={(e) => {
            const name = e.target.value.trim()
            if (name && name !== model.name)
              change({ ...model, name }, 'Model renamed')
            else e.target.value = model.name
          }}
        />
        <Typography variant="caption" color="text.secondary">
          {dirty ? 'Unapplied changes' : 'Local workspace'} · Linear static
        </Typography>
      </Stack>
      <Box sx={{ height: 2, flexShrink: 0 }}>
        {busy && (
          <LinearProgress
            aria-label={
              importing ? 'Opening plate project' : 'Solving plate model'
            }
          />
        )}
      </Box>
      {warning && <Alert severity="warning">{warning}</Alert>}
      {error && (
        <Alert severity="error" onClose={() => setError('')}>
          {error}
        </Alert>
      )}
      <Box sx={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {mode === 'model' && (
          <Box
            component="nav"
            aria-label="Plate model navigator"
            sx={{
              width: 232,
              flexShrink: 0,
              overflowY: 'auto',
              p: 1.5,
              borderRight: '1px solid',
              borderColor: 'divider',
              bgcolor: 'background.paper',
            }}
          >
            <Typography variant="overline">Plate · 3D</Typography>
            <Typography variant="body2" sx={{ mb: 2 }}>
              Spatial plate bending
            </Typography>
            {categories.map((c) => (
              <Button
                fullWidth
                key={c}
                disabled={busy || (dirty && c !== category)}
                variant={properties && category === c ? 'contained' : 'text'}
                sx={{ justifyContent: 'space-between', mb: 0.5 }}
                onClick={() => openCategory(c)}
              >
                {c}
                <Typography component="span" variant="caption">
                  {c === 'Nodes'
                    ? model.nodes.length
                    : c === 'Elements'
                      ? model.elements.length
                      : c === 'Supports'
                        ? model.constraints.length
                        : c === 'Loads'
                          ? model.pressures.length + model.nodal_loads.length
                          : ''}
                </Typography>
              </Button>
            ))}
            <Divider sx={{ my: 2 }} />
            <Typography variant="caption" color="text.secondary">
              MITC4 · {3 * model.nodes.length} DOFs
            </Typography>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ mt: 1, display: 'block' }}
            >
              One plane, any spatial orientation. Local axes define supports and
              result components.
            </Typography>
          </Box>
        )}
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            flex: 1,
            minWidth: 0,
            minHeight: 0,
          }}
        >
          <Stack
            direction="row"
            sx={{
              height: 48,
              flexShrink: 0,
              alignItems: 'center',
              gap: 1,
              px: 2,
              borderBottom: '1px solid',
              borderColor: 'divider',
              bgcolor: 'background.paper',
            }}
          >
            {mode === 'model' ? (
              <>
                <Button
                  disabled={dirty || busy}
                  onClick={() => openCategory('Geometry')}
                >
                  Geometry & mesh
                </Button>
                <Button
                  disabled={dirty || busy}
                  onClick={() => openCategory('Supports')}
                >
                  Support
                </Button>
                <Button
                  disabled={dirty || busy}
                  onClick={() => openCategory('Loads')}
                >
                  Load
                </Button>
              </>
            ) : (
              <>
                <TextField
                  select
                  label="Result quantity"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value as Quantity)}
                  sx={{ width: 240 }}
                >
                  {Object.entries(quantities).map(([key, v]) => (
                    <MenuItem key={key} value={key}>
                      {v.label}
                    </MenuItem>
                  ))}
                </TextField>
                <TextField
                  select
                  label="Deformation scale"
                  value={scale}
                  onChange={(e) => setScale(Number(e.target.value))}
                  sx={{ width: 155 }}
                >
                  {[0, 1, 10, 100, 1000].map((v) => (
                    <MenuItem key={v} value={v}>
                      {v === 0 ? 'Undeformed' : `×${v}`}
                    </MenuItem>
                  ))}
                </TextField>
                <Button
                  onClick={() => setTables((v) => !v)}
                  aria-expanded={tables}
                >
                  Results & tables
                </Button>
              </>
            )}
            <Box sx={{ flex: 1 }} />
            {mode === 'model' && (
              <Button
                onClick={() => setProperties((v) => !v)}
                aria-expanded={properties}
              >
                Properties
              </Button>
            )}
          </Stack>
          <PlateCanvas
            selectable={!busy && !dirty && mode === 'model'}
            model={model}
            result={mode === 'results' ? result : null}
            quantity={quantity}
            scale={mode === 'results' ? scale : 0}
            selection={selection}
            onSelect={select}
          />
          <Stack
            direction="row"
            sx={{
              height: 34,
              flexShrink: 0,
              px: 2,
              alignItems: 'center',
              borderTop: '1px solid',
              borderColor: 'divider',
              bgcolor: 'background.paper',
            }}
          >
            <Typography
              variant="caption"
              color={dirty ? 'warning.main' : 'text.secondary'}
            >
              {dirty
                ? 'Unapplied changes'
                : mode === 'results'
                  ? 'Local plate axes · positive pressure along +normal'
                  : 'w, θx, θy · m, rad · MITC4 bending'}
            </Typography>
            <Box sx={{ flex: 1 }} />
            {dirty && (
              <Button
                size="small"
                onClick={() => {
                  resetFields()
                  setError('')
                }}
              >
                Cancel changes
              </Button>
            )}
          </Stack>
        </Box>
        <Box
          ref={form}
          component="aside"
          aria-label="Plate properties"
          sx={{
            display: properties && mode === 'model' ? 'flex' : 'none',
            width: 320,
            flexShrink: 0,
            flexDirection: 'column',
            minHeight: 0,
            borderLeft: '1px solid',
            borderColor: 'divider',
            bgcolor: 'background.paper',
          }}
        >
          <Stack direction="row" sx={{ p: 2, alignItems: 'center' }}>
            <Typography variant="subtitle2">{category}</Typography>
            <Box sx={{ flex: 1 }} />
            <Button size="small" onClick={() => setProperties(false)}>
              Close
            </Button>
          </Stack>
          <Stack
            component="fieldset"
            disabled={busy}
            key={formKey}
            sx={{
              border: 0,
              m: 0,
              minWidth: 0,
              p: 2,
              pt: 0,
              gap: 2,
              overflowY: 'auto',
              flex: 1,
              minHeight: 0,
            }}
          >
            {category === 'Geometry' && (
              <>
                {numeric(
                  'Length X',
                  geometry.a,
                  (v) => setGeometry((g) => ({ ...g, a: v })),
                  { unit: 'm', exclusiveMin: 0 },
                )}
                {numeric(
                  'Length Y',
                  geometry.b,
                  (v) => setGeometry((g) => ({ ...g, b: v })),
                  { unit: 'm', exclusiveMin: 0 },
                )}
                {numeric(
                  'Divisions X',
                  geometry.nx,
                  (v) => setGeometry((g) => ({ ...g, nx: v })),
                  { integer: true, min: 1, max: 99 },
                )}
                {numeric(
                  'Divisions Y',
                  geometry.ny,
                  (v) => setGeometry((g) => ({ ...g, ny: v })),
                  { integer: true, min: 1, max: 99 },
                )}
                {numeric(
                  'Tilt',
                  geometry.tilt,
                  (v) => setGeometry((g) => ({ ...g, tilt: v })),
                  { unit: 'deg' },
                )}
                {numeric(
                  'Azimuth',
                  geometry.yaw,
                  (v) => setGeometry((g) => ({ ...g, yaw: v })),
                  { unit: 'deg' },
                )}
                {(['ox', 'oy', 'oz'] as const).map((axis, i) => (
                  <Box key={axis}>
                    {numeric(
                      `Origin ${'XYZ'[i]}`,
                      geometry[axis],
                      (v) => setGeometry((g) => ({ ...g, [axis]: v })),
                      { unit: 'm' },
                    )}
                  </Box>
                ))}
                <Typography variant="caption">
                  Creates a rectangle at the specified origin. Replacing the
                  mesh clears supports and loads; Undo restores them. Other
                  coplanar Q4 geometries can be opened as plate JSON.
                </Typography>
                {(geometry.nx + 1) * (geometry.ny + 1) > 200 && (
                  <Alert severity="error">
                    Use at most 200 nodes. Reduce mesh divisions.
                  </Alert>
                )}
              </>
            )}
            {category === 'Material' && (
              <>
                {numeric(
                  'Young modulus',
                  material.E,
                  (v) => setMaterial((m) => ({ ...m, E: v })),
                  { unit: 'Pa', exclusiveMin: 0 },
                )}
                {numeric(
                  'Poisson ratio',
                  material.nu,
                  (v) => setMaterial((m) => ({ ...m, nu: v })),
                  { exclusiveMin: -1, exclusiveMax: 0.5 },
                )}
                {numeric(
                  'Thickness',
                  material.thickness,
                  (v) => setMaterial((m) => ({ ...m, thickness: v })),
                  { unit: 'm', exclusiveMin: 0 },
                )}
                {numeric(
                  'Shear factor',
                  material.shear_factor,
                  (v) => setMaterial((m) => ({ ...m, shear_factor: v })),
                  { exclusiveMin: 0 },
                )}
                <Typography variant="caption">
                  One homogeneous isotropic material and constant thickness for
                  the entire plate.
                </Typography>
              </>
            )}
            {category === 'Supports' && (
              <>
                {selectField(
                  'Support target',
                  supportTarget,
                  setSupportTarget,
                  edges,
                )}
                {selectField('Support type', supportKind, setSupportKind, [
                  ['clamped', 'Clamped · w, θx, θy'],
                  ['hard', 'Hard simply supported'],
                  ['soft', 'Soft simply supported · w'],
                  ['free', 'Free · remove target supports'],
                ])}
                {numeric('Prescribed w', settlement, setSettlement, {
                  unit: 'm',
                })}
                <Typography variant="caption">
                  Hard support: X edges constrain w and θy; Y edges constrain w
                  and θx. Applying replaces constraints on the target. Rotations
                  are prescribed as zero.
                </Typography>
                {supportTarget === 'selected' && (
                  <Typography variant="caption">
                    {selection?.kind === 'node'
                      ? `Node ${selection.id}`
                      : 'Select a node from the mesh or Nodes table first.'}
                  </Typography>
                )}
                {supportTarget === 'selected' && supportKind === 'hard' && (
                  <Alert severity="error">
                    Choose an edge for hard support, or a different support
                    type.
                  </Alert>
                )}
                <DataTable
                  label="Plate supports"
                  columns={[
                    { key: 'id', label: 'Node' },
                    { key: 'dof', label: 'DOF' },
                    { key: 'value', label: 'Value' },
                  ]}
                  rows={model.constraints.map((c) => ({
                    id: c.node_id,
                    dof: c.dof,
                    value: fmt(c.value),
                  }))}
                />
              </>
            )}
            {category === 'Loads' && (
              <>
                {selectField('Load type', loadType, setLoadType, [
                  ['pressure', 'Normal pressure'],
                  ['nodal', 'Nodal generalized load'],
                ])}
                {loadType === 'pressure' ? (
                  <>
                    {selectField('Pressure target', loadTarget, setLoadTarget, [
                      ['all', 'All plate elements'],
                      ['selected', 'Selected element'],
                    ])}
                    {numeric('Normal pressure', pressure, setPressure, {
                      unit: 'Pa',
                    })}
                    <Typography variant="caption">
                      Positive along the plate normal ex × ey. Applying replaces
                      pressures on the target.
                    </Typography>
                  </>
                ) : (
                  <>
                    {(
                      [
                        'Normal force',
                        'Generalized moment θx',
                        'Generalized moment θy',
                      ] as const
                    ).map((label, j) => (
                      <Box key={label}>
                        {numeric(
                          label,
                          nodal[j],
                          (v) =>
                            setNodal(
                              (ns) =>
                                ns.map((n, i) => (i === j ? v : n)) as Vec,
                            ),
                          { unit: j === 0 ? 'N' : 'N·m' },
                        )}
                      </Box>
                    ))}
                    <Typography variant="caption">
                      {selection?.kind === 'node'
                        ? `Node ${selection.id}`
                        : 'Select a node first.'}{' '}
                      Moments are work-conjugate to director tilts: global
                      moment = −Mθx ey + Mθy ex.
                    </Typography>
                  </>
                )}
                <Button
                  disabled={
                    dirty ||
                    busy ||
                    (!model.pressures.length && !model.nodal_loads.length)
                  }
                  onClick={() =>
                    change(
                      { ...model, pressures: [], nodal_loads: [] },
                      'Loads cleared. Undo restores them.',
                    )
                  }
                >
                  Clear all loads
                </Button>
              </>
            )}
            {category === 'Nodes' && (
              <>
                <Typography variant="caption">
                  {selectedNode
                    ? `Selected node ${selectedNode.id}. Use Support or Load to assign it.`
                    : 'Select a node from the table or mesh.'}
                </Typography>
                <DataTable
                  label="Plate nodes"
                  columns={[
                    { key: 'id', label: 'Node' },
                    ...['x', 'y', 'z'].map((key) => ({
                      key,
                      label: `${key.toUpperCase()} (m)`,
                      numeric: true,
                    })),
                  ]}
                  rows={model.nodes.map((n) => ({
                    id: n.id,
                    x: fmt(n.x),
                    y: fmt(n.y),
                    z: fmt(n.z),
                  }))}
                  selected={selectedNode ? [selectedNode.id] : []}
                  onSelect={(id) => select({ kind: 'node', id })}
                />
              </>
            )}
            {category === 'Elements' && (
              <>
                <Typography variant="caption">
                  {selectedElement
                    ? `Selected element ${selectedElement.id}. Use Load for a local pressure.`
                    : 'Select a Q4 element.'}
                </Typography>
                <DataTable
                  label="Plate elements"
                  columns={[
                    { key: 'id', label: 'Element' },
                    { key: 'nodes', label: 'Ordered nodes' },
                  ]}
                  rows={model.elements.map((e) => ({
                    id: e.id,
                    nodes: e.nodes.join(', '),
                  }))}
                  selected={selectedElement ? [selectedElement.id] : []}
                  onSelect={(id) => select({ kind: 'element', id })}
                />
              </>
            )}
          </Stack>
        </Box>
        {mode === 'results' && tables && (
          <Box
            component="aside"
            aria-label="Plate numerical results"
            sx={{
              width: 460,
              flexShrink: 0,
              minHeight: 0,
              display: 'flex',
              flexDirection: 'column',
              borderLeft: '1px solid',
              borderColor: 'divider',
              bgcolor: 'background.paper',
            }}
          >
            <Box sx={{ p: 2 }}>
              <Typography variant="subtitle2">Plate results</Typography>
              {running && (
                <Typography role="status" variant="body2">
                  Solving the plate…
                </Typography>
              )}
              {!running && !result && (
                <Typography variant="body2">
                  No result available. Check the model and run analysis.
                </Typography>
              )}
              {result && (
                <>
                  <Typography variant="body2">
                    Max |w|{' '}
                    {fmt(
                      Math.max(
                        ...result.nodes.map((n) => Math.abs(n.local[0])),
                      ),
                    )}{' '}
                    m · Energy {fmt(result.strain_energy)} J
                  </Typography>
                  <Typography variant="caption">
                    w/t {fmt(result.max_w_over_t)} · Bending{' '}
                    {fmt(result.bending_energy)} J · Shear{' '}
                    {fmt(result.shear_energy)} J
                  </Typography>
                  <Alert
                    severity={result.validation.passed ? 'success' : 'warning'}
                    sx={{ mt: 1 }}
                  >
                    {result.validation.passed
                      ? 'Numerical checks passed'
                      : 'Review numerical checks'}{' '}
                    · residual {fmt(result.validation.relative_residual)}
                  </Alert>
                </>
              )}
            </Box>
            {result && (
              <>
                <Box sx={{ px: 2, pb: 2 }}>
                  <TextField
                    select
                    fullWidth
                    label="Result table"
                    value={table}
                    onChange={(e) => setTable(e.target.value)}
                  >
                    {[
                      ['displacements', 'Displacements'],
                      ['reactions', 'Generalized reactions'],
                      ['moments', 'Moments & shear · raw points'],
                      ['stress', 'Surface stress · raw points'],
                      ['checks', 'Checks & scope'],
                    ].map(([v, label]) => (
                      <MenuItem value={v} key={v}>
                        {label}
                      </MenuItem>
                    ))}
                  </TextField>
                </Box>
                {table === 'checks' ? (
                  <Stack sx={{ p: 2, pt: 0, gap: 1, overflowY: 'auto' }}>
                    {Object.entries(result.validation)
                      .filter(([k]) => k !== 'passed')
                      .map(([key, v]) => (
                        <Typography key={key} variant="caption">
                          {key.replaceAll('_', ' ')}:{' '}
                          {Array.isArray(v)
                            ? v.map(fmt).join(', ')
                            : fmt(v as number)}
                        </Typography>
                      ))}
                    {result.warnings.map((w) => (
                      <Alert key={w} severity="info">
                        {w}
                      </Alert>
                    ))}
                  </Stack>
                ) : (
                  <DataTable
                    key={table}
                    label={`Plate ${table}`}
                    columns={columns}
                    rows={rows}
                  />
                )}
              </>
            )}
          </Box>
        )}
      </Box>
      <Snackbar
        open={!!message && active}
        autoHideDuration={4500}
        onClose={() => setMessage('')}
        message={message}
      />
      <Dialog
        open={help}
        onClose={() => setHelp(false)}
        maxWidth="sm"
        fullWidth
        aria-labelledby="plate-guide-title"
      >
        <DialogTitle id="plate-guide-title">Spatial plate guide</DialogTitle>
        <DialogContent>
          <Stack spacing={2}>
            <Typography>
              Build a coplanar Q4 mesh, set material and thickness, apply
              supports and normal loads, then run analysis. The example is an
              inclined cantilever under −1 kPa pressure.
            </Typography>
            <Typography>
              MITC4 uses local w, θx, θy with γ = ∇w − θ. θx and θy are director
              tilts, not same-axis rotations. Results map translations along the
              normal and rotations as −θx ey + θy ex.
            </Typography>
            <Typography>
              Small-deflection, constant-thickness isotropic linear bending
              only. Membrane forces, warped or connected noncoplanar plates,
              shell action, plasticity, buckling and dynamics are outside this
              module.
            </Typography>
            <Typography>
              Pressure is normal to the plate. Moment resultants use N·m/m (N);
              shear resultants N/m. Surface stresses are local XX, YY, XY. Raw
              integration points remain authoritative; contour colors are
              element means.
            </Typography>
            <Typography>
              Models autosave locally; Save project exports JSON. Results are
              session-local. Opened meshes are validated by the backend. Orbit
              with drag or arrow keys, pan with Shift-drag, and use Fit or
              principal views. Node and element tables provide keyboard
              selection.
            </Typography>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setHelp(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
