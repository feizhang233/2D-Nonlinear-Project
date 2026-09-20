import { useState } from 'react'
import { Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Checkbox, Divider, FormControlLabel, MenuItem, Stack, TextField, Typography } from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import { NumericForm, type Field } from './NumericForm'
import { DataTable } from './DataTable'
import { PropertyEditor, type DrawingProperties } from './PropertyEditor'
import { defaultSection, dofs, forces, insertMember, insertNode, lineKeys, norm, parseModel3D, sub, xyz, type LineLoad, type Model3D, type NodalLoad, type Selection, type Support, type Tool, type Vec3 } from './model'
export const toolNames: Record<Tool, string> = { select: 'Properties', node: 'Node', member: 'Element', material: 'Materials', section: 'Sections', support: 'Supports', load: 'Loads', tables: 'Model tables' }
const title = (heading: string, description: string) => <div className="inspector-intro"><Typography variant="subtitle1">{heading}</Typography><Typography variant="body2" color="text.secondary">{description}</Typography></div>
export function Inspector({ model, revision, selection, tool, defaults, templates, onTemplates, onExample, onDefaults, onChange, onSelect, onDelete, onTool, onMessage }: {
  revision: number; templates: DrawingProperties; onTemplates: (value: DrawingProperties) => void; onExample: () => void
  model: Model3D; selection: Selection; tool: Tool; defaults: ReturnType<typeof defaultSection>; onDefaults: (value: ReturnType<typeof defaultSection>) => void
  onChange: (model: Model3D, message?: string) => void; onSelect: (kind: 'nodes' | 'elements', id: number | null, extend: boolean) => void; onDelete: () => void; onTool: (tool: Tool) => void; onMessage: (message: string) => void
}) {
  const selectedNode = model.nodes.find(n => selection.nodes.includes(n.id)); const selectedMember = model.elements.find(e => selection.elements.includes(e.id))
  const [table, setTable] = useState<'nodes' | 'elements'>('nodes')
  const count = selection.nodes.length + selection.elements.length
  const editorKey = `${selection.nodes.join(',')}-${selection.elements.join(',')}-${revision}`
  const coordinateFields = (prefix: string, p: Vec3, label = ''): Field[] => p.map((value, i) => ({ key: `${prefix}${'xyz'[i]}`, label: `${label}${'XYZ'[i]} (m)`, value }))
  return <div className="spatial-inspector-body">
    <div className="inspector-selection"><span>{selection.nodes.length} nodes · {selection.elements.length} members selected</span>{count > 0 && <Button size="small" onClick={() => onSelect('nodes', null, false)}>Clear</Button>}</div>
    {(tool === 'select' || tool === 'node') && <>
      {title(selectedNode ? `Node ${selectedNode.id}` : 'Exact coordinates', selectedNode ? 'Edit this node in global coordinates. Connected members move with it.' : 'Add a node with global X, Y, Z coordinates. Values are in metres.')}
      <NumericForm key={editorKey} fields={coordinateFields('', selectedNode ? xyz(selectedNode) : [0, 0, 0])} action={selectedNode ? 'Update node' : 'Add node'} onSubmit={v => {
        const p: Vec3 = [v.x, v.y, v.z]
        if (selectedNode) {
          if (model.nodes.some(n => n.id !== selectedNode.id && norm(sub(xyz(n), p)) < 1e-8)) throw new Error('Another node already occupies this point. Delete or redraw connected members to merge nodes.')
          const next = structuredClone(model); Object.assign(next.nodes[selectedNode.id - 1], { x: v.x, y: v.y, z: v.z }); onChange(next, `Node ${selectedNode.id} updated`)
        } else { const inserted = insertNode(model, p); onChange(inserted.model, `Node ${inserted.id} ready`); onSelect('nodes', inserted.id, false) }
      }} />
      {selectedNode && <Button fullWidth variant="outlined" onClick={() => onSelect('nodes', null, false)}>Add another node</Button>}
      {selectedMember && <Box className="selection-summary"><Typography variant="subtitle2">Member E{selectedMember.id}</Typography><Typography variant="body2">Node {selectedMember.node_i} → {selectedMember.node_j} · {norm(sub(xyz(model.nodes[selectedMember.node_j - 1]), xyz(model.nodes[selectedMember.node_i - 1]))).toFixed(3)} m</Typography><Button size="small" onClick={() => onTool('material')}>Edit material</Button><Button size="small" onClick={() => onTool('section')}>Edit section</Button></Box>}
      {title('Selection', 'Click a node or member. Hold Shift to add to the selection. Model tables provide the same selection by ID.')}
      <Stack direction="row" spacing={1}><Button variant="outlined" onClick={() => onTool('tables')}>Model tables</Button><Button color="error" disabled={!count} onClick={onDelete}>Delete selected</Button></Stack>
    </>}
    {tool === 'member' && <>
      {title('Connect two points', 'Click a start and end point on the active plane. Keep clicking to continue. Right-click finishes the chain; Esc returns to Select.')}
      <div className="inspector-note">Grid intersections snap automatically. Existing nodes and crossing members connect at shared points.</div>
      <Divider />
      {title('Draw with coordinates', 'Enter two global points. Existing nodes are reused; exact coordinates are never rounded to the grid.')}
      <NumericForm fields={[...coordinateFields('a', [0, 0, 0], 'Start '), ...coordinateFields('b', [6, 0, 0], 'End ')]} action="Add member" onSubmit={v => {
        const inserted = insertMember(model, [v.ax, v.ay, v.az], [v.bx, v.by, v.bz], defaults); onChange(inserted.model, 'Member added; shared joints connected')
      }} />
      <Stack direction="row" spacing={1}><Button variant="outlined" onClick={() => onTool('material')}>Drawing material</Button><Button variant="outlined" onClick={() => onTool('section')}>Drawing section</Button></Stack>
    </>}
    {(tool === 'material' || tool === 'section') && <PropertyEditor key={`${tool}-${selection.elements.join(',')}`} kind={tool} model={model} selection={selection} defaults={defaults} templates={templates} onTemplates={onTemplates} onDefaults={onDefaults} onChange={onChange} onMessage={onMessage} />}
    {tool === 'support' && <SupportEditor key={editorKey} model={model} selection={selection} onChange={onChange} />}
    {tool === 'load' && <LoadEditor key={editorKey} model={model} selection={selection} onChange={onChange} />}
    {tool === 'tables' && <>
      {title('Model data', 'Select rows here, then assign supports, loads, or section properties. Selection is shared with both views.')}
      <TextField select label="Objects" value={table} onChange={e => setTable(e.target.value as typeof table)}><MenuItem value="nodes">Nodes ({model.nodes.length})</MenuItem><MenuItem value="elements">Members ({model.elements.length})</MenuItem></TextField>
      <div className="inspector-table"><DataTable label={table === 'nodes' ? 'Nodes' : 'Members'} selected={selection[table]} onSelect={(id, extend) => onSelect(table, id, extend)}
        columns={table === 'nodes' ? [{ key: 'id', label: 'ID' }, ...['x', 'y', 'z'].map(key => ({ key, label: `${key.toUpperCase()} (m)`, numeric: true }))] : [{ key: 'id', label: 'ID' }, { key: 'node_i', label: 'Start' }, { key: 'node_j', label: 'End' }, { key: 'length', label: 'L (m)', numeric: true }]}
        rows={table === 'nodes' ? model.nodes.map(n => ({ ...n })) : model.elements.map(e => ({ id: e.id, node_i: e.node_i, node_j: e.node_j, length: norm(sub(xyz(model.nodes[e.node_j - 1]), xyz(model.nodes[e.node_i - 1]))).toFixed(3) }))} /></div>
      <Button color="error" variant="outlined" disabled={!count} onClick={onDelete}>Delete selected objects</Button>
      <Divider />
      <Button variant="outlined" onClick={onExample}>Load 3D example</Button>
      <AnalysisSettings key={revision} model={model} onChange={onChange} />
    </>}
  </div>
}
function SupportEditor({ model, selection, onChange }: { model: Model3D; selection: Selection; onChange: (model: Model3D, message?: string) => void }) {
  const existing = model.supports.find(s => s.node_id === selection.nodes[0]); const [fixed, setFixed] = useState(dofs.filter(d => existing ? existing[d] : true)); const [local, setLocal] = useState(!!existing?.axes)
  const axes = existing?.axes ?? [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
  return <>{title('Restrain selected nodes', 'Choose constraints and apply. Prescribed translations are in metres; rotations are in radians.')}
    {!selection.nodes.length && <Alert severity="info">Select nodes in a view or in Model tables.</Alert>}
    <Stack direction="row" sx={{ flexWrap: "wrap", gap: 1 }}>{[['Fixed', dofs], ['Pinned', dofs.slice(0, 3)], ['Z roller', ['w']]].map(([label, values]) => <Button size="small" variant="outlined" key={label as string} onClick={() => setFixed(values as typeof fixed)}>{label}</Button>)}</Stack>
    <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)' }}>{dofs.map(d => <FormControlLabel key={d} control={<Checkbox checked={fixed.includes(d)} onChange={(_, checked) => setFixed(checked ? [...fixed, d] : fixed.filter(v => v !== d))} />} label={d.toUpperCase()} />)}</Box>
    <FormControlLabel control={<Checkbox checked={local} onChange={(_, checked) => setLocal(checked)} />} label="Use inclined support axes" />
    <NumericForm fields={[...fixed.map(d => ({ key: d, label: `${d} (${d.length === 1 ? 'm' : 'rad'})`, value: existing?.[`${d}_value`] ?? 0 })), ...(local ? axes.flatMap((row, i) => row.map((value, j) => ({ key: `a${i}${j}`, label: `Axis ${i + 1} · ${'XYZ'[j]}`, value }))) : [])]} action="Apply supports" onSubmit={v => {
      if (!selection.nodes.length) throw new Error('Select at least one node.')
      if (!fixed.length) throw new Error('Choose at least one restrained direction, or use Remove supports.')
      const m = structuredClone(model); m.supports = m.supports.filter(s => !selection.nodes.includes(s.node_id))
      for (const id of selection.nodes) {
        const s: Support = { node_id: id }; dofs.forEach(d => { s[d] = fixed.includes(d); s[`${d}_value`] = fixed.includes(d) ? v[d] : 0 })
        if (local) s.axes = [[v.a00, v.a01, v.a02], [v.a10, v.a11, v.a12], [v.a20, v.a21, v.a22]]; m.supports.push(s)
      }
      onChange(parseModel3D(m), 'Supports applied')
    }} />
    <Button color="error" disabled={!selection.nodes.length} onClick={() => { const m = structuredClone(model); m.supports = m.supports.filter(s => !selection.nodes.includes(s.node_id)); onChange(m, 'Supports removed') }}>Remove supports</Button>
  </>
}
function LoadEditor({ model, selection, onChange }: { model: Model3D; selection: Selection; onChange: (model: Model3D, message?: string) => void }) {
  const [kind, setKind] = useState<'nodal' | 'line'>(selection.elements.length && !selection.nodes.length ? 'line' : 'nodal')
  const line = model.distributed_loads.filter(l => l.element_id === selection.elements[0]); const [axes, setAxes] = useState<'local' | 'global'>(line[0]?.coordinate_system ?? 'local')
  const nodal = model.nodal_loads.filter(l => l.node_id === selection.nodes[0])
  const fields = kind === 'nodal' ? forces.map(key => ({ key, label: `${key.toUpperCase()} (${key[0] === 'f' ? 'kN' : 'kN·m'})`, value: nodal.reduce((s, l) => s + l[key], 0) / 1000 })) : lineKeys.map(key => ({ key, label: `${key.replace('_', ' ')} (${key[0] === 'q' ? 'kN/m' : 'kN·m/m'})`, value: line.filter(l => l.coordinate_system === axes).reduce((s, l) => s + l[key], 0) / 1000 }))
  return <>{title('Assign loads', 'Apply replaces existing loads on the selected objects. Other objects keep their loads.')}
    <TextField select label="Load type" value={kind} onChange={e => setKind(e.target.value as typeof kind)}><MenuItem value="nodal">Nodal force / moment</MenuItem><MenuItem value="line">Distributed member load</MenuItem></TextField>
    <Alert severity="info">{kind === 'nodal' ? `${selection.nodes.length} nodes selected · global axes` : `${selection.elements.length} members selected · i = start, j = end`}</Alert>
    {kind === 'line' && <><TextField select label="Line-load axes" value={axes} onChange={e => setAxes(e.target.value as typeof axes)}><MenuItem value="local">Local member axes</MenuItem><MenuItem value="global">Global axes</MenuItem></TextField><Typography variant="caption" color="text.secondary">qx, qy, qz use the chosen axes. mx is always torsion about local x.</Typography></>}
    <NumericForm key={`${kind}-${axes}`} fields={fields} action="Apply loads" onSubmit={v => {
      const m = structuredClone(model)
      if (kind === 'nodal') {
        if (!selection.nodes.length) throw new Error('Select at least one node.')
        m.nodal_loads = m.nodal_loads.filter(l => !selection.nodes.includes(l.node_id))
        if (forces.some(f => v[f] !== 0)) for (const node_id of selection.nodes) m.nodal_loads.push(Object.fromEntries([['node_id', node_id], ...forces.map(f => [f, v[f] * 1000])]) as NodalLoad)
      } else {
        if (!selection.elements.length) throw new Error('Select at least one member.')
        if (m.elements.some(e => selection.elements.includes(e.id) && e.theory === 'timoshenko') && lineKeys.some(k => v[k] !== 0)) throw new Error('Distributed loads require Euler–Bernoulli members.')
        m.distributed_loads = m.distributed_loads.filter(l => !selection.elements.includes(l.element_id))
        if (lineKeys.some(k => v[k] !== 0)) for (const element_id of selection.elements) m.distributed_loads.push(Object.fromEntries([['element_id', element_id], ['coordinate_system', axes], ...lineKeys.map(k => [k, v[k] * 1000])]) as LineLoad)
      }
      onChange(m, 'Loads applied')
    }} />
    <Button color="error" disabled={!(kind === 'nodal' ? selection.nodes.length : selection.elements.length)} onClick={() => { const m = structuredClone(model); if (kind === 'nodal') m.nodal_loads = m.nodal_loads.filter(l => !selection.nodes.includes(l.node_id)); else m.distributed_loads = m.distributed_loads.filter(l => !selection.elements.includes(l.element_id)); onChange(m, 'Loads removed') }}>Remove selected loads</Button>
  </>
}
function AnalysisSettings({ model, onChange }: { model: Model3D; onChange: (model: Model3D, message?: string) => void }) {
  const [points, setPoints] = useState(model.section_points.map(p => `${p.y}, ${p.z}`).join('\n'))
  return <Accordion disableGutters elevation={0}><AccordionSummary expandIcon={<ExpandMoreIcon />}><Typography variant="subtitle2">Analysis & stress recovery</Typography></AccordionSummary><AccordionDetails>
    <NumericForm fields={[{ key: 'stations', label: 'Result stations', value: model.number_of_points, min: 2, max: 2001, integer: true }]} action="Apply settings" onSubmit={v => {
      const section_points = points.trim() ? points.trim().split('\n').map(row => { const values = row.split(',').map(s => s.trim()); if (values.length !== 2 || values.some(s => !s || !Number.isFinite(Number(s)))) throw new Error('Enter one y, z pair per line, in metres.'); return { y: Number(values[0]), z: Number(values[1]) } }) : []
      onChange({ ...model, number_of_points: v.stations, section_points }, 'Analysis settings applied')
    }}><TextField multiline minRows={3} label="Section points y, z (m)" value={points} onChange={e => setPoints(e.target.value)} helperText="Optional. One local y, z pair per line for normal-stress recovery." /></NumericForm>
  </AccordionDetails></Accordion>
}
