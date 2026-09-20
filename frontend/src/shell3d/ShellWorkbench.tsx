import { useEffect, useRef, useState } from 'react'
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
import { useSpatialDocument } from '../spatial/useSpatialDocument'
import type { SurfaceSelection } from '../spatial/SurfaceCanvas'
import { solveShell3D, validateShell3D } from '../api'
import {
  defaultMesh,
  dofs,
  exampleShell,
  facetBasis,
  parseShell,
  shellMesh,
  targetNodes,
  type MeshSettings,
  type ShellDof,
  type ShellModel,
  type Vec,
} from './model'
import { ShellCanvas, quantities, type Quantity } from './ShellCanvas'
import '../spatial/spatial.css'
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
const fmt = (v: number) => (v === 0 ? '0' : v.toExponential(5))
const targets = [
  ['x-', 'Global X minimum'],
  ['x+', 'Global X maximum'],
  ['boundary', 'All boundary nodes'],
  ['selected', 'Selected node'],
]
export function ShellWorkbench({
  active,
  onFrame,
  onContinuum,
  onPlate,
  on2D,
}: {
  active: boolean
  onFrame: () => void
  onContinuum: () => void
  onPlate: () => void
  on2D: () => void
}) {
  const doc = useSpatialDocument({
    storage: 'nonlinear-studio.shell3d.model.v1',
    example: exampleShell,
    parse: parseShell,
    solve: solveShell3D,
    validate: validateShell3D,
    active,
  })
  const { model, result, busy } = doc
  const [mode, setMode] = useState<'model' | 'results'>('model'),
    [category, setCategory] = useState<Category>('Geometry'),
    [properties, setProperties] = useState(false)
  const [dirty, setDirty] = useState(false),
    [formKey, setFormKey] = useState(0),
    [selection, setSelection] = useState<SurfaceSelection>(null)
  const [geometry, setGeometry] = useState<MeshSettings>(defaultMesh),
    [material, setMaterial] = useState(model.material)
  const [target, setTarget] = useState('x-'),
    [support, setSupport] = useState('clamped'),
    [supportDof, setSupportDof] = useState<ShellDof>('uz'),
    [settlement, setSettlement] = useState(0)
  const [loadType, setLoadType] = useState('pressure'),
    [loadTarget, setLoadTarget] = useState('all'),
    [pressure, setPressure] = useState(-1000),
    [force, setForce] = useState<Vec>([0, 0, 0]),
    [moment, setMoment] = useState<Vec>([0, 0, 0])
  const [quantity, setQuantity] = useState<Quantity>('displacement'),
    [scale, setScale] = useState(10),
    [table, setTable] = useState('displacements'),
    [tables, setTables] = useState(true)
  const [menu, setMenu] = useState<HTMLElement | null>(null),
    [help, setHelp] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const geometryBaseline = useRef<MeshSettings>(defaultMesh)
  const reset = (m = model) => {
    setGeometry(geometryBaseline.current)
    setMaterial(m.material)
    setSettlement(0)
    setPressure(m.pressures[0]?.value ?? -1000)
    setForce([0, 0, 0])
    setMoment([0, 0, 0])
    setDirty(false)
    setFormKey((k) => k + 1)
  }
  const afterChange = (m: ShellModel) => {
    reset(m)
    setMode('model')
    setSelection(null)
  }
  useEffect(() => {
    if (active) document.title = 'Shell 3D workspace — Nonlinear Studio'
    else {
      setMenu(null)
      setHelp(false)
    }
  }, [active])
  useEffect(() => {
    if (!active || !dirty) return
    const guard = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', guard)
    return () => window.removeEventListener('beforeunload', guard)
  }, [active, dirty])
  const select = (s: SurfaceSelection) => {
    if (dirty || busy || mode === 'results') return
    setSelection(s)
    setCategory(s?.kind === 'node' ? 'Nodes' : 'Elements')
    setProperties(true)
  }
  const openCategory = (c: Category) => {
    if (dirty && c !== category) return
    setCategory(c)
    setProperties(true)
    setMode('model')
    if (c === 'Loads' && !dirty) {
      const l = model.nodal_loads.find(
        (l) => selection?.kind === 'node' && l.node_id === selection.id,
      )
      setForce(l?.force ?? [0, 0, 0])
      setMoment(l?.moment ?? [0, 0, 0])
      setPressure(
        model.pressures.find(
          (p) => selection?.kind === 'element' && p.element_id === selection.id,
        )?.value ??
          model.pressures[0]?.value ??
          -1000,
      )
    }
  }
  const apply = () => {
    try {
      let next = model,
        note = 'Shell model updated'
      if (category === 'Geometry') {
        next = {
          ...shellMesh(geometry),
          name: model.name,
          material: model.material,
        }
        note =
          'Shell mesh replaced; supports and loads cleared. Undo restores the previous model.'
      }
      if (category === 'Material') next = { ...model, material }
      if (category === 'Supports') {
        const ids = targetNodes(
          model,
          target,
          selection?.kind === 'node' ? selection.id : undefined,
        )
        if (!ids.length) throw new Error('Select a node first.')
        const constraints = model.constraints.filter(
          (c) =>
            !ids.includes(c.node_id) ||
            (support === 'single' && c.dof !== supportDof),
        )
        const names: ShellDof[] =
          support === 'clamped'
            ? [...dofs]
            : support === 'pinned'
              ? ['ux', 'uy', 'uz']
              : support === 'single'
                ? [supportDof]
                : []
        ids.forEach((node_id) =>
          names.forEach((dof) =>
            constraints.push({
              node_id,
              dof,
              value: support === 'single' ? settlement : 0,
            }),
          ),
        )
        next = { ...model, constraints }
        note = 'Supports updated on the selected target'
      }
      if (category === 'Loads') {
        if (loadType === 'nodal') {
          if (selection?.kind !== 'node')
            throw new Error('Select a node in the Nodes table first.')
          next = {
            ...model,
            nodal_loads: [
              ...model.nodal_loads.filter((l) => l.node_id !== selection.id),
              { node_id: selection.id, force, moment },
            ],
          }
        } else {
          const ids =
            loadTarget === 'all'
              ? model.elements.map((e) => e.id)
              : selection?.kind === 'element'
                ? [selection.id]
                : []
          if (!ids.length)
            throw new Error('Select an element in the Elements table first.')
          next = {
            ...model,
            pressures: [
              ...model.pressures.filter((p) => !ids.includes(p.element_id)),
              ...ids.map((element_id) => ({ element_id, value: pressure })),
            ],
          }
        }
        note = 'Loads updated'
      }
      const checked = doc.change(next, note)
      if (category === 'Geometry') geometryBaseline.current = { ...geometry }
      reset(checked)
      if (category === 'Geometry') setSelection(null)
    } catch (e) {
      doc.setError(e instanceof Error ? e.message : 'Check the input values.')
    }
  }
  const valid =
    category === 'Geometry'
      ? Object.values(geometry).every(Number.isFinite) &&
        geometry.length > 0 &&
        geometry.width > 0 &&
        Number.isInteger(geometry.nx) &&
        geometry.nx > 0 &&
        Number.isInteger(geometry.ny) &&
        geometry.ny >= 2 &&
        geometry.ny % 2 === 0 &&
        Math.abs(geometry.fold) < 170 &&
        (geometry.nx + 1) * (geometry.ny + 1) <= 100
      : category === 'Material'
        ? Object.values(material).every(Number.isFinite) &&
          material.E > 0 &&
          material.nu > -1 &&
          material.nu < 0.5 &&
          material.thickness > 0 &&
          material.shear_factor > 0 &&
          material.alpha_d >= 1e-6 &&
          material.alpha_d <= 1e-2
        : category === 'Supports'
          ? Number.isFinite(settlement) &&
            (target !== 'selected' || selection?.kind === 'node')
          : category === 'Loads'
            ? loadType === 'nodal'
              ? force.every(Number.isFinite) &&
                moment.every(Number.isFinite) &&
                selection?.kind === 'node'
              : Number.isFinite(pressure) &&
                (loadTarget === 'all' || selection?.kind === 'element')
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
    set: (v: string) => void,
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
      {options.map(([v, l]) => (
        <MenuItem key={v} value={v}>
          {l}
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
  const raw = ['membrane', 'moments', 'stress', 'strains'].includes(table)
  const labels =
    table === 'membrane'
      ? ['Nx (N/m)', 'Ny (N/m)', 'Nxy (N/m)']
      : table === 'moments'
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
          : table === 'strains'
            ? [
                'εx',
                'εy',
                'γxy',
                'κx (1/m)',
                'κy (1/m)',
                'κxy (1/m)',
                'γxz',
                'γyz',
              ]
            : table === 'reactions'
              ? [
                  'FX (N)',
                  'FY (N)',
                  'FZ (N)',
                  'MX (N·m)',
                  'MY (N·m)',
                  'MZ (N·m)',
                ]
              : [
                  'UX (m)',
                  'UY (m)',
                  'UZ (m)',
                  'RX (rad)',
                  'RY (rad)',
                  'RZ (rad)',
                ]
  const rows = !result
    ? []
    : raw
      ? result.elements.flatMap((e) =>
          e.points.map((p, i) => ({
            id: `${e.element_id}.${i + 1}`,
            element: e.element_id,
            point: i + 1,
            ...Object.fromEntries(
              (table === 'membrane'
                ? p.membrane
                : table === 'moments'
                  ? [...p.moment, ...p.shear]
                  : table === 'strains'
                    ? [...p.membrane_strain, ...p.curvature, ...p.shear_strain]
                    : [...p.stress_top, ...p.stress_bottom]
              ).map((v, j) => [`v${j}`, fmt(v)]),
            ),
          })),
        )
      : result.nodes.map((n) => ({
          id: n.node_id,
          ...Object.fromEntries(
            (table === 'reactions'
              ? [...n.force, ...n.moment]
              : [...n.displacement, ...n.rotation]
            ).map((v, j) => [`v${j}`, fmt(v)]),
          ),
        }))
  const columns = [
    ...(raw
      ? [
          { key: 'element', label: 'Element' },
          { key: 'point', label: 'Point' },
        ]
      : [{ key: 'id', label: 'Node' }]),
    ...labels.map((label, i) => ({ key: `v${i}`, label, numeric: true })),
  ]
  const run = () => {
    if (dirty || busy) return
    setMode('results')
    setTables(true)
    void doc.run()
  }
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
          <ToggleButton value="model" disabled={!!busy}>
            Model
          </ToggleButton>
          <ToggleButton
            value="results"
            disabled={dirty || (!result && !doc.error && !busy)}
          >
            Results
          </ToggleButton>
        </ToggleButtonGroup>
        <Box sx={{ flex: 1 }} />
        <Button
          disabled={!doc.canUndo || dirty || !!busy}
          onClick={() => {
            const m = doc.undo()
            if (m) afterChange(m)
          }}
        >
          Undo
        </Button>
        <Button
          disabled={!doc.canRedo || dirty || !!busy}
          onClick={() => {
            const m = doc.redo()
            if (m) afterChange(m)
          }}
        >
          Redo
        </Button>
        <Button
          color="inherit"
          disabled={dirty || !!busy}
          onClick={() =>
            doc.exportFile(
              `${model.name.replace(/[^\p{L}\p{N}._-]+/gu, '-')}.shell3d.json`,
            )
          }
        >
          Save project
        </Button>
        <Button color="inherit" onClick={() => setHelp(true)}>
          Guide
        </Button>
        <Button
          variant="contained"
          sx={{ width: 158 }}
          startIcon={busy ? undefined : <PlayArrowRoundedIcon />}
          disabled={dirty && !valid}
          onClick={busy ? doc.cancel : dirty ? apply : run}
        >
          {busy ? 'Cancel' : dirty ? 'Apply changes' : 'Run analysis'}
        </Button>
      </Stack>
      <Box
        sx={{
          px: 2,
          bgcolor: 'background.paper',
          borderBottom: '1px solid',
          borderColor: 'divider',
        }}
      >
        <WorkspaceSwitcher
          activeFamily="shell3d"
          draftFamilies={families}
          resultFamilies={families}
          onChange={() => {}}
          onSpatial={onFrame}
          onContinuumSpatial={onContinuum}
          onPlateSpatial={onPlate}
          onShellSpatial={() => {}}
          onDimensionChange={(v) => {
            if (v === '2d') on2D()
          }}
        />
      </Box>
      {busy && (
        <LinearProgress
          aria-label={busy === 'solve' ? 'Solving shell' : 'Validating project'}
        />
      )}
      {doc.warning && <Alert severity="warning">{doc.warning}</Alert>}
      {doc.error && (
        <Alert severity="error" onClose={() => doc.setError('')}>
          {doc.error}
        </Alert>
      )}
      <Box sx={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <Box
          component="aside"
          sx={{
            width: 232,
            flexShrink: 0,
            bgcolor: 'background.paper',
            borderRight: '1px solid',
            borderColor: 'divider',
            overflowY: 'auto',
          }}
        >
          <Box sx={{ p: 2 }}>
            <Typography variant="overline" color="text.secondary">
              SHELL / 3D
            </Typography>
            <InputBase
              value={model.name}
              disabled={dirty || !!busy}
              inputProps={{
                'aria-label': 'Shell project name',
                maxLength: 120,
              }}
              onChange={(e) => {
                if (e.target.value.trim())
                  doc.change(
                    { ...model, name: e.target.value },
                    'Project renamed',
                  )
              }}
              sx={{ fontWeight: 600, fontSize: 16, width: '100%' }}
            />
            <Typography variant="caption" color="text.secondary">
              Linear · Q4 / QLLL · SI units
            </Typography>
          </Box>
          <Divider />
          <Stack sx={{ p: 1 }} spacing={0.5}>
            {categories.map((c) => (
              <Button
                key={c}
                color="inherit"
                disabled={!!busy || (dirty && category !== c)}
                onClick={() => openCategory(c)}
                aria-pressed={mode === 'model' && category === c && properties}
                sx={{
                  justifyContent: 'space-between',
                  px: 1.5,
                  bgcolor:
                    mode === 'model' && category === c && properties
                      ? 'action.selected'
                      : undefined,
                }}
              >
                {c}
                <Typography
                  component="span"
                  variant="caption"
                  color="text.secondary"
                >
                  {c === 'Nodes'
                    ? model.nodes.length
                    : c === 'Elements'
                      ? model.elements.length
                      : c === 'Supports'
                        ? model.constraints.length
                        : c === 'Loads'
                          ? model.nodal_loads.length + model.pressures.length
                          : ''}
                </Typography>
              </Button>
            ))}
          </Stack>
          <Divider />
          <Box sx={{ p: 2 }}>
            <Typography variant="body2" sx={{ fontWeight: 600, mb: 1 }}>
              Spatial flat-facet shell
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Each Q4 is planar. Connected facets may have different normals.
              Six global degrees of freedom per node.
            </Typography>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ mt: 2, display: 'block' }}
            >
              Pressure follows the undeformed local normal. Local N / M / Q
              components change with facet axes.
            </Typography>
          </Box>
          {result && (
            <Box sx={{ p: 2, borderTop: '1px solid', borderColor: 'divider' }}>
              <Typography variant="caption" color="text.secondary">
                Strain energy
              </Typography>
              <Typography sx={{ fontVariantNumeric: 'tabular-nums' }}>
                {fmt(result.strain_energy)} J
              </Typography>
              <Typography
                variant="caption"
                color={
                  result.validation.passed ? 'success.main' : 'warning.main'
                }
              >
                {result.validation.passed
                  ? 'Numerical checks passed'
                  : 'Review numerical checks'}
              </Typography>
            </Box>
          )}
        </Box>
        {mode === 'model' && (
          <Box
            component="section"
            aria-label="Shell properties"
            sx={{
              width: 320,
              flexShrink: 0,
              bgcolor: 'background.paper',
              borderRight: '1px solid',
              borderColor: 'divider',
              display: properties ? 'flex' : 'none',
              flexDirection: 'column',
              minHeight: 0,
            }}
          >
            <Stack
              direction="row"
              sx={{
                p: 1.5,
                alignItems: 'center',
                borderBottom: '1px solid',
                borderColor: 'divider',
              }}
            >
              <Typography sx={{ fontWeight: 600, flex: 1 }}>
                {category}
              </Typography>
              <Button
                size="small"
                disabled={!!busy}
                onClick={() => setProperties(false)}
              >
                Close
              </Button>
            </Stack>
            <Box
              component="fieldset"
              disabled={!!busy}
              key={formKey}
              sx={{
                m: 0,
                p: 2,
                border: 0,
                minWidth: 0,
                overflowY: 'auto',
                flex: 1,
              }}
            >
              <Stack spacing={2}>
                {category === 'Geometry' && (
                  <>
                    <Typography variant="body2" color="text.secondary">
                      Generate a rectangular sheet with a crease at half width.
                      Fold 0° creates a flat shell.
                    </Typography>
                    {numeric(
                      'Length',
                      geometry.length,
                      (v) => setGeometry({ ...geometry, length: v }),
                      { unit: 'm', exclusiveMin: 0 },
                    )}
                    {numeric(
                      'Developed width',
                      geometry.width,
                      (v) => setGeometry({ ...geometry, width: v }),
                      { unit: 'm', exclusiveMin: 0 },
                    )}
                    {numeric(
                      'Longitudinal divisions',
                      geometry.nx,
                      (v) => setGeometry({ ...geometry, nx: v }),
                      { integer: true, min: 1 },
                    )}
                    {numeric(
                      'Transverse divisions (even)',
                      geometry.ny,
                      (v) => setGeometry({ ...geometry, ny: v }),
                      { integer: true, min: 2 },
                    )}
                    {numeric(
                      'Fold angle',
                      geometry.fold,
                      (v) => setGeometry({ ...geometry, fold: v }),
                      { unit: '°', exclusiveMin: -170, exclusiveMax: 170 },
                    )}
                    <Alert severity="info">
                      Applying geometry replaces the mesh and clears supports
                      and loads. Undo restores them. Imported geometry is
                      preserved until Apply.
                    </Alert>
                  </>
                )}
                {category === 'Material' && (
                  <>
                    {numeric(
                      "Young's modulus",
                      material.E,
                      (v) => setMaterial({ ...material, E: v }),
                      { unit: 'Pa', exclusiveMin: 0 },
                    )}
                    {numeric(
                      "Poisson's ratio",
                      material.nu,
                      (v) => setMaterial({ ...material, nu: v }),
                      { exclusiveMin: -1, exclusiveMax: 0.5 },
                    )}
                    {numeric(
                      'Thickness',
                      material.thickness,
                      (v) => setMaterial({ ...material, thickness: v }),
                      { unit: 'm', exclusiveMin: 0 },
                    )}
                    {numeric(
                      'Shear correction',
                      material.shear_factor,
                      (v) => setMaterial({ ...material, shear_factor: v }),
                      { exclusiveMin: 0 },
                    )}
                    {numeric(
                      'Drilling factor αd',
                      material.alpha_d,
                      (v) => setMaterial({ ...material, alpha_d: v }),
                      { min: 1e-6, max: 1e-2 },
                    )}
                    <Typography variant="caption" color="text.secondary">
                      Drilling is numerical stabilization. Compare a factor of
                      10 above and below your selected value.
                    </Typography>
                  </>
                )}
                {category === 'Supports' && (
                  <>
                    {selectField('Support target', target, setTarget, targets)}
                    {selectField('Support type', support, setSupport, [
                      ['clamped', 'Clamped · all six DOFs'],
                      ['pinned', 'Pinned · translations only'],
                      ['single', 'Prescribed single DOF'],
                      ['free', 'Remove all restraints'],
                    ])}
                    {support === 'single' && (
                      <>
                        {selectField(
                          'Global degree of freedom',
                          supportDof,
                          (v) => setSupportDof(v as ShellDof),
                          dofs.map((d) => [d, d.toUpperCase()]),
                        )}
                        {numeric(
                          'Prescribed value',
                          settlement,
                          setSettlement,
                          { unit: supportDof.startsWith('r') ? 'rad' : 'm' },
                        )}
                      </>
                    )}
                    <Typography variant="caption" color="text.secondary">
                      Targets use global coordinates. Single DOF preserves other
                      restraints; other types replace all restraints on the
                      target.
                    </Typography>
                    <Button
                      disabled={dirty || !model.constraints.length}
                      onClick={() =>
                        doc.change(
                          { ...model, constraints: [] },
                          'All supports removed',
                        )
                      }
                    >
                      Clear all supports
                    </Button>
                    <Typography variant="caption">
                      {model.constraints.length} prescribed degrees of freedom
                    </Typography>
                  </>
                )}
                {category === 'Loads' && (
                  <>
                    {selectField('Load type', loadType, setLoadType, [
                      ['pressure', 'Facet normal pressure'],
                      ['nodal', 'Global nodal force and moment'],
                    ])}
                    {loadType === 'pressure' ? (
                      <>
                        {selectField(
                          'Pressure target',
                          loadTarget,
                          setLoadTarget,
                          [
                            ['all', 'All elements'],
                            ['selected', 'Selected element'],
                          ],
                        )}
                        {numeric('Normal pressure', pressure, setPressure, {
                          unit: 'Pa',
                        })}
                        <Typography variant="caption" color="text.secondary">
                          Positive acts along each right-hand element normal.
                          Dead load; no follower stiffness.
                        </Typography>
                      </>
                    ) : (
                      <>
                        <Typography variant="body2">
                          {selectedNode
                            ? `Node ${selectedNode.id}`
                            : 'Select a node in the Nodes table.'}
                        </Typography>
                        {['X', 'Y', 'Z'].map((axis, i) => (
                          <Box key={axis}>
                            {numeric(
                              `Force ${axis}`,
                              force[i],
                              (v) =>
                                setForce(
                                  force.map((x, j) => (i === j ? v : x)) as Vec,
                                ),
                              { unit: 'N' },
                            )}
                          </Box>
                        ))}
                        {['X', 'Y', 'Z'].map((axis, i) => (
                          <Box key={axis}>
                            {numeric(
                              `Moment ${axis}`,
                              moment[i],
                              (v) =>
                                setMoment(
                                  moment.map((x, j) =>
                                    i === j ? v : x,
                                  ) as Vec,
                                ),
                              { unit: 'N·m' },
                            )}
                          </Box>
                        ))}
                      </>
                    )}
                    <Button
                      disabled={
                        dirty ||
                        (!model.nodal_loads.length && !model.pressures.length)
                      }
                      onClick={() =>
                        doc.change(
                          { ...model, nodal_loads: [], pressures: [] },
                          'All loads removed',
                        )
                      }
                    >
                      Clear all loads
                    </Button>
                  </>
                )}
                {category === 'Nodes' && (
                  <>
                    <Typography variant="body2">
                      Select a node to assign a support or nodal load.
                      Coordinates are defined by the generator or imported
                      project.
                    </Typography>
                    {selectedNode && (
                      <Typography variant="caption">
                        Node {selectedNode.id} · (
                        {[selectedNode.x, selectedNode.y, selectedNode.z]
                          .map(fmt)
                          .join(', ')}
                        ) m
                      </Typography>
                    )}
                    <Box sx={{ height: 420 }}>
                      <DataTable
                        label="Shell nodes"
                        columns={[
                          { key: 'id', label: 'ID' },
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
                    </Box>
                  </>
                )}
                {category === 'Elements' && (
                  <>
                    <Typography variant="body2">
                      Q4 nodes follow the right-hand normal. Adjacent facets
                      share oppositely directed edges.
                    </Typography>
                    {selectedElement && (
                      <>
                        <Typography variant="caption">
                          Element {selectedElement.id} local basis
                        </Typography>
                        {facetBasis(model, selectedElement.id).map((v, i) => (
                          <Typography key={i} variant="caption">
                            e{['x', 'y', 'z'][i]} = ({v.map(fmt).join(', ')})
                          </Typography>
                        ))}
                      </>
                    )}
                    <Box sx={{ height: 420 }}>
                      <DataTable
                        label="Shell elements"
                        columns={[
                          { key: 'id', label: 'ID' },
                          { key: 'nodes', label: 'Node IDs' },
                        ]}
                        rows={model.elements.map((e) => ({
                          id: e.id,
                          nodes: e.nodes.join(' → '),
                        }))}
                        selected={selectedElement ? [selectedElement.id] : []}
                        onSelect={(id) => select({ kind: 'element', id })}
                      />
                    </Box>
                  </>
                )}
              </Stack>
            </Box>
            {dirty && (
              <Stack
                direction="row"
                spacing={1}
                sx={{ p: 1.5, borderTop: '1px solid', borderColor: 'divider' }}
              >
                <Button fullWidth onClick={() => reset()}>
                  Cancel changes
                </Button>
                <Button
                  fullWidth
                  variant="contained"
                  disabled={!valid || !!busy}
                  onClick={apply}
                >
                  Apply
                </Button>
              </Stack>
            )}
          </Box>
        )}
        <Box
          sx={{
            flex: 1,
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <Stack
            direction="row"
            sx={{
              height: 48,
              flexShrink: 0,
              alignItems: 'center',
              px: 2,
              gap: 1,
              bgcolor: 'background.paper',
              borderBottom: '1px solid',
              borderColor: 'divider',
            }}
          >
            {mode === 'model' && (
              <Typography variant="body2" sx={{ flex: 1 }}>
                Model viewport
              </Typography>
            )}
            {mode === 'model' && (
              <Button
                onClick={() => setProperties((v) => !v)}
                aria-pressed={properties}
              >
                Properties
              </Button>
            )}
            {mode === 'results' && result && (
              <>
                <TextField
                  select
                  size="small"
                  label="Result quantity"
                  value={quantity}
                  sx={{ width: 180 }}
                  onChange={(e) => setQuantity(e.target.value as Quantity)}
                >
                  {Object.entries(quantities).map(([v, o]) => (
                    <MenuItem key={v} value={v}>
                      {o.label}
                    </MenuItem>
                  ))}
                </TextField>
                <TextField
                  select
                  label="Deformation scale"
                  value={scale}
                  onChange={(e) => setScale(Number(e.target.value))}
                  sx={{ width: 130 }}
                >
                  {[0, 1, 10, 100, 1000].map((v) => (
                    <MenuItem key={v} value={v}>
                      {v === 0 ? 'Undeformed' : `×${v}`}
                    </MenuItem>
                  ))}
                </TextField>
                <Button onClick={() => setTables((v) => !v)}>
                  {tables ? 'Hide tables' : 'Show tables'}
                </Button>
              </>
            )}
          </Stack>
          <Box
            sx={{
              flex: 1,
              minHeight: 240,
              position: 'relative',
              display: 'flex',
            }}
          >
            <ShellCanvas
              model={model}
              result={mode === 'results' ? result : null}
              quantity={quantity}
              scale={scale}
              selection={selection}
              onSelect={select}
              selectable={!dirty && !busy && mode === 'model'}
            />
          </Box>
          <Box
            sx={{
              px: 2,
              py: 0.75,
              borderTop: '1px solid',
              borderColor: 'divider',
              bgcolor: 'background.paper',
            }}
          >
            <Typography variant="caption" color="text.secondary">
              Drag to orbit · Shift-drag to pan · Scroll to zoom · F to fit
              {dirty
                ? ' · Unapplied changes'
                : selection
                  ? ` · ${selection.kind} ${selection.id}`
                  : ''}
            </Typography>
          </Box>
        </Box>
        {mode === 'results' && tables && (
          <Box
            component="section"
            aria-label="Shell result tables"
            sx={{
              width: 460,
              flexShrink: 0,
              borderLeft: '1px solid',
              borderColor: 'divider',
              bgcolor: 'background.paper',
              display: 'flex',
              flexDirection: 'column',
              minHeight: 0,
            }}
          >
            <Box
              sx={{ p: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}
            >
              <TextField
                select
                fullWidth
                label="Result table"
                value={table}
                onChange={(e) => setTable(e.target.value)}
              >
                {[
                  ['displacements', 'Global displacements'],
                  ['membrane', 'Raw membrane resultants'],
                  ['moments', 'Raw moments and shear'],
                  ['stress', 'Raw surface stresses'],
                  ['strains', 'Raw strains and curvatures'],
                  ['reactions', 'Global support reactions'],
                  ['checks', 'Energy and numerical checks'],
                ].map(([v, l]) => (
                  <MenuItem key={v} value={v}>
                    {l}
                  </MenuItem>
                ))}
              </TextField>
            </Box>
            {!result ? (
              <Box sx={{ p: 3 }}>
                <Typography color="text.secondary">
                  {busy
                    ? 'Solving the shell model…'
                    : doc.error
                      ? 'Analysis failed. Correct the model and run again.'
                      : 'Run analysis to see results.'}
                </Typography>
              </Box>
            ) : table === 'checks' ? (
              <Box sx={{ p: 2, overflowY: 'auto' }}>
                <Stack spacing={1.5}>
                  <Alert
                    severity={result.validation.passed ? 'success' : 'warning'}
                  >
                    {result.validation.passed
                      ? 'Numerical checks passed'
                      : 'Review numerical checks'}
                  </Alert>
                  {Object.entries(result.energy).map(([k, v]) => (
                    <Typography key={k} variant="body2">
                      {k[0].toUpperCase() + k.slice(1)} energy: {fmt(v)} J
                    </Typography>
                  ))}
                  <Typography variant="body2">
                    Drilling fraction: {fmt(result.drilling_fraction)}
                  </Typography>
                  <Typography variant="body2">
                    Max |U| / t: {fmt(result.max_displacement_over_t)}
                  </Typography>
                  <Divider />
                  {Object.entries(result.validation)
                    .filter(([k]) => k !== 'passed')
                    .map(([k, v]) => (
                      <Typography key={k} variant="caption">
                        {k.replaceAll('_', ' ')}:{' '}
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
              </Box>
            ) : (
              <>
                <Box sx={{ px: 2, py: 1 }}>
                  <Typography variant="caption" color="text.secondary">
                    {raw
                      ? 'Four raw Gauss points per element · local axes · no smoothing'
                      : 'Global coordinates · support reactions include prescribed-motion effects'}
                  </Typography>
                </Box>
                <DataTable
                  label="Shell results"
                  rows={rows}
                  columns={columns}
                />
              </>
            )}
          </Box>
        )}
      </Box>
      <Stack
        direction="row"
        sx={{
          height: 34,
          px: 2,
          alignItems: 'center',
          gap: 2,
          bgcolor: 'background.paper',
          borderTop: '1px solid',
          borderColor: 'divider',
          flexShrink: 0,
        }}
      >
        <Typography variant="caption">
          {model.nodes.length} nodes · {model.elements.length} Q4 facets ·{' '}
          {model.nodes.length * 6} DOFs
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ flex: 1 }}>
          Linear static · membrane + bending + assumed shear
        </Typography>
        <Typography variant="caption" color="text.secondary">
          m · N · Pa · rad
        </Typography>
      </Stack>
      <Menu anchorEl={menu} open={!!menu} onClose={() => setMenu(null)}>
        {[
          ['example', 'Load folded-shell example'],
          ['flat', 'Load flat-shell example'],
          ['open', 'Open project…'],
        ].map(([v, label]) => (
          <MenuItem
            key={v}
            disabled={dirty || !!busy}
            onClick={() => {
              setMenu(null)
              if (v === 'open') {
                input.current?.click()
                return
              }
              const m = exampleShell()
              if (v === 'flat') {
                const flat = shellMesh({ ...defaultMesh, fold: 0 })
                m.nodes = flat.nodes
                m.name = 'Flat cantilever shell'
              }
              afterChange(
                doc.change(
                  m,
                  'Example loaded. Undo restores the previous model.',
                ),
              )
            }}
          >
            {label}
          </MenuItem>
        ))}
      </Menu>
      <input
        ref={input}
        type="file"
        accept=".json,application/json"
        hidden
        onChange={async (e) => {
          const file = e.target.files?.[0]
          e.target.value = ''
          if (!file || dirty || busy) return
          const m = await doc.importFile(file)
          if (m) afterChange(m)
        }}
      />
      <Dialog
        open={help}
        onClose={() => setHelp(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Shell 3D · flat-facet workflow</DialogTitle>
        <DialogContent>
          <Stack spacing={2}>
            <Typography>
              Generate a flat or folded mesh, set material and thickness, then
              assign supports and loads. The initial folded cantilever is ready
              to run. Import shell3d-1 JSON for other planar Q4 facet
              geometries.
            </Typography>
            <Typography>
              Each node has UX, UY, UZ, RX, RY, RZ. Local director tilts are θx
              = −ey · ω and θy = ex · ω. Positive pressure acts along each facet
              normal.
            </Typography>
            <Typography>
              QLLL assumed shear, 2×2 integration, and consistent drilling
              stabilization follow the L baseline in the supplied 3D-Shell
              guide. Strain uses ε(z) = εm − zκ; the work-conjugate bending
              resultant is M = −∫zσ dz.
            </Typography>
            <Typography>
              Results include membrane N (N/m), bending M (N·m/m), shear Q
              (N/m), top/bottom stresses (Pa), reactions and energy. Raw Gauss
              values are authoritative. Contours show element means in each
              element's local axes.
            </Typography>
            <Alert severity="info">
              This workspace solves linear planar facets with small motion.
              General curved-shell kinematics, finite rotations, nonlinear
              materials, buckling and dynamics are outside this implementation.
            </Alert>
            <Typography variant="body2">
              Check drilling sensitivity by changing αd tenfold in both
              directions. High drilling energy or large displacement/thickness
              needs engineering review. Cancel stops waiting for the response;
              the server may finish its calculation.
            </Typography>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setHelp(false)}>Close guide</Button>
        </DialogActions>
      </Dialog>
      <Snackbar
        open={active && !!doc.message}
        autoHideDuration={4000}
        onClose={() => doc.setMessage('')}
        message={doc.message}
      />
    </Box>
  )
}
