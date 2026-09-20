import { Box, Button, ButtonGroup, Typography, useTheme } from '@mui/material'
import { useId, useRef, useState } from 'react'
import { basis, project } from './projection'
export type Vec = [number, number, number]
export type SurfaceSelection = { kind: 'node' | 'element'; id: number } | null
export type SurfaceFace = { element: number; face: number; nodes: number[] }
export function SurfaceCanvas({
  model,
  boundaries,
  displacementRows,
  values,
  loads,
  hasResult,
  showContour,
  quantityLabel,
  meshLabel,
  unit,
  contourCaption,
  scale,
  selection,
  onSelect,
  displacementContour = false,
  localFrame,
  moments = [],
  selectable = true,
}: {
  model: {
    nodes: { id: number; x: number; y: number; z: number }[]
    elements: { id: number }[]
    constraints: { node_id: number }[]
  }
  boundaries: SurfaceFace[]
  displacementRows: { node_id: number; value: Vec }[]
  values: Map<number, number>
  loads: { position: Vec; force: Vec }[]
  hasResult: boolean
  showContour: boolean
  quantityLabel: string
  meshLabel: string
  unit: string
  contourCaption: string
  localFrame?: { ex: Vec; ey: Vec }
  moments?: { position: Vec; value: Vec }[]
  selectable?: boolean
  displacementContour?: boolean
  scale: number
  selection: SurfaceSelection
  onSelect: (s: SurfaceSelection) => void
}) {
  const theme = useTheme()
  const arrowId = useId()
  const [camera, setCamera] = useState({ azimuth: -0.65, elevation: 0.55 })
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState([0, 0])
  const drag = useRef<{
    x: number
    y: number
    camera: typeof camera
    pan: number[]
    move: boolean
    moved: boolean
  } | null>(null)
  const suppressClick = useRef(false)
  const axes = basis(camera)
  const displacements = new Map(
    displacementRows.map((n) => [n.node_id, n.value]),
  )
  const positions = new Map(
    model.nodes.map((n) => {
      const u = displacements.get(n.id) ?? [0, 0, 0]
      return [
        n.id,
        [n.x + scale * u[0], n.y + scale * u[1], n.z + scale * u[2]] as Vec,
      ]
    }),
  )
  const xyz = [...positions.values()]
  const center = [0, 1, 2].map(
    (i) =>
      (Math.min(...xyz.map((p) => p[i])) + Math.max(...xyz.map((p) => p[i]))) /
      2,
  ) as Vec
  const projected = (p: Vec) =>
    project(p.map((v, i) => v - center[i]) as Vec, axes)
  const raw = xyz.map(projected)
  const width =
    Math.max(...raw.map((p) => p[0])) - Math.min(...raw.map((p) => p[0]))
  const height =
    Math.max(...raw.map((p) => p[1])) - Math.min(...raw.map((p) => p[1]))
  const factor =
    Math.min(670 / Math.max(width, 1e-12), 340 / Math.max(height, 1e-12)) * zoom
  const screen = (p: Vec) => {
    const a = projected(p)
    return [450 + a[0] * factor + pan[0], 255 - a[1] * factor + pan[1], a[2]]
  }
  const points = new Map([...positions].map(([id, p]) => [id, screen(p)]))
  const faceValue = (f: SurfaceFace) =>
    displacementContour
      ? f.nodes.reduce(
          (sum, id) =>
            sum + Math.hypot(...(displacements.get(id) ?? [0, 0, 0])),
          0,
        ) / f.nodes.length
      : (values.get(f.element) ?? 0)
  const field = boundaries.map(faceValue)
  const low = Math.min(...field)
  const high = Math.max(...field)
  const color = (value: number) => {
    const t =
      high - low > Math.max(Math.abs(high), 1e-30) * 1e-8
        ? (value - low) / (high - low)
        : 0.5
    const from = theme.palette.secondary.main
    const to = theme.palette.error.main
    return `color-mix(in srgb, ${to} ${Math.round(t * 100)}%, ${from})`
  }
  const sorted = boundaries
    .map((f) => ({
      ...f,
      depth:
        f.nodes.reduce((s, n) => s + points.get(n)![2], 0) / f.nodes.length,
    }))
    .sort((a, b) => a.depth - b.depth)
  const reference = (ids: number[]) =>
    ids
      .map((id) => {
        const n = model.nodes.find((v) => v.id === id)!
        return screen([n.x, n.y, n.z]).slice(0, 2).join(',')
      })
      .join(' ')
  const pick = (s: SurfaceSelection) => {
    if (selectable && !suppressClick.current) onSelect(s)
  }
  const supported = new Set(model.constraints.map((c) => c.node_id))
  const arrow = (at: Vec, force: Vec, key: string) => {
    const magnitude = Math.hypot(...force)
    if (!magnitude) return null
    const p = screen(at)
    const vector = project(force.map((v) => v / magnitude) as Vec, axes)
    const end = [p[0] + vector[0] * 42, p[1] - vector[1] * 42]
    return (
      <g
        key={key}
        stroke={theme.palette.error.main}
        fill={theme.palette.error.main}
      >
        <line
          x1={p[0]}
          y1={p[1]}
          x2={end[0]}
          y2={end[1]}
          strokeWidth={1.7}
          markerEnd={`url(#${arrowId})`}
        />
        <title>{force.map((v) => v.toPrecision(4)).join(', ')}</title>
      </g>
    )
  }
  return (
    <Box
      sx={{
        position: 'relative',
        flex: 1,
        minHeight: 220,
        bgcolor: 'background.canvas',
        overflow: 'hidden',
      }}
    >
      <svg
        viewBox="0 0 900 520"
        width="100%"
        height="100%"
        role="img"
        aria-label="3D mesh viewport. Drag to orbit; Shift-drag to pan. Arrow keys orbit, Shift-arrow keys pan, plus and minus zoom."
        tabIndex={0}
        style={{ display: 'block', touchAction: 'none' }}
        onKeyDown={(e) => {
          if (
            [
              'ArrowLeft',
              'ArrowRight',
              'ArrowUp',
              'ArrowDown',
              '+',
              '-',
              'f',
              'F',
              'Escape',
            ].includes(e.key)
          )
            e.preventDefault()
          if (e.shiftKey && e.key.startsWith('Arrow')) {
            setPan((p) => [
              p[0] +
                (e.key === 'ArrowLeft' ? -20 : e.key === 'ArrowRight' ? 20 : 0),
              p[1] +
                (e.key === 'ArrowUp' ? -20 : e.key === 'ArrowDown' ? 20 : 0),
            ])
            return
          }
          if (e.key === 'Escape' && drag.current) {
            setCamera(drag.current.camera)
            setPan(drag.current.pan)
            drag.current = null
          }
          if (e.key === 'ArrowLeft' || e.key === 'ArrowRight')
            setCamera((c) => ({
              ...c,
              azimuth: c.azimuth + (e.key === 'ArrowLeft' ? -0.15 : 0.15),
            }))
          if (e.key === 'ArrowUp' || e.key === 'ArrowDown')
            setCamera((c) => ({
              ...c,
              elevation: c.elevation + (e.key === 'ArrowUp' ? 0.15 : -0.15),
            }))
          if (e.key === '+') setZoom((v) => Math.min(v * 1.2, 8))
          if (e.key === '-') setZoom((v) => Math.max(v / 1.2, 0.2))
          if (e.key.toLowerCase() === 'f') {
            setZoom(1)
            setPan([0, 0])
          }
        }}
        onWheel={(e) => {
          if (!e.ctrlKey)
            setZoom((v) =>
              Math.max(0.2, Math.min(8, v * Math.exp(-e.deltaY * 0.001))),
            )
        }}
        onPointerDown={(e) => {
          if (e.button !== 0 && e.button !== 1) return
          suppressClick.current = false
          drag.current = {
            x: e.clientX,
            y: e.clientY,
            camera,
            pan,
            move: e.shiftKey || e.button === 1,
            moved: false,
          }
        }}
        onPointerMove={(e) => {
          const d = drag.current
          if (!d) return
          const dx = e.clientX - d.x
          const dy = e.clientY - d.y
          if (Math.hypot(dx, dy) < 4 && !d.moved) return
          if (!d.moved) e.currentTarget.setPointerCapture(e.pointerId)
          d.moved = true
          suppressClick.current = true
          if (d.move) {
            const ratio = 900 / e.currentTarget.getBoundingClientRect().width
            setPan([d.pan[0] + dx * ratio, d.pan[1] + dy * ratio])
          } else
            setCamera({
              azimuth: d.camera.azimuth - dx * 0.008,
              elevation: Math.max(
                -1.5,
                Math.min(1.5, d.camera.elevation + dy * 0.008),
              ),
            })
        }}
        onPointerUp={() => {
          drag.current = null
        }}
        onPointerCancel={() => {
          const d = drag.current
          if (d) {
            setCamera(d.camera)
            setPan(d.pan)
          }
          drag.current = null
        }}
      >
        <defs>
          <marker
            id={arrowId}
            markerWidth="6"
            markerHeight="6"
            refX="5"
            refY="3"
            orient="auto"
          >
            <path d="M0,0 L6,3 L0,6" fill={theme.palette.error.main} />
          </marker>
        </defs>
        {hasResult &&
          boundaries.map((f, i) => (
            <polygon
              key={`r${i}`}
              points={reference(f.nodes)}
              fill="none"
              stroke={theme.palette.text.secondary}
              strokeDasharray="4 4"
              opacity={0.3}
            />
          ))}
        {sorted.map((f, i) => (
          <polygon
            key={`${f.element}-${f.face}`}
            points={f.nodes
              .map((n) => points.get(n)!.slice(0, 2).join(','))
              .join(' ')}
            fill={
              hasResult && showContour
                ? color(faceValue(f))
                : i % 2
                  ? theme.palette.background.container
                  : theme.palette.background.containerHigh
            }
            stroke={
              selection?.kind === 'element' && selection.id === f.element
                ? theme.palette.primary.main
                : theme.palette.secondary.dark
            }
            strokeWidth={
              selection?.kind === 'element' && selection.id === f.element
                ? 2.5
                : 0.8
            }
            style={{ cursor: selectable ? 'pointer' : 'default' }}
            onClick={() => pick({ kind: 'element', id: f.element })}
          >
            <title>
              Element {f.element} · Face {f.face}
            </title>
          </polygon>
        ))}
        {model.nodes
          .filter((n) => supported.has(n.id))
          .map((n) => {
            const p = points.get(n.id)!
            return (
              <path
                key={`s${n.id}`}
                d={`M${p[0]},${p[1]} l-5,9 h10 z`}
                fill={theme.palette.background.paper}
                stroke={theme.palette.primary.main}
              >
                <title>Support at node {n.id}</title>
              </path>
            )
          })}
        {model.nodes.map((n) => {
          const p = points.get(n.id)!
          const selected = selection?.kind === 'node' && selection.id === n.id
          return (
            <g
              key={n.id}
              style={{ cursor: selectable ? 'pointer' : 'default' }}
              onClick={() => pick({ kind: 'node', id: n.id })}
            >
              <circle
                cx={p[0]}
                cy={p[1]}
                r={selected ? 5 : 2.2}
                fill={
                  selected
                    ? theme.palette.error.main
                    : theme.palette.primary.main
                }
              />
              <circle cx={p[0]} cy={p[1]} r={7} fill="transparent" />
              <title>
                Node {n.id}: {n.x}, {n.y}, {n.z} m
              </title>
              {selected && (
                <text
                  x={p[0] + 9}
                  y={p[1] - 8}
                  fill={theme.palette.text.primary}
                  fontSize={12}
                >
                  Node {n.id}
                </text>
              )}
            </g>
          )
        })}
        {loads.map((l, i) => arrow(l.position, l.force, `load${i}`))}
        {moments
          .filter((m) => Math.hypot(...m.value) > 0)
          .map((m, i) => {
            const magnitude = Math.hypot(...m.value),
              axis = m.value.map((v) => v / magnitude) as Vec
            const cross = (a: Vec, b: Vec): Vec => [
              a[1] * b[2] - a[2] * b[1],
              a[2] * b[0] - a[0] * b[2],
              a[0] * b[1] - a[1] * b[0],
            ]
            const seed: Vec = Math.abs(axis[2]) < 0.9 ? [0, 0, 1] : [0, 1, 0],
              raw = cross(axis, seed),
              u = raw.map((v) => v / Math.hypot(...raw)) as Vec,
              v = cross(axis, u),
              p = screen(m.position)
            const arc = Array.from({ length: 22 }, (_, j) => {
              const t = 0.2 + (j * 5) / 21,
                offset = project(
                  u.map((x, k) => x * Math.cos(t) + v[k] * Math.sin(t)) as Vec,
                  axes,
                )
              return `${j ? 'L' : 'M'}${p[0] + offset[0] * 20},${p[1] - offset[1] * 20}`
            }).join(' ')
            return (
              <g key={`moment${i}`} fill={theme.palette.error.main}>
                <path
                  d={arc}
                  fill="none"
                  stroke={theme.palette.error.main}
                  strokeWidth={1.7}
                  markerEnd={`url(#${arrowId})`}
                />
                <text x={p[0] + 22} y={p[1]} fontSize={10}>
                  M
                </text>
                <title>
                  Global moment:{' '}
                  {m.value.map((v) => v.toPrecision(4)).join(', ')} N m
                </title>
              </g>
            )
          })}
        {localFrame && (
          <g aria-label="Local plate axes">
            {[
              localFrame.ex,
              localFrame.ey,
              [
                localFrame.ex[1] * localFrame.ey[2] -
                  localFrame.ex[2] * localFrame.ey[1],
                localFrame.ex[2] * localFrame.ey[0] -
                  localFrame.ex[0] * localFrame.ey[2],
                localFrame.ex[0] * localFrame.ey[1] -
                  localFrame.ex[1] * localFrame.ey[0],
              ] as Vec,
            ].map((v, i) => {
              const a = project(v, axes)
              return (
                <g
                  key={i}
                  fill={theme.palette.primary.main}
                  stroke={theme.palette.primary.main}
                >
                  <line
                    x1={175}
                    y1={460}
                    x2={175 + a[0] * 32}
                    y2={460 - a[1] * 32}
                  />
                  <text
                    x={175 + a[0] * 44}
                    y={460 - a[1] * 44}
                    fontSize={11}
                    stroke="none"
                  >
                    {['ex', 'ey', 'n'][i]}
                  </text>
                </g>
              )
            })}
          </g>
        )}
        {[0, 1, 2].map((i) => {
          const a = project([+(i === 0), +(i === 1), +(i === 2)], axes)
          const color = [
            theme.palette.error.main,
            theme.palette.primary.main,
            theme.palette.secondary.main,
          ][i]
          return (
            <g key={i} stroke={color} fill={color}>
              <line x1={65} y1={460} x2={65 + a[0] * 35} y2={460 - a[1] * 35} />
              <text
                x={65 + a[0] * 48}
                y={460 - a[1] * 48}
                fontSize={12}
                stroke="none"
              >
                {'XYZ'[i]}
              </text>
            </g>
          )
        })}
      </svg>
      <Box
        sx={{ position: 'absolute', top: 16, left: 18, pointerEvents: 'none' }}
      >
        <Typography variant="body2">
          {hasResult ? quantityLabel : meshLabel}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {hasResult
            ? `Deformation ×${scale} · dashed reference`
            : 'Orbit: drag · Pan: Shift + drag'}
        </Typography>
        {hasResult && showContour && (
          <Box sx={{ mt: 1, bgcolor: 'background.paper', p: 1 }}>
            <Box
              sx={{
                width: 160,
                height: 6,
                background: `linear-gradient(to right, ${theme.palette.secondary.main}, ${theme.palette.error.main})`,
              }}
            />
            <Typography variant="caption">
              {low.toExponential(3)} — {high.toExponential(3)} {unit}
            </Typography>
            <Typography
              sx={{ display: 'block' }}
              variant="caption"
              color="text.secondary"
            >
              {contourCaption}
            </Typography>
          </Box>
        )}
      </Box>
      <ButtonGroup
        size="small"
        variant="text"
        sx={{
          position: 'absolute',
          bottom: 36,
          right: 12,
          bgcolor: 'background.paper',
        }}
      >
        <Button
          onClick={() => setZoom((v) => Math.min(v * 1.2, 8))}
          aria-label="Zoom in mesh"
        >
          +
        </Button>
        <Button
          onClick={() => setZoom((v) => Math.max(v / 1.2, 0.2))}
          aria-label="Zoom out mesh"
        >
          −
        </Button>
        <Button
          onClick={() => {
            setZoom(1)
            setPan([0, 0])
          }}
        >
          Fit
        </Button>
        <Button onClick={() => setCamera({ azimuth: -0.65, elevation: 0.55 })}>
          Iso
        </Button>
        <Button
          onClick={() => setCamera({ azimuth: 0, elevation: Math.PI / 2 })}
        >
          XY
        </Button>
        <Button onClick={() => setCamera({ azimuth: 0, elevation: 0 })}>
          XZ
        </Button>
        <Button
          onClick={() => setCamera({ azimuth: Math.PI / 2, elevation: 0 })}
        >
          YZ
        </Button>
      </ButtonGroup>
      <Typography
        sx={{ position: 'absolute', bottom: 12, left: 16 }}
        variant="caption"
        color="text.secondary"
      >
        m · N · Pa · {model.nodes.length} nodes · {model.elements.length}{' '}
        elements
      </Typography>
    </Box>
  )
}
