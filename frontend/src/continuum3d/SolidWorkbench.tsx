import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import { Alert, Box, Button, Checkbox, Dialog, DialogActions, DialogContent, DialogTitle, Divider, FormControlLabel, InputBase, LinearProgress, Menu, MenuItem, Snackbar, Stack, Tab, Tabs, TextField, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material'
import AccountTreeRoundedIcon from '@mui/icons-material/AccountTreeRounded'
import PlayArrowRoundedIcon from '@mui/icons-material/PlayArrowRounded'
import KeyboardArrowDownRoundedIcon from '@mui/icons-material/KeyboardArrowDownRounded'
import { WorkspaceSwitcher } from '../components/WorkspaceSwitcher'
import { ScientificField } from '../components/ScientificField'
import { DataTable } from '../spatial/DataTable'
import { useSpatialDocument } from '../spatial/useSpatialDocument'
import { solveContinuum3D, validateContinuum3D } from '../api'
import { blockModel, boundaryFaces, exampleSolid, faceNodes, parseSolid, type Kind, type SolidModel, type Vec } from './model'
import { SolidCanvas, quantityLabels, type Quantity, type SolidSelection } from './SolidCanvas'
import '../spatial/spatial.css'

const STORAGE = 'nonlinear-studio.continuum3d.model.v1'
const emptyFamilies = new Set<never>()
const categories = ['Geometry', 'Materials', 'Supports', 'Loads', 'Nodes', 'Elements'] as const
type Category = typeof categories[number]
const sides = ['x-', 'x+', 'y-', 'y+', 'z-', 'z+']
const format = (v: number) => v === 0 ? '0' : v.toExponential(5)

export function SolidWorkbench({ active, onFrame, onShell, onPlate, on2D }: { active: boolean; onFrame: () => void; onShell?: () => void; onPlate?: () => void; on2D: () => void }) {
  const doc = useSpatialDocument({ storage: STORAGE, example: exampleSolid, parse: parseSolid,
    solve: solveContinuum3D, validate: validateContinuum3D, active })
  const { model, result, warning, message, error, setError, setMessage, cancel } = doc
  const running = doc.busy === 'solve'
  const importing = doc.busy === 'import'
  const busy = doc.busy !== null
  const [mode, setMode] = useState<'model' | 'results'>('model'); const [category, setCategory] = useState<Category>('Geometry')
  const [properties, setProperties] = useState(false); const [selection, setSelection] = useState<SolidSelection>(null)
  const [dirty, setDirty] = useState(false); const [formKey, setFormKey] = useState(0)
  const [menu, setMenu] = useState<HTMLElement | null>(null); const [help, setHelp] = useState(false)
  const [quantity, setQuantity] = useState<Quantity>('displacement'); const [scale, setScale] = useState(1000)
  const [tables, setTables] = useState(true); const [table, setTable] = useState('displacements')
  const [lengths, setLengths] = useState<Vec>([2,1,1]); const [divisions, setDivisions] = useState<Vec>([4,2,2]); const [kind, setKind] = useState<Kind>('hex8')
  const [materialId, setMaterialId] = useState(model.materials[0].id); const [young, setYoung] = useState(model.materials[0].E); const [poisson, setPoisson] = useState(model.materials[0].nu)
  const [target, setTarget] = useState('x-'); const [axes, setAxes] = useState([true,true,true]); const [settlement, setSettlement] = useState<Vec>([0,0,0])
  const [loadType, setLoadType] = useState('traction'); const [loadTarget, setLoadTarget] = useState('x+'); const [force, setForce] = useState<Vec>([1e6,0,0])
  const input = useRef<HTMLInputElement>(null)
  const change = (next: SolidModel, text: string) => {
    doc.change(next, text); setMode('model'); setDirty(false)
  }
  const resetFields = (next = model) => { setLengths(['x','y','z'].map(axis => { const values = next.nodes.map(n => n[axis as 'x'|'y'|'z']); return Math.max(...values)-Math.min(...values) }) as Vec); setDivisions(['x','y','z'].map(axis => Math.max(1, new Set(next.nodes.map(n=>n[axis as 'x'|'y'|'z'])).size-1)) as Vec); setKind(next.elements[0].kind); setAxes([true,true,true]); const m = next.materials.find(m => m.id === materialId) ?? next.materials[0]; setMaterialId(m.id); setYoung(m.E); setPoisson(m.nu); setSettlement([0,0,0]); setForce([1e6,0,0]); setDirty(false); setFormKey(v => v+1) }
  const restore = (next: SolidModel | undefined) => {
    if (!next) return
    setMode('model'); resetFields(next); setSelection(null)
  }
  const undo = () => restore(doc.undo())
  const redo = () => restore(doc.redo())
  const exportFile = () => doc.exportFile(`${model.name}.continuum3d.json`)
  const openFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]; event.target.value = ''
    if (!file || dirty || busy) return
    restore(await doc.importFile(file))
  }
  const run = () => {
    if (dirty || busy) return
    setMode('results'); setTables(true); void doc.run()
  }
  useEffect(() => {
    if (active) document.title = 'Continuum 3D workspace — Nonlinear Studio'
    else { setMenu(null); setHelp(false) }
  }, [active])
  useEffect(() => { if (!dirty || !active) return; const guard=(e:BeforeUnloadEvent) => { e.preventDefault(); e.returnValue='' }; window.addEventListener('beforeunload',guard); return () => window.removeEventListener('beforeunload',guard) },[dirty,active])
  const select = (s: SolidSelection) => { if (dirty) return; setSelection(s); setProperties(true); if (s) setCategory(s.kind==='node'?'Nodes':'Elements') }
  const openCategory = (c: Category) => { if (dirty && c!==category) return; setCategory(c); setProperties(true); setMode('model') }
  const numeric = (label:string,value:number,onChange:(v:number)=>void,options: { unit?:string; min?:number; max?:number; exclusiveMin?:number; exclusiveMax?:number; integer?:boolean }={}) => <ScientificField label={label} value={value} onValueChange={v=>{onChange(v);setDirty(true)}} {...options}/>
  const valid = (v:number[]) => v.every(Number.isFinite)
  const targetIds = (side:string) => side==='selected' ? selection?.kind==='node' ? [selection.id] : [] : faceNodes(model,side)
  const sideField = (label:string,value:string,set:(v:string)=>void,allowNode=true) => <TextField select fullWidth label={label} value={value} onChange={e=>{set(e.target.value);setDirty(true)}}>{sides.map(v=><MenuItem key={v} value={v}>{v[0].toUpperCase()} {v[1]==='-'?'minimum':'maximum'} face</MenuItem>)}{allowNode&&<MenuItem value="selected" disabled={selection?.kind!=='node'}>Selected node{selection?.kind==='node'?` ${selection.id}`:''}</MenuItem>}</TextField>
  const applySupports = () => {
    const ids=targetIds(target); if (!ids.length) {setError('Select a node or a boundary face first.');return}
    const constraints=model.constraints.filter(c=>!ids.includes(c.node_id))
    ids.forEach(id=>axes.forEach((enabled,j)=>{if(enabled) constraints.push({node_id:id,dof:(['ux','uy','uz'] as const)[j],value:settlement[j]})}))
    change({...model,constraints},'Supports updated on the selected target')
  }
  const applyLoad = () => {
    if (loadType==='body') {change({...model,body_force:force},'Body force updated');return}
    if (loadType==='nodal') { if(selection?.kind!=='node') {setError('Select a mesh node first.');return}; change({...model,nodal_loads:[...model.nodal_loads.filter(l=>l.node_id!==selection.id),{node_id:selection.id,force}]},'Nodal force updated');return }
    const ids=new Set(faceNodes(model,loadTarget)); const targets=boundaryFaces(model).filter(f=>f.nodes.every(n=>ids.has(n)))
    if(!targets.length) {setError('No complete exposed mesh face lies on this boundary. Use a block boundary or import explicit face loads.');return}
    const keys=new Set(targets.map(f=>`${f.element}:${f.face}`))
    change({...model,tractions:[...model.tractions.filter(t=>!keys.has(`${t.element_id}:${t.face}`)),...targets.map(f=>({element_id:f.element,face:f.face,traction:force}))]},'Boundary traction updated')
  }
  const node=model.nodes.find(n=>selection?.kind==='node'&&n.id===selection.id)
  const element=model.elements.find(e=>selection?.kind==='element'&&e.id===selection.id)
  const maxU=result?Math.max(...result.nodal_displacements.map(n=>Math.hypot(...n.value))):0
  const resultRows = !result?[]:table==='stress'?result.elements.flatMap(e=>e.points.map((p,i)=>({id:`${e.element_id}.${i+1}`,element:e.element_id,point:i+1,xx:format(p.stress[0]),yy:format(p.stress[1]),zz:format(p.stress[2]),xy:format(p.stress[3]),yz:format(p.stress[4]),zx:format(p.stress[5]),vm:format(p.von_mises)}))):(table==='reactions'?result.nodal_reactions:result.nodal_displacements).map(n=>({id:n.node_id,x:format(n.value[0]),y:format(n.value[1]),z:format(n.value[2]),magnitude:format(Math.hypot(...n.value))}))
  const tableColumns=table==='stress'?[{key:'element',label:'Element'},{key:'point',label:'Point'},...['xx','yy','zz','xy','yz','zx','vm'].map(key=>({key,label:`${key==='vm'?'von Mises':key.toUpperCase()} (Pa)`,numeric:true}))]:[{key:'id',label:'Node'},...['x','y','z','magnitude'].map(key=>({key,label:`${key==='magnitude'?'Magnitude':key.toUpperCase()} (${table==='reactions'?'N':'m'})`,numeric:true}))]

  return <Box sx={{height:'100dvh',minWidth:1120,display:'flex',flexDirection:'column',bgcolor:'background.default'}}>
    <Stack direction="row" sx={{height:56,flexShrink:0,alignItems:'center',gap:1,px:2,bgcolor:'background.paper',borderBottom:'1px solid',borderColor:'divider'}}>
      <AccountTreeRoundedIcon color="primary"/><Typography variant="h6" sx={{fontSize:16,mr:2}}>Nonlinear Studio</Typography>
      <Button color="inherit" endIcon={<KeyboardArrowDownRoundedIcon/>} onClick={e=>setMenu(e.currentTarget)} aria-haspopup="menu" aria-expanded={!!menu}>Project</Button>
      <ToggleButtonGroup size="small" exclusive value={mode} aria-label="Workbench mode" onChange={(_,v)=>{if(v)setMode(v)}}><ToggleButton value="model">Model</ToggleButton><ToggleButton value="results" disabled={dirty||(!result&&!error&&!running)}>Results</ToggleButton></ToggleButtonGroup>
      <Box sx={{flex:1}}/><Button disabled={!doc.canUndo||dirty||busy} onClick={undo}>Undo</Button><Button disabled={!doc.canRedo||dirty||busy} onClick={redo}>Redo</Button>
      <Button color="inherit" disabled={dirty||busy} onClick={exportFile}>Save project</Button><Button color="inherit" onClick={()=>setHelp(true)}>Guide</Button>
      <Button variant="contained" startIcon={<PlayArrowRoundedIcon/>} sx={{width:158}} disabled={dirty||importing} onClick={()=>running?cancel():void run()}>{running?'Cancel':'Run analysis'}</Button>
    </Stack>
    <Menu anchorEl={menu} open={!!menu} onClose={()=>setMenu(null)}>
      <MenuItem disabled={dirty||busy} onClick={()=>{setMenu(null);input.current?.click()}}>Open solid JSON</MenuItem>
      <MenuItem disabled={dirty||busy} onClick={()=>{setMenu(null);exportFile()}}>Export solid JSON</MenuItem>
      <MenuItem disabled={dirty||busy} onClick={()=>{setMenu(null);const next=exampleSolid();change(next,'Example restored. Undo recovers the previous model.');resetFields(next);setSelection(null)}}>Reset solid example</MenuItem>
    </Menu><input ref={input} hidden type="file" accept="application/json,.json" onChange={openFile}/>
    <Stack direction="row" sx={{height:38,flexShrink:0,alignItems:'center',px:1,bgcolor:'background.paper',borderBottom:'1px solid',borderColor:'divider'}}>
      <WorkspaceSwitcher activeFamily="continuum3d" draftFamilies={emptyFamilies} resultFamilies={emptyFamilies} onChange={()=>{}} onSpatial={onFrame} onContinuumSpatial={()=>{}} onShellSpatial={onShell} onPlateSpatial={onPlate} onDimensionChange={d=>{if(d==='2d')on2D()}}/>
      <Divider orientation="vertical" flexItem sx={{mx:2,my:1}}/><InputBase key={model.name} defaultValue={model.name} disabled={dirty||busy} inputProps={{'aria-label':'Solid model name',maxLength:120}} sx={{flex:1,fontSize:13}} onBlur={e=>{const name=e.target.value.trim();if(name&&name!==model.name)change({...model,name},'Model renamed');else e.target.value=model.name}}/>
      <Typography variant="caption" color="text.secondary">{dirty?'Unapplied changes':'Local workspace'} · Linear static</Typography>
    </Stack>
    <Box sx={{height:2,flexShrink:0}}>{busy&&<LinearProgress aria-label={importing?'Opening solid project':'Solving solid model'}/>}</Box>
    {warning&&<Alert severity="warning">{warning}</Alert>}{error&&<Alert severity="error" onClose={()=>setError('')}>{error}</Alert>}
    <Box sx={{display:'flex',flex:1,minHeight:0}}>
      {mode==='model'&&<Box component="nav" aria-label="Solid model navigator" sx={{width:232,flexShrink:0,overflowY:'auto',p:1.5,borderRight:'1px solid',borderColor:'divider',bgcolor:'background.paper'}}>
        <Typography variant="overline">Continuum · 3D</Typography><Typography variant="body2" sx={{mb:2}}>Linear elastic solid</Typography>
        {categories.map(c=><Button fullWidth key={c} disabled={busy||(dirty&&c!==category)} variant={properties&&category===c?'contained':'text'} color="primary" sx={{justifyContent:'space-between',mb:.5}} onClick={()=>openCategory(c)}>{c}<Typography component="span" variant="caption">{c==='Nodes'?model.nodes.length:c==='Elements'?model.elements.length:c==='Materials'?model.materials.length:c==='Supports'?model.constraints.length:c==='Loads'?model.nodal_loads.length+model.tractions.length+(model.body_force.some(v=>v!==0)?1:0):''}</Typography></Button>)}
        <Divider sx={{my:2}}/><Typography variant="caption" color="text.secondary">{[...new Set(model.elements.map(e=>e.kind.toUpperCase()))].join(' + ')} · {3*model.nodes.length} DOFs</Typography>
        <Typography variant="caption" color="text.secondary" sx={{mt:1,display:'block'}}>Geometry creates a block mesh. Open solid JSON for another topology.</Typography>
      </Box>}
      <Box sx={{display:'flex',flexDirection:'column',flex:1,minWidth:0,minHeight:0}}>
        <Stack direction="row" sx={{height:48,alignItems:'center',gap:1,px:2,borderBottom:'1px solid',borderColor:'divider',bgcolor:'background.paper'}}>
          {mode==='model'?<><Button disabled={dirty||busy} onClick={()=>openCategory('Geometry')}>Geometry & mesh</Button><Button disabled={dirty||busy} onClick={()=>openCategory('Supports')}>Support</Button><Button disabled={dirty||busy} onClick={()=>openCategory('Loads')}>Load</Button></>:<><TextField select label="Result quantity" value={quantity} onChange={e=>setQuantity(e.target.value as Quantity)} sx={{width:230}}>{Object.entries(quantityLabels).map(([key,label])=><MenuItem key={key} value={key}>{label}</MenuItem>)}</TextField><TextField select label="Deformation scale" value={scale} onChange={e=>setScale(Number(e.target.value))} sx={{width:155}}>{[0,1,10,100,1000,10000].map(v=><MenuItem key={v} value={v}>{v===0?'Undeformed':`×${v}`}</MenuItem>)}</TextField><Button onClick={()=>setTables(v=>!v)} aria-expanded={tables}>Results & tables</Button></>}
          <Box sx={{flex:1}}/>{mode==='model'&&<Button onClick={()=>setProperties(v=>!v)} aria-expanded={properties}>Properties</Button>}
        </Stack>
        <SolidCanvas model={model} result={mode==='results'?result:null} quantity={quantity} scale={mode==='results'?scale:0} selection={selection} onSelect={select}/>
        {mode==='results'&&tables&&<Box sx={{height:270,flexShrink:0,display:'flex',flexDirection:'column',borderTop:'1px solid',borderColor:'divider',bgcolor:'background.paper'}}>
          <Stack direction="row" sx={{px:2,alignItems:'center',gap:2,minHeight:36}}><Typography variant="body2" role="status">{running?'Solving…':result?result.validation.passed?'Checks passed':'Review numerical checks':'No result yet'}</Typography>{result&&<Typography variant="caption">Max displacement {format(maxU)} m · Energy {format(result.strain_energy)} J · Residual {format(result.validation.relative_residual)}</Typography>}</Stack>
          <Tabs value={table} onChange={(_,v)=>setTable(v)} aria-label="Solid result tables" sx={{minHeight:34,'& .MuiTab-root':{minHeight:34,py:0}}}><Tab value="displacements" label="Displacements"/><Tab value="reactions" label="Reactions"/><Tab value="stress" label="Integration-point stress"/><Tab value="checks" label="Checks & scope"/></Tabs>
          {table==='checks'?<Box sx={{overflow:'auto',p:2}}>{result?<><Typography variant="body2">Force balance (N): {result.validation.force_balance.map(format).join(', ')} · Moment balance (N·m): {result.validation.moment_balance.map(format).join(', ')}</Typography><Typography variant="body2">Energy error: {format(result.validation.relative_energy_error)} · Integrated recovery error: {format(result.validation.relative_recovery_energy_error)}</Typography>{result.warnings.map(w=><Typography key={w} variant="body2" color="text.secondary" sx={{mt:1}}>{w}</Typography>)}</>:<Typography variant="body2">Run analysis to inspect equilibrium and recovery evidence.</Typography>}</Box>:<Box sx={{flex:1,minHeight:0,display:'flex','&>.spatial-data-table':{width:'100%',display:'flex',flexDirection:'column'}}}><DataTable columns={tableColumns} rows={resultRows} label={table==='stress'?'Integration point stress':table==='reactions'?'Solid reactions':'Solid displacements'}/></Box>}
        </Box>}
      </Box>
      <Box component="aside" aria-label="Solid properties" sx={{display:mode==='model'&&properties?'flex':'none',width:320,flexShrink:0,flexDirection:'column',borderLeft:'1px solid',borderColor:'divider',bgcolor:'background.paper'}}>
        <Stack direction="row" sx={{height:48,px:2,alignItems:'center',borderBottom:'1px solid',borderColor:'divider'}}><Typography variant="subtitle2" sx={{flex:1}}>{category}</Typography><Button size="small" onClick={()=>setProperties(false)}>Close</Button></Stack>
        <Box key={formKey} sx={{flex:1,overflowY:'auto',p:2}}>
          <Stack spacing={1.5} sx={{display:category==='Geometry'?'flex':'none'}}>
            <Typography variant="body2">Block geometry</Typography>
            {['X length','Y length','Z length'].map((label,i)=><Box key={label}>{numeric(label,lengths[i],v=>setLengths(a=>a.map((n,j)=>j===i?v:n) as Vec),{unit:'m',exclusiveMin:0})}</Box>)}
            <TextField select label="Solid element" value={kind} onChange={e=>{setKind(e.target.value as Kind);setDirty(true)}}><MenuItem value="hex8">Hex8 · full integration</MenuItem><MenuItem value="tet4">Tet4 · tetrahedra</MenuItem></TextField>
            {['X divisions','Y divisions','Z divisions'].map((label,i)=><Box key={label}>{numeric(label,divisions[i],v=>setDivisions(a=>a.map((n,j)=>j===i?v:n) as Vec),{min:1,integer:true})}</Box>)}
            <Typography variant="caption" color="text.secondary">Generate replaces this mesh and clears its supports and loads. Material 1 is retained. Undo restores the previous model.</Typography>
            <Button variant="contained" disabled={busy||!valid([...lengths,...divisions])} onClick={()=>{try {const next=blockModel(lengths,divisions,kind);next.name=model.name;next.materials=[{...model.materials[0],id:1}];change(next,'Solid mesh generated. Add supports and loads before analysis.');resetFields(next);setSelection(null)}catch(e){setError((e as Error).message)}}}>Generate mesh</Button>
          </Stack>
          <Stack spacing={1.5} sx={{display:category==='Materials'?'flex':'none'}}>
            <TextField select label="Material" value={materialId} disabled={dirty} onChange={e=>{const m=model.materials.find(m=>m.id===Number(e.target.value))!;setMaterialId(m.id);setYoung(m.E);setPoisson(m.nu);setFormKey(v=>v+1)}}>{model.materials.map(m=><MenuItem key={m.id} value={m.id}>Material {m.id}</MenuItem>)}</TextField>
            {numeric('Young’s modulus',young,setYoung,{unit:'Pa',exclusiveMin:0})}{numeric('Poisson ratio',poisson,setPoisson,{exclusiveMin:-1,exclusiveMax:.5})}
            {poisson>.45&&<Alert severity="warning">Near incompressibility can cause volumetric locking.</Alert>}
            <Button variant="contained" disabled={busy||!valid([young,poisson])} onClick={()=>change({...model,materials:model.materials.map(m=>m.id===materialId?{...m,E:young,nu:poisson}:m)},'Material updated')}>Apply material</Button>
            <Button disabled={busy||!valid([young,poisson])} onClick={()=>{const id=Math.max(...model.materials.map(m=>m.id))+1;change({...model,materials:[...model.materials,{id,E:young,nu:poisson}]},'Material added');setMaterialId(id)}}>Add material</Button>
            <Button disabled={busy||dirty||selection?.kind!=='element'} onClick={()=>change({...model,elements:model.elements.map(e=>e.id===selection?.id?{...e,material_id:materialId}:e)},'Material assigned to selected element')}>Assign to selected element</Button>
            <Button disabled={busy||dirty} onClick={()=>change({...model,elements:model.elements.map(e=>({...e,material_id:materialId}))},'Material assigned to all elements')}>Assign to all elements</Button>
          </Stack>
          <Stack spacing={1.5} sx={{display:category==='Supports'?'flex':'none'}}>
            {sideField('Support target',target,setTarget)}<Typography variant="caption">Replace constraints on target nodes; unchecked directions are free.</Typography>
            {['UX','UY','UZ'].map((label,i)=><Box key={label}><FormControlLabel control={<Checkbox checked={axes[i]} onChange={(_,v)=>{setAxes(a=>a.map((n,j)=>j===i?v:n));setDirty(true)}}/>} label={`Prescribe ${label}`}/>{axes[i]&&numeric(`${label} displacement`,settlement[i],v=>setSettlement(a=>a.map((n,j)=>j===i?v:n) as Vec),{unit:'m'})}</Box>)}
            <Button variant="contained" disabled={busy||!valid(settlement.filter((_,i)=>axes[i]))||!targetIds(target).length} onClick={applySupports}>Apply supports</Button>
            <Button disabled={busy||dirty||!model.constraints.length} onClick={()=>change({...model,constraints:[]},'All supports removed. Undo restores them.')}>Clear all supports</Button>
          </Stack>
          <Stack spacing={1.5} sx={{display:category==='Loads'?'flex':'none'}}>
            <TextField select label="Load type" value={loadType} onChange={e=>{setLoadType(e.target.value);setForce([0,0,0]);setDirty(true)}}><MenuItem value="traction">Boundary traction</MenuItem><MenuItem value="nodal">Selected-node force</MenuItem><MenuItem value="body">Uniform body force</MenuItem></TextField>
            {loadType==='traction'&&sideField('Loaded boundary',loadTarget,setLoadTarget,false)}
            {loadType==='nodal'&&<Typography variant="body2">{selection?.kind==='node'?`Node ${selection.id}`:'Select a node in the viewport or Nodes table first.'}</Typography>}
            {['X component','Y component','Z component'].map((label,i)=><Box key={label}>{numeric(label,force[i],v=>setForce(a=>a.map((n,j)=>j===i?v:n) as Vec),{unit:loadType==='traction'?'Pa':loadType==='body'?'N/m³':'N'})}</Box>)}
            <Typography variant="caption" color="text.secondary">Global XYZ components. Apply replaces this target’s existing load. Traction is a vector, not automatic normal pressure.</Typography>
            <Button variant="contained" disabled={busy||!valid(force)||(loadType==='nodal'&&selection?.kind!=='node')} onClick={applyLoad}>Apply load</Button>
            <Button disabled={busy||dirty} onClick={()=>change({...model,nodal_loads:[],tractions:[],body_force:[0,0,0]},'All loads removed. Undo restores them.')}>Clear all loads</Button>
          </Stack>
          <Stack spacing={1.5} sx={{display:category==='Nodes'?'flex':'none'}}>
            <Typography variant="caption">Generated topology is read-only. Change Geometry or open a mesh JSON.</Typography>
            {node&&<><Typography variant="body2">Node {node.id} · {node.x}, {node.y}, {node.z} m</Typography><Typography variant="caption">Supports: {model.constraints.filter(c=>c.node_id===node.id).map(c=>`${c.dof} = ${c.value} m`).join(', ')||'Free'}</Typography><Typography variant="caption">Nodal force: {model.nodal_loads.filter(l=>l.node_id===node.id).map(l=>l.force.join(', ')).join('; ')||'None'} N</Typography><Button onClick={()=>{setTarget('selected');const prescribed=['ux','uy','uz'].map(dof=>model.constraints.find(c=>c.node_id===node.id&&c.dof===dof));setAxes(prescribed.map(Boolean));setSettlement(prescribed.map(c=>c?.value??0) as Vec);setCategory('Supports');setFormKey(v=>v+1)}}>Edit node support</Button><Button onClick={()=>{setLoadType('nodal');setForce(model.nodal_loads.find(l=>l.node_id===node.id)?.force??[0,0,0]);setCategory('Loads');setFormKey(v=>v+1)}}>Edit node load</Button></>}
            <Box sx={{height:380,display:'flex','&>.spatial-data-table':{minWidth:0,display:'flex',flexDirection:'column'}}}><DataTable label="Solid nodes" columns={[{key:'id',label:'Node'},{key:'x',label:'X (m)'},{key:'y',label:'Y (m)'},{key:'z',label:'Z (m)'}]} rows={model.nodes} selected={selection?.kind==='node'?[selection.id]:[]} onSelect={id=>select({kind:'node',id})}/></Box>
          </Stack>
          <Stack spacing={1.5} sx={{display:category==='Elements'?'flex':'none'}}>
            {element&&<><Typography variant="body2">Element {element.id} · {element.kind.toUpperCase()}</Typography><Typography variant="caption">Ordered nodes: {element.nodes.join(', ')} · Material {element.material_id}</Typography><Button onClick={()=>{const m=model.materials.find(m=>m.id===element.material_id)!;setMaterialId(m.id);setYoung(m.E);setPoisson(m.nu);setCategory('Materials');setFormKey(v=>v+1)}}>Edit material assignment</Button></>}
            <Box sx={{height:420,display:'flex','&>.spatial-data-table':{minWidth:0,display:'flex',flexDirection:'column'}}}><DataTable label="Solid elements" columns={[{key:'id',label:'Element'},{key:'kind',label:'Type'},{key:'material_id',label:'Material'}]} rows={model.elements.map(e=>({id:e.id,kind:e.kind,material_id:e.material_id}))} selected={selection?.kind==='element'?[selection.id]:[]} onSelect={id=>select({kind:'element',id})}/></Box>
          </Stack>
        </Box>
      </Box>
    </Box>
    <Stack direction="row" sx={{height:34,alignItems:'center',gap:2,px:2,borderTop:'1px solid',borderColor:'divider',bgcolor:'background.paper'}}><Typography variant="caption" color="text.secondary">{dirty?'Unapplied properties · Apply in Properties or cancel':'Small-strain isotropic elasticity · 3 translations per node'}</Typography>{dirty&&<Button size="small" onClick={()=>resetFields()}>Cancel changes</Button>}</Stack>
    <Dialog open={help} onClose={()=>setHelp(false)} maxWidth="sm" fullWidth><DialogTitle>Continuum 3D</DialogTitle><DialogContent><Stack spacing={2}><Typography>Create a block mesh or open a continuum3d-1 JSON mesh. Select nodes and elements in the view or tables, assign materials, prescribe supports, and apply global nodal, face or body forces. All inputs use m, N and Pa.</Typography><Typography>Hex8 uses eight integration points. Tet4 has constant strain. Run analysis returns displacements, reactions and raw integration-point stresses, with equilibrium and energy checks. Contour colors show element means; inspect the raw point table for peak values.</Typography><Typography>Linear small-strain only. No plasticity, contact, dynamics or nonlinear geometry. Refine meshes for bending and stress gradients; near-incompressible materials can lock. Numerical checks do not establish mesh convergence.</Typography><Typography>Drag to orbit; Shift-drag to pan. Arrow keys orbit and +/− zoom. Fit and XY/XZ/YZ provide keyboard-accessible view controls. Switching dimension preserves each document and unfinished properties.</Typography></Stack></DialogContent><DialogActions><Button onClick={()=>setHelp(false)}>Close</Button></DialogActions></Dialog>
    <Snackbar open={!!message&&active} autoHideDuration={5000} onClose={()=>setMessage('')} message={message}/>
  </Box>
}
