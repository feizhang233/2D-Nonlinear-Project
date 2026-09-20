import { useState } from 'react'
import { Alert, Button, Chip, LinearProgress, MenuItem, Tab, Tabs, TextField } from '@mui/material'
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown'
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp'
import { DataTable, type Column } from './DataTable'
import { dofs, forces, type Result3D, type Selection } from './model'
const number = (n: number) => Math.abs(n) < 1e-14 ? '0' : n.toPrecision(6)
export function SpatialResults({ result, running, error, expanded, onExpand, onRun, onCancel, selection, onSelect }: {
  result: Result3D | null; running: boolean; error: string | null; expanded: boolean; onExpand: () => void; onRun: () => void; onCancel: () => void; selection: Selection
  onSelect: (kind: 'nodes' | 'elements', id: number | null, extend: boolean) => void
}) {
  const [tab, setTab] = useState('displacements'); const [member, setMember] = useState(0)
  const current = result?.elements.find(e => selection.elements.includes(e.element_id)) ?? result?.elements.find(e => e.element_id === member) ?? result?.elements[0]
  let columns: Column[] = []; let rows: Record<string, string | number>[] = []
  if (result && tab === 'displacements') {
    columns = [{ key: 'id', label: 'Node' }, ...dofs.map(key => ({ key, label: `${key.toUpperCase()} (${key.length === 1 ? 'mm' : 'mrad'})`, numeric: true }))]
    rows = result.nodal_displacements.map(n => Object.fromEntries([['id', n.node_id], ...dofs.map(d => [d, number(n[d] * 1000)])]))
  } else if (result && tab === 'reactions') {
    columns = [{ key: 'id', label: 'Node' }, ...forces.map(key => ({ key, label: `${key.toUpperCase()} (${key[0] === 'f' ? 'kN' : 'kN·m'})`, numeric: true }))]
    rows = result.nodal_reactions.map(n => Object.fromEntries([['id', n.node_id], ...forces.map(d => [d, number(n[d] / 1000)])]))
  } else if (result && tab === 'ends') {
    columns = [{ key: 'id', label: 'Member' }, { key: 'end', label: 'End' }, ...['N', 'Vy', 'Vz', 'T', 'My', 'Mz'].map((label, i) => ({ key: `f${i}`, label: `${label} (${i < 3 ? 'kN' : 'kN·m'})`, numeric: true }))]
    rows = result.elements.flatMap(e => [0, 1].map(end => Object.fromEntries([['id', e.element_id], ['end', end ? 'j' : 'i'], ...e.local_end_forces.slice(end * 6, end * 6 + 6).map((f, i) => [`f${i}`, number(f / 1000)])])))
  } else if (current && tab === 'fields') {
    const names = ['axial_force', 'shear_force_y', 'shear_force_z', 'torsional_moment', 'bending_moment_y', 'bending_moment_z'] as const
    columns = [{ key: 'x', label: 'x local (m)', numeric: true }, ...['N', 'Vy', 'Vz', 'T', 'My', 'Mz'].map((label, i) => ({ key: names[i], label: `${label} (${i < 3 ? 'kN' : 'kN·m'})`, numeric: true })), ...current.fields.normal_stress.map((_, i) => ({ key: `s${i}`, label: `σ point ${i + 1} (MPa)`, numeric: true }))]
    rows = current.fields.x_local.map((x, i) => Object.fromEntries([['id', i], ['x', number(x)], ...names.map(key => [key, number(current.fields[key][i] / 1000)]), ...current.fields.normal_stress.map((values, p) => [`s${p}`, number(values[i] / 1e6)])]))
  }
  const peak = result ? Math.max(...result.nodal_displacements.map(n => Math.hypot(n.u, n.v, n.w))) * 1000 : 0
  return <section className={`spatial-results ${expanded ? 'expanded' : ''}`} aria-label="Analysis results">
    <div className="spatial-results-heading"><Button color="inherit" size="small" onClick={onExpand} aria-expanded={expanded} endIcon={expanded ? <KeyboardArrowDownIcon /> : <KeyboardArrowUpIcon />}>Analysis results</Button>
      {running ? <span role="status">Solving 3D frame…</span> : result ? <><Chip size="small" color={result.validation.passed ? 'success' : 'warning'} label={result.validation.passed ? 'Checks passed' : 'Review checks'} /><span className="spatial-muted">Max displacement {number(peak)} mm</span></> : <span className="spatial-muted">{error ? 'Analysis needs attention' : 'Linear static · ready when you are'}</span>}
      <div className="spatial-spacer" />{running ? <Button size="small" onClick={onCancel}>Cancel analysis</Button> : error ? <Button size="small" onClick={onRun}>Retry analysis</Button> : null}
    </div>
    {running && <LinearProgress />}
    {expanded && <>
      {error && <Alert severity="error" sx={{ m: 1, flexShrink: 0, overflow: 'auto', maxHeight: 120 }}>{error}</Alert>}
      {result ? <>
        {!result.validation.passed && <Alert severity="warning">The solver returned a result, but numerical validation did not pass. Review constraints, section properties, and the checks below.</Alert>}
        <div className="results-tabs"><Tabs value={tab} onChange={(_, value) => setTab(value)} variant="scrollable" scrollButtons="auto" aria-label="Result tables"><Tab value="displacements" label="Displacements" /><Tab value="reactions" label="Reactions" /><Tab value="ends" label="Member end forces" /><Tab value="fields" label="Section forces & stress" /><Tab value="checks" label="Checks" /></Tabs>
          {tab === 'fields' && <TextField size="small" select label="Member" value={current?.element_id ?? ''} onChange={e => { setMember(Number(e.target.value)); onSelect('elements', Number(e.target.value), false) }} sx={{ minWidth: 100, m: .5 }}>{result.elements.map(e => <MenuItem key={e.element_id} value={e.element_id}>E{e.element_id}</MenuItem>)}</TextField>}
        </div>
        {tab === 'checks' ? <DataTable label="Validation checks" columns={[{ key: 'name', label: 'Check' }, { key: 'value', label: 'Value', numeric: true }]} rows={Object.entries(result.validation).filter(([, value]) => typeof value === 'number' || typeof value === 'boolean').map(([name, value], id) => ({ id, name: name.replaceAll('_', ' '), value: typeof value === 'number' ? number(value) : String(value) }))} /> : <DataTable key={tab} label={tab === 'displacements' || tab === 'reactions' ? 'Result nodes' : 'Result members'} columns={columns} rows={rows} selected={tab === 'ends' ? selection.elements : selection.nodes} onSelect={tab === 'fields' ? undefined : (id, extend) => onSelect(tab === 'ends' ? 'elements' : 'nodes', id, extend)} />}
        <div className="results-footnote">{tab === 'ends' ? 'Local nodal end forces; signs follow each member’s local axes.' : tab === 'fields' ? 'Section forces on the positive local-x face. Normal stress includes axial force and biaxial bending.' : 'Global axes · translations in mm · rotations in mrad · forces in kN.'}</div>
      </> : !running && !error && <div className="results-placeholder">Run analysis to inspect displacement, reactions, six member-force components, and section stresses.</div>}
    </>}
  </section>
}
