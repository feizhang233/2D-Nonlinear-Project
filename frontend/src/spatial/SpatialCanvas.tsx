import { useEffect, useId, useRef, useState } from 'react'
import { IconButton, Tooltip } from '@mui/material'
import FitScreenIcon from '@mui/icons-material/FitScreen'
import AddIcon from '@mui/icons-material/Add'
import RemoveIcon from '@mui/icons-material/Remove'
import RotateLeftIcon from '@mui/icons-material/RotateLeft'
import RotateRightIcon from '@mui/icons-material/RotateRight'
import NorthIcon from '@mui/icons-material/North'
import SouthIcon from '@mui/icons-material/South'
import { add, dofs, mul, planeCoords, planeLabels, planePoint, sub, xyz, type Model3D, type Plane, type Result3D, type Selection, type Tool, type Vec3 } from './model'
import { basis, project, unproject } from './projection'

export type Display = 'model' | 'deformed' | 'axial_force' | 'shear_force_y' | 'shear_force_z' | 'torsional_moment' | 'bending_moment_y' | 'bending_moment_z'
export const displayNames: Record<Display, string> = { model: 'Undeformed model', deformed: 'Deformed shape', axial_force: 'Axial force N', shear_force_y: 'Shear Vy', shear_force_z: 'Shear Vz', torsional_moment: 'Torsion T', bending_moment_y: 'Moment My', bending_moment_z: 'Moment Mz' }
function bounds(model: Model3D): { center: Vec3; span: number } {
  if (!model.nodes.length) return { center: [3, 2, 1.5], span: 9 }
  const points = model.nodes.map(xyz)
  const lo = [0, 1, 2].map(i => Math.min(...points.map(p => p[i])))
  const hi = [0, 1, 2].map(i => Math.max(...points.map(p => p[i])))
  return { center: lo.map((v, i) => (v + hi[i]) / 2) as Vec3, span: Math.max(3, Math.hypot(...lo.map((v, i) => hi[i] - v))) * 1.4 }
}
export function SpatialCanvas({ model, selection, tool, plane, offset, grid, snap, spatial, chain, fitKey, result, display, deformationScale, labels, onSelect, onPoint, onEnd, onMessage }: {
  model: Model3D; selection: Selection; tool: Tool; plane: Plane; offset: number; grid: number; snap: boolean; spatial: boolean; chain: number | null; fitKey: number
  result: Result3D | null; display: Display; deformationScale: number; labels: boolean
  onSelect: (kind: 'nodes' | 'elements', id: number | null, extend: boolean) => void
  onPoint: (point: Vec3) => void; onEnd: () => void; onMessage: (message: string) => void
}) {
  const ref = useRef<HTMLDivElement>(null); const svgRef = useRef<SVGSVGElement>(null)
  const [size, setSize] = useState({ width: 600, height: 600 })
  const [camera, setCamera] = useState({ azimuth: -.63, elevation: .55 })
  const [frame, setFrame] = useState(() => bounds(model)); const [zoom, setZoom] = useState(1); const [pan, setPan] = useState([0, 0])
  const [cursor, setCursor] = useState<Vec3 | null>(null)
  const drag = useRef<{ x: number; y: number; lastX: number; lastY: number; moved: boolean; button: number; target: Element | null } | null>(null)
  const marker = useId().replace(/:/g, '')
  const axes = basis(camera, spatial ? undefined : plane); const center = project(frame.center, axes)
  const scale = Math.min(size.width, size.height) / frame.span * zoom
  const screen = (p: Vec3): [number, number] => { const q = project(p, axes); return [size.width / 2 + (q[0] - center[0]) * scale + pan[0], size.height / 2 - (q[1] - center[1]) * scale + pan[1]] }
  const fit = () => { setFrame(bounds(model)); setZoom(1); setPan([0, 0]) }
  useEffect(() => { fit() }, [fitKey]) // Explicit Fit action; drawing never moves the viewport.
  useEffect(() => {
    if (!ref.current) return
    const observer = new ResizeObserver(entries => { const { width, height } = entries[0].contentRect; if (width > 0 && height > 0) setSize({ width, height }) })
    observer.observe(ref.current); return () => observer.disconnect()
  }, [])
  const drawing = tool === 'node' || tool === 'member'
  const onPlane = (p: Vec3) => Math.abs(planeCoords(plane, p)[2] - offset) < 1e-7
  const pointFromEvent = (clientX: number, clientY: number): Vec3 | null => {
    const box = svgRef.current!.getBoundingClientRect(); const sx = clientX - box.left; const sy = clientY - box.top
    const p = unproject((sx - size.width / 2 - pan[0]) / scale + center[0], -(sy - size.height / 2 - pan[1]) / scale + center[1], axes, plane, offset)
    if (!p) return null
    if (snap) {
      const nearby = model.nodes.find(n => onPlane(xyz(n)) && Math.hypot(screen(xyz(n))[0] - sx, screen(xyz(n))[1] - sy) < 12)
      if (nearby) return xyz(nearby)
      const [a, b] = planeCoords(plane, p); return planePoint(plane, Math.round(a / grid) * grid, Math.round(b / grid) * grid, offset)
    }
    return p
  }
  const base = planeCoords(plane, frame.center); const extent = frame.span / Math.max(.2, zoom)
  const gridSpacing = grid * Math.max(1, Math.ceil(extent / grid / 30))
  const ranges = [base[0], base[1]].map(c => [Math.floor((c - extent) / gridSpacing) * gridSpacing, Math.ceil((c + extent) / gridSpacing) * gridSpacing])
  const path = (points: Vec3[]) => points.map((p, i) => `${i ? 'L' : 'M'}${screen(p).join(',')}`).join(' ')
  const diagramRaw = result && display !== 'model' && display !== 'deformed' ? Math.max(0, ...result.elements.flatMap(e => e.fields[display].map(Math.abs))) : 0
  const family = display.includes('moment') ? ['torsional_moment', 'bending_moment_y', 'bending_moment_z'] as const : ['axial_force', 'shear_force_y', 'shear_force_z'] as const
  const familyMax = result ? Math.max(1, ...result.elements.flatMap(e => family.flatMap(key => e.fields[key].map(Math.abs)))) : 1
  const diagramMax = diagramRaw < familyMax * 1e-10 ? 0 : diagramRaw
  const diagramFactor = diagramMax > 0 ? frame.span * .13 / diagramMax : 0
  const selectedCount = selection.nodes.length + selection.elements.length
  const button = (title: string, icon: React.ReactNode, action: () => void) => <Tooltip title={title} key={title}><IconButton size="small" aria-label={title} onClick={action}>{icon}</IconButton></Tooltip>
  return <section className="spatial-view" aria-label={spatial ? '3D model view' : 'Working plane view'}>
    <header className="spatial-view-heading"><div><span className="view-indicator" />{spatial ? '3D MODEL VIEW' : `${plane} WORKING PLANE`}<span className="spatial-muted">{spatial ? 'Orthographic' : `${planeLabels(plane)[2]} = ${offset} m`}</span></div>
      <span className="spatial-muted">{spatial ? 'Drag to orbit' : `${planeLabels(plane)[0]} →  ${planeLabels(plane)[1]} ↑`}</span></header>
    <div className={`spatial-viewport ${drawing ? 'is-drawing' : ''}`} ref={ref}>
      <svg ref={svgRef} width="100%" height="100%" viewBox={`0 0 ${size.width} ${size.height}`} role="img" tabIndex={0} aria-label={spatial ? 'Interactive 3D frame. Arrow keys pan; plus and minus zoom; F fits. Use coordinates and model tables for keyboard editing.' : `${plane} drawing canvas at ${planeLabels(plane)[2]} ${offset} metres. Arrow keys pan; plus and minus zoom; F fits. Use coordinates for keyboard drawing.`}
        onKeyDown={e => {
          if (e.nativeEvent.isComposing) return
          const moves: Record<string, number[]> = { ArrowLeft: [-30, 0], ArrowRight: [30, 0], ArrowUp: [0, -30], ArrowDown: [0, 30] }
          if (moves[e.key]) { e.preventDefault(); const d = moves[e.key]; setPan(p => [p[0] + d[0], p[1] + d[1]]) }
          if (e.key === '+' || e.key === '=') setZoom(z => Math.min(12, z * 1.2))
          if (e.key === '-') setZoom(z => Math.max(.15, z / 1.2))
          if (e.key.toLowerCase() === 'f') fit()
        }}
        onContextMenu={e => { e.preventDefault(); onEnd() }}
        onPointerDown={e => { if (e.button === 2) return; e.currentTarget.setPointerCapture(e.pointerId); drag.current = { x: e.clientX, y: e.clientY, lastX: e.clientX, lastY: e.clientY, moved: false, button: e.button, target: e.target as Element } }}
        onPointerMove={e => {
          const d = drag.current
          if (d && Math.hypot(e.clientX - d.x, e.clientY - d.y) > 4) d.moved = true
          if (d?.moved) {
            const dx = e.clientX - d.lastX; const dy = e.clientY - d.lastY
            if (spatial && d.button === 0 && !e.shiftKey && !drawing) setCamera(c => ({ azimuth: c.azimuth + dx * .008, elevation: Math.max(-1.45, Math.min(1.45, c.elevation + dy * .008)) }))
            else setPan(p => [p[0] + dx, p[1] + dy])
            d.lastX = e.clientX; d.lastY = e.clientY
          } else setCursor(pointFromEvent(e.clientX, e.clientY))
        }}
        onPointerUp={e => {
          const d = drag.current; drag.current = null
          if (!d || d.moved || d.button !== 0) return
          if (drawing) { const p = pointFromEvent(e.clientX, e.clientY); if (p) onPoint(p); else onMessage('This plane is edge-on. Orbit the model or draw in the working-plane view.'); return }
          const target = d.target?.closest('[data-node],[data-member]')
          if (target?.hasAttribute('data-node')) onSelect('nodes', Number(target.getAttribute('data-node')), e.shiftKey)
          else if (target?.hasAttribute('data-member')) onSelect('elements', Number(target.getAttribute('data-member')), e.shiftKey)
          else onSelect('nodes', null, false)
        }} onPointerCancel={() => { drag.current = null }} onPointerLeave={() => setCursor(null)} onWheel={e => setZoom(z => Math.max(.15, Math.min(12, z * Math.exp(-e.deltaY * .001))))}>
        <defs><marker id={`${marker}-load`} markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0L7 3.5L0 7Z" className="load-fill" /></marker></defs>
        <g className="spatial-grid" pointerEvents="none">
          {Array.from({ length: Math.min(80, Math.ceil((ranges[0][1] - ranges[0][0]) / gridSpacing) + 1) }, (_, i) => { const a = ranges[0][0] + i * gridSpacing; return <path key={`a${i}`} d={path([planePoint(plane, a, ranges[1][0], offset), planePoint(plane, a, ranges[1][1], offset)])} className={Math.abs(a) < 1e-9 ? 'grid-origin' : ''} /> })}
          {Array.from({ length: Math.min(80, Math.ceil((ranges[1][1] - ranges[1][0]) / gridSpacing) + 1) }, (_, i) => { const b = ranges[1][0] + i * gridSpacing; return <path key={`b${i}`} d={path([planePoint(plane, ranges[0][0], b, offset), planePoint(plane, ranges[0][1], b, offset)])} className={Math.abs(b) < 1e-9 ? 'grid-origin' : ''} /> })}
          {spatial && <path className="plane-tint" d={`${path([[base[0] - extent / 3, base[1] - extent / 3], [base[0] + extent / 3, base[1] - extent / 3], [base[0] + extent / 3, base[1] + extent / 3], [base[0] - extent / 3, base[1] + extent / 3]].map(([a, b]) => planePoint(plane, a, b, offset)))} Z`} />}
        </g>
        {[...model.elements].sort((a, b) => project(xyz(model.nodes[a.node_i - 1]), axes)[2] - project(xyz(model.nodes[b.node_i - 1]), axes)[2]).map(e => {
          const a = xyz(model.nodes[e.node_i - 1]); const b = xyz(model.nodes[e.node_j - 1]); const selected = selection.elements.includes(e.id)
          const inPlane = onPlane(a) && onPlane(b); const mid = screen(mul(add(a, b), .5))
          return <g key={e.id} data-member={e.id} className={`spatial-member ${selected ? 'selected' : ''} ${!spatial && !inPlane ? 'off-plane' : ''}`}>
            <path d={path([a, b])} className="member-hit" /><path d={path([a, b])} className="member-line" />
            {labels && (spatial || inPlane) && <text x={mid[0] + 7} y={mid[1] - 8} className="member-label">E{e.id}</text>}
            {e.releases.length > 0 && [0, 1].map(end => e.releases.some(r => end ? r > 6 : r < 6) && <circle key={end} cx={screen(add(a, mul(sub(b, a), end ? .96 : .04)))[0]} cy={screen(add(a, mul(sub(b, a), end ? .96 : .04)))[1]} r="4" className="release-dot" />)}
          </g>
        })}
        {result && display !== 'model' && result.elements.map(e => {
          const f = e.fields; let points = f.x_global.map((x, i): Vec3 => [x, f.y_global[i], f.z_global[i]])
          if (!spatial && !points.every(onPlane)) return null
          if (display === 'deformed') points = points.map((p, i) => add(p, mul(sub([f.x_deformed[i], f.y_deformed[i], f.z_deformed[i]], p), deformationScale)))
          else { const direction = e.local_axes[display === 'shear_force_z' || display === 'bending_moment_y' ? 2 : 1] as Vec3; points = points.map((p, i) => add(p, mul(direction, f[display][i] * diagramFactor))) }
          return <g key={e.element_id} className="spatial-result" pointerEvents="none"><path d={path(points)} />{display !== 'deformed' && <path className="diagram-end" d={`${path([[f.x_global[0], f.y_global[0], f.z_global[0]], points[0]])} ${path([[f.x_global.at(-1)!, f.y_global.at(-1)!, f.z_global.at(-1)!], points.at(-1)!])}`} />}</g>
        })}
        {model.supports.map(s => { const n = model.nodes[s.node_id - 1]; const p = xyz(n); if (!spatial && !onPlane(p)) return null; const [x, y] = screen(p); return <g key={s.node_id} className="spatial-support" transform={`translate(${x} ${y})`} pointerEvents="none"><title>Node {s.node_id}: {dofs.filter(d => s[d]).join(', ')} restrained</title><path d={dofs.every(d => s[d]) ? 'M-9 7H9V12H-9Z M-8 14L-11 17 M0 14L-3 17 M8 14L5 17' : 'M0 4L-8 16H8Z M-9 19H9'} /></g> })}
        {model.nodes.map(n => { const p = xyz(n); if (!spatial && !onPlane(p)) return null; const [x, y] = screen(p); return <g key={n.id} data-node={n.id} className={`spatial-node ${selection.nodes.includes(n.id) ? 'selected' : ''}`}>
          <circle cx={x} cy={y} r="11" className="node-hit" /><circle cx={x} cy={y} r={chain === n.id ? 6 : 3.5} className="node-dot" />{labels && <text x={x + 9} y={y + 15}>{n.id}</text>}
        </g> })}
        {model.nodal_loads.map((l, i) => { const n = model.nodes[l.node_id - 1]; const p = xyz(n); if (!spatial && !onPlane(p)) return null; const [x, y] = screen(p); const f = project([l.fx, l.fy, l.fz], axes); const len = Math.hypot(f[0], f[1]); const moment = Math.hypot(l.mx, l.my, l.mz)
          return <g key={i} className="spatial-load" pointerEvents="none">{len > 1e-8 && <path d={`M${x - f[0] / len * 40},${y + f[1] / len * 40}L${x - f[0] / len * 7},${y + f[1] / len * 7}`} markerEnd={`url(#${marker}-load)`} />}{moment > 0 && <path d={`M${x + 14},${y - 2}a14,14 0 1,0 -15,16`} markerEnd={`url(#${marker}-load)`} />}</g>
        })}
        {model.distributed_loads.map((l, i) => { const e = model.elements.find(e => e.id === l.element_id)!; const a = xyz(model.nodes[e.node_i - 1]); const b = xyz(model.nodes[e.node_j - 1]); if (!spatial && !(onPlane(a) && onPlane(b))) return null; const [x, y] = screen(mul(add(a, b), .5)); return <g key={i} className="spatial-load" pointerEvents="none"><text x={x + 8} y={y + 15}>q · {l.coordinate_system}</text></g> })}
        {drawing && cursor && <g pointerEvents="none" className="spatial-preview">{chain && model.nodes[chain - 1] && <path d={path([xyz(model.nodes[chain - 1]), cursor])} />}<circle cx={screen(cursor)[0]} cy={screen(cursor)[1]} r="6" /><path d={`M${screen(cursor)[0] - 10},${screen(cursor)[1]}h20M${screen(cursor)[0]},${screen(cursor)[1] - 10}v20`} /></g>}
        <g className="axis-triad" transform={`translate(42 ${size.height - 48})`} pointerEvents="none">
          {([[1, 0, 0], [0, 1, 0], [0, 0, 1]] as Vec3[]).map((a, i) => { const p = project(a, axes); return <g key={i} className={`axis-${i}`}><line x1="0" y1="0" x2={p[0] * 28} y2={-p[1] * 28} /><text x={p[0] * 37 - 4} y={-p[1] * 37 + 4}>{'XYZ'[i]}</text></g> })}
        </g>
      </svg>
      <div className="canvas-view-controls">
        {button(spatial ? 'Fit 3D view' : 'Fit plane view', <FitScreenIcon fontSize="small" />, fit)}
        {button(spatial ? 'Zoom in 3D' : 'Zoom in plane', <AddIcon fontSize="small" />, () => setZoom(z => Math.min(12, z * 1.2)))}
        {button(spatial ? 'Zoom out 3D' : 'Zoom out plane', <RemoveIcon fontSize="small" />, () => setZoom(z => Math.max(.15, z / 1.2)))}
        {spatial && <>{button('Rotate view left', <RotateLeftIcon fontSize="small" />, () => setCamera(c => ({ ...c, azimuth: c.azimuth - .25 })))}{button('Rotate view right', <RotateRightIcon fontSize="small" />, () => setCamera(c => ({ ...c, azimuth: c.azimuth + .25 })))}{button('Tilt view up', <NorthIcon fontSize="small" />, () => setCamera(c => ({ ...c, elevation: Math.min(1.45, c.elevation + .2) })))}{button('Tilt view down', <SouthIcon fontSize="small" />, () => setCamera(c => ({ ...c, elevation: Math.max(-1.45, c.elevation - .2) })))}</>}
      </div>
      {!model.nodes.length && <div className="spatial-empty"><strong>Your next structure starts here.</strong><span>Choose Draw member, or enter exact coordinates in the panel.</span></div>}
      {display !== 'model' && result && <div className="canvas-result-legend">{displayNames[display]} · {display === 'deformed' ? `× ${deformationScale}` : `peak |value| ${(diagramMax / 1000).toPrecision(4)} ${display.includes('moment') ? 'kN·m' : 'kN'}`}</div>}
      <div className="canvas-coordinate-readout">{cursor ? cursor.map((v, i) => `${'XYZ'[i]} ${v.toFixed(3)}`).join('   ') : `${selectedCount} selected`} <span>m</span></div>
    </div>
  </section>
}
