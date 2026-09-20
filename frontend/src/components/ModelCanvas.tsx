import {
  defaultHoleDimensions,
  replaceOutline,
  shapePoints,
  upsertHole,
  type HoleDimensions,
} from '../cadGeometry'
import { Alert, MenuItem, TextField } from '@mui/material'
import { nearestBoundaryEdge, type PlacementTarget } from '../loadPlacement'
import Button from '@mui/material/Button'
import { FrameDiagramLayer } from './FrameDiagramLayer'
import {
  frameDiagrams,
  frameQuantityLabels,
  type FrameQuantity,
} from '../frameDiagrams'
import CenterFocusStrongRoundedIcon from '@mui/icons-material/CenterFocusStrongRounded'
import ZoomInRoundedIcon from '@mui/icons-material/ZoomInRounded'
import ZoomOutRoundedIcon from '@mui/icons-material/ZoomOutRounded'
import PanToolRoundedIcon from '@mui/icons-material/PanToolRounded'
import { alpha, useTheme } from '@mui/material/styles'
import GridOnRoundedIcon from '@mui/icons-material/GridOnRounded'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import IconButton from '@mui/material/IconButton'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type MouseEvent,
  type PointerEvent as ReactPointerEvent,
} from 'react'
import {
  clientToSvg,
  fitCamera,
  gridInterval,
  projectPoint,
  unprojectPoint,
  zoomCamera,
  type Camera,
  type Point,
} from '../canvasViewport'
import type {
  Dof,
  JsonValue,
  LoadInput,
  ModelInput,
  ResultView,
  Selection,
  SolveResult,
} from '../domain'
import {
  elementDisplayLabel,
  loadDisplayLabel,
  nodeDisplayLabel,
  supportDisplayLabel,
} from '../entityLabels'
import {
  addFrameMember,
  placeFramePoint,
  addOuterVertexAt,
  geometryNeedsMesh,
  CadTool,
  getSketch,
  isGeneratedMesh,
  isSurfaceFamily,
  moveFrameNode,
  moveSketchVertex,
  nodeForSketchVertex,
  PlacementState,
} from '../geometrySketch'
import { meshBoundaries, meshStatusForModel } from '../meshing'
import { dofsForModel, MODEL_FAMILIES } from '../modelFamilies'
import {
  displacementByNode,
  elementInternalLabel,
  elementRecords,
  elementResultScalar,
  formatNumber,
  reactionByNode,
} from '../resultUtils'

interface ModelCanvasProps {
  readOnly?: boolean
  showResultControls?: boolean
  model: ModelInput
  result: SolveResult | null
  selectedStep: number
  view: ResultView
  selection: Selection
  cadTool: CadTool
  placement: PlacementState
  pendingMember: string | null
  onViewChange: (view: ResultView) => void
  onStepChange?: (step: number) => void
  onSelection: (selection: Selection) => void
  onModelChange: (model: ModelInput, selection?: Selection) => void
  onPlace: (target: PlacementTarget) => void
  onPlacementChange?: (placement: PlacementState) => void
  onPendingMember: (nodeId: string | null) => void
  holeDimensions?: HoleDimensions
  onStopDrawing?: () => void
}

const TRANSLATIONAL_DOFS: Dof[] = ['UX', 'UY', 'UZ']

const activateOnKeyboard = (
  event: KeyboardEvent<SVGGElement | SVGCircleElement>,
  action: () => void,
) => {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    event.stopPropagation()
    action()
  }
}

export function ModelCanvas({
  readOnly = false,
  showResultControls = false,
  holeDimensions = defaultHoleDimensions,
  onStopDrawing,
  model: inputModel,
  result,
  selectedStep,
  view,
  selection,
  cadTool,
  placement,
  pendingMember,
  onViewChange,
  onStepChange,
  onSelection,
  onModelChange,
  onPlace,
  onPlacementChange,
  onPendingMember,
}: ModelCanvasProps) {
  const theme = useTheme()
  const CANVAS = theme.palette.background.canvas
  const instanceId = useId().replace(/:/g, '')
  const svgRef = useRef<SVGSVGElement>(null)
  const [viewport, setViewport] = useState({ width: 1000, height: 560 })
  const { width: WIDTH, height: HEIGHT } = viewport
  const [camera, setCamera] = useState<Camera | null>(null)
  const [panMode, setPanMode] = useState(false)
  const [pointer, setPointer] = useState<Point | null>(null)
  const [dragModel, setDragModel] = useState<ModelInput | null>(null)
  const model = dragModel ?? inputModel
  const [outlinePoints, setOutlinePoints] = useState<number[][]>([])
  const [cadError, setCadError] = useState('')
  const [coordinate, setCoordinate] = useState({ x: '', y: '' })
  useEffect(() => {
    setOutlinePoints([])
    setCadError('')
  }, [cadTool])
  const [showGrid, setShowGrid] = useState(true)
  const dragRef = useRef<{
    id: string
    kind: 'sketch' | 'frame' | 'pan'
    moved: boolean
    start: Point
    camera: Camera
    model: ModelInput
    preview: ModelInput | null
  } | null>(null)
  useEffect(() => {
    const svg = svgRef.current
    if (!svg || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      if (width > 0 && height > 0) setViewport({ width, height })
    })
    observer.observe(svg)
    return () => observer.disconnect()
  }, [])
  const skipClickRef = useRef(false)
  const family = MODEL_FAMILIES[model.model_family]
  const dofs = dofsForModel(model)
  const isSurface = family.elementNodeCount === 4
  const meshStatus = meshStatusForModel(model)
  const hideMeshNodes = isGeneratedMesh(model)
  const geometryOnly =
    !readOnly && (geometryNeedsMesh(model) || cadTool === 'draw-outline')
  const hideFeNodes = geometryOnly
  const sketch = getSketch(model)
  const denseSurfaceMesh =
    isSurface && (model.nodes.length > 80 || model.elements.length > 80)
  const editingCad = !readOnly && (cadTool !== 'select' || Boolean(placement))
  const hasOutOfPlane = dofs.includes('UZ')
  const step = result?.steps[selectedStep]
  const displacements = useMemo(
    () => displacementByNode(model, result, step),
    [model, result, step],
  )
  const reactions = useMemo(() => reactionByNode(result), [result])
  const resultElements = useMemo(() => elementRecords(result), [result])
  const maxDisplacement = Math.max(
    0,
    ...Array.from(displacements.values()).map((value) =>
      Math.hypot(
        Number(value.UX ?? 0),
        Number(value.UY ?? 0),
        Number(value.UZ ?? 0),
      ),
    ),
  )
  const xs = [
    ...model.nodes.map((node) => node.coordinates[0] ?? 0),
    ...sketch.vertices.map((vertex) => vertex.coordinates[0] ?? 0),
  ]
  const ys = [
    ...model.nodes.map((node) => node.coordinates[1] ?? 0),
    ...sketch.vertices.map((vertex) => vertex.coordinates[1] ?? 0),
  ]
  if (!xs.length) xs.push(0, 1)
  if (!ys.length) ys.push(0, 1)
  const modelSpan = Math.max(
    1e-9,
    Math.max(...xs) - Math.min(...xs),
    Math.max(...ys) - Math.min(...ys),
  )
  const deformationScale =
    maxDisplacement > 0
      ? Math.min(25, Math.max(1, (modelSpan * 0.15) / maxDisplacement))
      : 1
  const shouldDeform = view === 'deformation' && result !== null
  const positions = new Map(
    model.nodes.map((node) => {
      const displacement = displacements.get(node.id) ?? {}
      const uzLift = hasOutOfPlane ? Number(displacement.UZ ?? 0) * 0.28 : 0
      return [
        node.id,
        {
          x:
            (node.coordinates[0] ?? 0) +
            (shouldDeform
              ? (Number(displacement.UX ?? 0) + uzLift) * deformationScale
              : 0),
          y:
            (node.coordinates[1] ?? 0) +
            (shouldDeform
              ? (Number(displacement.UY ?? 0) + uzLift) * deformationScale
              : 0),
        },
      ]
    }),
  )
  const allX = [
    ...outlinePoints.map((p) => p[0]),
    ...xs,
    ...Array.from(positions.values()).map((point) => point.x),
  ]
  const allY = [
    ...outlinePoints.map((p) => p[1]),
    ...ys,
    ...Array.from(positions.values()).map((point) => point.y),
  ]
  const fitted = fitCamera(
    allX.map((x, index) => ({ x, y: allY[index] })),
    viewport,
  )
  const activeCamera = camera ?? fitted
  const scale = activeCamera.scale
  const project = (point: Point) => projectPoint(point, activeCamera, viewport)
  const unproject = (screenX: number, screenY: number) =>
    unprojectPoint({ x: screenX, y: screenY }, activeCamera, viewport)
  const svgPoint = (event: { clientX: number; clientY: number }) => {
    const svg = svgRef.current
    if (!svg) return { x: 0, y: 0 }
    const matrix = svg.getScreenCTM?.()
    if (matrix && typeof DOMPoint !== 'undefined') {
      const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(
        matrix.inverse(),
      )
      return { x: point.x, y: point.y }
    }
    return clientToSvg(
      { x: event.clientX, y: event.clientY },
      svg.getBoundingClientRect(),
      viewport,
    )
  }
  const zoom = (factor: number, anchor = { x: WIDTH / 2, y: HEIGHT / 2 }) => {
    setCamera(zoomCamera(activeCamera, factor, anchor, viewport))
  }
  const gridSize = gridInterval(scale)
  const gridPixels = gridSize * scale
  const origin = project({ x: 0, y: 0 })
  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return
    const onWheel = (event: WheelEvent) => {
      if (event.ctrlKey) return
      event.preventDefault()
      setCamera(
        zoomCamera(
          activeCamera,
          Math.exp(-Math.max(-100, Math.min(100, event.deltaY)) * 0.002),
          svgPoint(event),
          viewport,
        ),
      )
    }
    svg.addEventListener('wheel', onWheel, { passive: false })
    return () => svg.removeEventListener('wheel', onWheel)
  }, [activeCamera, viewport])
  useEffect(() => {
    setPanMode(false)
  }, [cadTool, placement])
  const nodeScreen = new Map(
    Array.from(positions, ([id, point]) => [id, project(point)]),
  )
  const referenceScreen = new Map(
    model.nodes.map((node) => [
      node.id,
      project({ x: node.coordinates[0] ?? 0, y: node.coordinates[1] ?? 0 }),
    ]),
  )
  const constrainedNodes = new Set(
    model.constraints.map((constraint) => constraint.node_id),
  )
  const loadedNodes = new Map<string, LoadInput[]>()
  model.loads
    .filter((load) => load.kind === 'nodal' && load.node_id)
    .forEach((load) => {
      loadedNodes.set(load.node_id!, [
        ...(loadedNodes.get(load.node_id!) ?? []),
        load,
      ])
    })
  const reactionValues = Array.from(reactions.values()).flatMap((value) =>
    dofs.map((dof) => Math.abs(Number(value[dof] ?? 0))),
  )
  const maxReaction = Math.max(1e-12, ...reactionValues)
  const resultByElement = new Map(
    resultElements.map((record) => [String(record.element_id), record]),
  )
  const elementById = new Map(
    model.elements.map((element) => [element.id, element]),
  )
  const boundaryById = new Map(
    meshBoundaries(model).map((boundary) => [boundary.id, boundary]),
  )
  const maxInternal = Math.max(
    1e-12,
    ...resultElements.map((record) =>
      elementResultScalar(model.model_family, record),
    ),
  )
  const lastAcceptedStep =
    result?.steps.reduce(
      (last, step, index) => (step.status === 'accepted' ? index : last),
      -1,
    ) ?? -1
  const isFinalStep = Boolean(result && selectedStep === lastAcceptedStep)
  const isFrameDiagram =
    model.model_family === 'frame' &&
    ['internal', 'moment', 'shear', 'axial'].includes(view)
  const quantity: FrameQuantity =
    view === 'shear' || view === 'axial' ? view : 'moment'
  const diagrams = useMemo(() => frameDiagrams(model, result), [model, result])
  const maximumDiagram = Math.max(
    0,
    ...diagrams.flatMap((d) => d.stations.map((p) => Math.abs(p[quantity]))),
  )
  const selectedDiagram =
    selection.kind === 'elements'
      ? diagrams.find((d) => d.elementId === selection.id)
      : undefined

  const screenLoadVector = (load: LoadInput, elementId?: string) => {
    if (load.kind === 'element' && elementId) {
      const element = elementById.get(elementId)
      const left = element ? positions.get(element.node_ids[0]) : undefined
      const right = element ? positions.get(element.node_ids[1]) : undefined
      if (left && right) {
        const length = Math.hypot(right.x - left.x, right.y - left.y) || 1
        const c = (right.x - left.x) / length
        const s = (right.y - left.y) / length
        const qx = Number(load.components.qx_i ?? load.components.UX ?? 0)
        const qy = Number(load.components.qy_i ?? load.components.UY ?? 0)
        const globalX = c * qx - s * qy
        const globalY = s * qx + c * qy
        return { dx: globalX, dy: -globalY }
      }
    }
    const ux = Number(load.components.UX ?? 0)
    const uy = Number(load.components.UY ?? 0)
    const uz = Number(load.components.UZ ?? 0)
    return { dx: ux + 0.7 * uz, dy: -uy - 0.7 * uz }
  }

  const distributedGlyphs: Array<{
    key: string
    loadId: string
    x: number
    y: number
    dx: number
    dy: number
    label?: string
  }> = []
  model.loads
    .filter((load) => load.kind !== 'nodal')
    .forEach((load) => {
      const vector = screenLoadVector(load, load.element_id ?? undefined)
      const magnitude = Math.hypot(vector.dx, vector.dy)
      if (magnitude <= 0) return
      const direction = {
        dx: (34 * vector.dx) / magnitude,
        dy: (34 * vector.dy) / magnitude,
      }
      const addGlyphs = (targets: Array<{ x: number; y: number }>) => {
        const stride = Math.max(1, Math.ceil(targets.length / 24))
        const visibleTargets = targets.filter(
          (_, index) => index % stride === 0,
        )
        visibleTargets.forEach((target, index) =>
          distributedGlyphs.push({
            key: `${load.id}-${index}`,
            loadId: load.id,
            x: target.x,
            y: target.y,
            ...direction,
            label:
              index === Math.floor(visibleTargets.length / 2)
                ? loadDisplayLabel(model, load.id)
                : undefined,
          }),
        )
      }
      if (load.kind === 'element' && load.element_id) {
        const element = elementById.get(load.element_id)
        const left = element ? nodeScreen.get(element.node_ids[0]) : undefined
        const right = element ? nodeScreen.get(element.node_ids[1]) : undefined
        if (left && right)
          addGlyphs(
            [0.15, 0.325, 0.5, 0.675, 0.85].map((ratio) => ({
              x: left.x + ratio * (right.x - left.x),
              y: left.y + ratio * (right.y - left.y),
            })),
          )
        return
      }
      if (load.kind === 'surface') {
        const rawIds = load.extensions?.element_ids
        const ids = Array.isArray(rawIds)
          ? rawIds.map(String)
          : load.element_id
            ? [load.element_id]
            : []
        addGlyphs(
          ids.flatMap((elementId) => {
            const element = elementById.get(elementId)
            if (!element) return []
            const points = element.node_ids
              .map((nodeId) => nodeScreen.get(nodeId))
              .filter(Boolean) as Array<{ x: number; y: number }>
            if (!points.length) return []
            return [
              {
                x:
                  points.reduce((sum, point) => sum + point.x, 0) /
                  points.length,
                y:
                  points.reduce((sum, point) => sum + point.y, 0) /
                  points.length,
              },
            ]
          }),
        )
        return
      }
      if (load.kind === 'edge') {
        const boundaryId =
          typeof load.extensions?.boundary_id === 'string'
            ? load.extensions.boundary_id
            : ''
        const boundary = boundaryById.get(boundaryId)
        const rawSegments =
          boundary?.segments ??
          (Array.isArray(load.extensions?.edge_segments)
            ? load.extensions.edge_segments.flatMap((candidate) => {
                if (
                  !candidate ||
                  typeof candidate !== 'object' ||
                  Array.isArray(candidate)
                )
                  return []
                const record = candidate as Record<string, JsonValue>
                return typeof record.element_id === 'string' &&
                  typeof record.local_edge === 'number'
                  ? [
                      {
                        element_id: record.element_id,
                        local_edge: record.local_edge,
                      },
                    ]
                  : []
              })
            : [])
        const segments = rawSegments.length
          ? rawSegments
          : load.element_id
            ? [
                {
                  element_id: load.element_id,
                  local_edge: Number(load.extensions?.local_edge ?? 0),
                },
              ]
            : []
        const edgePairs = [
          [0, 1],
          [1, 2],
          [2, 3],
          [3, 0],
        ]
        addGlyphs(
          segments.flatMap((segment) => {
            const element = elementById.get(segment.element_id)
            const pair = edgePairs[segment.local_edge]
            if (!element || !pair) return []
            const left = nodeScreen.get(element.node_ids[pair[0]])
            const right = nodeScreen.get(element.node_ids[pair[1]])
            return left && right
              ? [{ x: (left.x + right.x) / 2, y: (left.y + right.y) / 2 }]
              : []
          }),
        )
      }
    })

  const worldFromEvent = (event: {
    currentTarget: Element
    clientX: number
    clientY: number
  }) => {
    const screen = svgPoint(event)
    return unproject(screen.x, screen.y)
  }

  const selectElement = (event: MouseEvent<SVGGElement>, id: string) => {
    event.stopPropagation()
    if (panMode) return
    if (placement?.kind === 'load') {
      const world = worldFromEvent(event)
      onPlace({
        kind: 'element',
        id,
        localEdge: nearestBoundaryEdge(model, id, [world.x, world.y]),
      })
      return
    }
    if (editingCad) return
    onSelection({ kind: 'elements', id })
  }

  const beginDrag = (
    event: ReactPointerEvent<SVGElement>,
    kind: 'sketch' | 'frame' | 'pan',
    id = '',
  ) => {
    if (event.button !== 0 && event.button !== 1) return
    event.preventDefault()
    event.stopPropagation()
    svgRef.current?.setPointerCapture?.(event.pointerId)
    setCamera(activeCamera)
    dragRef.current = {
      id,
      kind,
      moved: false,
      start: svgPoint(event),
      camera: activeCamera,
      model,
      preview: null,
    }
  }

  const handleCanvasPointerMove = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (cadTool !== 'select' && !readOnly) setPointer(svgPoint(event))
    const drag = dragRef.current
    if (!drag) return
    const point = svgPoint(event)
    if (
      !drag.moved &&
      Math.hypot(point.x - drag.start.x, point.y - drag.start.y) < 4
    )
      return
    drag.moved = true
    if (drag.kind === 'pan') {
      setCamera({
        ...drag.camera,
        x: drag.camera.x - (point.x - drag.start.x) / drag.camera.scale,
        y: drag.camera.y + (point.y - drag.start.y) / drag.camera.scale,
      })
      return
    }
    if (readOnly) return
    const delta = {
      x: (point.x - drag.start.x) / drag.camera.scale,
      y: -(point.y - drag.start.y) / drag.camera.scale,
    }
    const original =
      drag.kind === 'sketch'
        ? getSketch(drag.model).vertices.find((vertex) => vertex.id === drag.id)
            ?.coordinates
        : drag.model.nodes.find((node) => node.id === drag.id)?.coordinates
    if (!original) return
    const coordinates = [original[0] + delta.x, original[1] + delta.y]
    drag.preview =
      drag.kind === 'sketch'
        ? moveSketchVertex(drag.model, drag.id, coordinates)
        : moveFrameNode(drag.model, drag.id, coordinates)
    setDragModel(drag.preview)
  }

  const handleCanvasPointerUp = (event: ReactPointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current
    dragRef.current = null
    if (svgRef.current?.hasPointerCapture?.(event.pointerId))
      svgRef.current.releasePointerCapture(event.pointerId)
    if (drag?.moved) {
      skipClickRef.current = true
      if (drag.preview && !readOnly)
        onModelChange(drag.preview, {
          kind: drag.kind === 'sketch' ? 'geometry' : 'nodes',
          id: drag.id,
        })
    }
    setDragModel(null)
  }

  const cancelDrag = () => {
    if (dragRef.current) {
      setCamera(dragRef.current.camera)
      skipClickRef.current = true
    }
    dragRef.current = null
    setDragModel(null)
  }

  const finishOutline = () => {
    try {
      const next = replaceOutline(model, outlinePoints)
      onModelChange(next, { kind: 'geometry' })
      setOutlinePoints([])
      setCadError('')
      onStopDrawing?.()
    } catch (error) {
      setCadError(error instanceof Error ? error.message : 'Check the outline.')
    }
  }
  const appendOutlinePoint = (point: number[]) => {
    setOutlinePoints((points) => [...points, point])
    setCadError('')
  }
  const handleCanvasClick = (event: MouseEvent<SVGSVGElement>) => {
    if (skipClickRef.current) {
      skipClickRef.current = false
      return
    }
    if (readOnly || panMode) return
    setCamera(activeCamera)
    const world = worldFromEvent(event)
    if (cadTool === 'draw-outline' && isSurfaceFamily(model)) {
      if (
        outlinePoints.length >= 3 &&
        Math.hypot(
          world.x - outlinePoints[0][0],
          world.y - outlinePoints[0][1],
        ) <
          10 / scale
      )
        finishOutline()
      else {
        const previous = outlinePoints.at(-1)
        const point =
          event.shiftKey && previous
            ? Math.abs(world.x - previous[0]) > Math.abs(world.y - previous[1])
              ? [world.x, previous[1]]
              : [previous[0], world.y]
            : [world.x, world.y]
        appendOutlinePoint(point)
      }
      return
    }
    if (cadTool === 'add-vertex' && isSurfaceFamily(model)) {
      const next = addOuterVertexAt(model, [world.x, world.y])
      const added = getSketch(next).vertices.at(-1)
      onModelChange(
        next,
        added ? { kind: 'geometry', id: added.id } : { kind: 'model' },
      )
      return
    }
    if (cadTool === 'add-hole' && isSurfaceFamily(model)) {
      try {
        const added = upsertHole(model, {
          ...holeDimensions,
          center: [world.x, world.y],
        })
        onModelChange(added.model, { kind: 'geometry', id: added.id })
        setCadError('')
        onStopDrawing?.()
        onSelection({ kind: 'geometry', id: added.id })
      } catch (error) {
        setCadError(error instanceof Error ? error.message : 'Check the hole.')
      }
      return
    }
    if (
      (cadTool === 'add-node' || cadTool === 'add-member') &&
      !isSurfaceFamily(model)
    ) {
      const added = placeFramePoint(model, [world.x, world.y], 10 / scale)
      if (cadTool === 'add-node') {
        onModelChange(added.model, { kind: 'nodes', id: added.nodeId })
      } else if (!pendingMember) {
        onModelChange(added.model, { kind: 'nodes', id: added.nodeId })
        onPendingMember(added.nodeId)
      } else if (pendingMember !== added.nodeId) {
        const next = addFrameMember(added.model, pendingMember, added.nodeId)
        onModelChange(next, { kind: 'elements', id: next.elements.at(-1)?.id })
        onPendingMember(null)
      }
      return
    }
    if (!placement) onSelection({ kind: 'model' })
  }

  const placeNode = (nodeId: string | undefined) => {
    if (nodeId) onPlace({ kind: 'node', id: nodeId })
  }

  const canvasCursor = panMode
    ? 'grab'
    : readOnly
      ? 'default'
      : placement
        ? 'copy'
        : cadTool === 'draw-outline' ||
            cadTool === 'add-vertex' ||
            cadTool === 'add-hole' ||
            cadTool === 'add-node'
          ? 'crosshair'
          : cadTool === 'add-member'
            ? 'cell'
            : 'default'

  const glyphProps = (selected: Selection, label: string) => {
    const enabled = !readOnly && cadTool === 'select' && !placement && !panMode
    return {
      role: enabled ? 'button' : undefined,
      tabIndex: enabled ? 0 : undefined,
      'aria-label': enabled ? `Select ${label}` : undefined,
      style: { cursor: enabled ? 'pointer' : 'default' },
      onPointerDown: (event: ReactPointerEvent<SVGGElement>) => {
        if (enabled) event.stopPropagation()
      },
      onClick: (event: MouseEvent<SVGGElement>) => {
        if (enabled) {
          event.stopPropagation()
          onSelection(selected)
        }
      },
      onKeyDown: (event: KeyboardEvent<SVGGElement>) => {
        if (enabled) activateOnKeyboard(event, () => onSelection(selected))
      },
    }
  }

  const renderSupportAndLoad = (
    point: { x: number; y: number },
    nodeId: string,
  ) => {
    const loads = loadedNodes.get(nodeId) ?? []
    const components = loads.flatMap((load) =>
      dofs
        .filter((dof) => Math.abs(load.components[dof] ?? 0) > 0)
        .map((dof) => ({ load, dof, sign: Math.sign(load.components[dof]!) })),
    )
    return (
      <>
        {constrainedNodes.has(nodeId) && (
          <g
            {...glyphProps(
              { kind: 'constraints', id: nodeId },
              `${supportDisplayLabel(model, nodeId)} on canvas`,
            )}
          >
            <path
              d={`M ${point.x - 13} ${point.y + 21} L ${point.x + 13} ${point.y + 21} L ${point.x} ${point.y + 4} Z`}
              fill={
                selection.kind === 'constraints' && selection.id === nodeId
                  ? theme.palette.primary.main
                  : '#8c96a8'
              }
              stroke="#596477"
              strokeWidth="1.5"
            />
          </g>
        )}
        {!isFrameDiagram &&
          view !== 'reactions' &&
          components.map(({ load, dof, sign }, index) => {
            const length = 48 + index * 16
            const dx =
              dof === 'UX'
                ? length * sign
                : dof === 'UY'
                  ? 0
                  : length * 0.7 * sign
            const dy =
              dof === 'UY'
                ? -length * sign
                : dof === 'UX'
                  ? 0
                  : -length * 0.7 * sign
            const rotational = dof.startsWith('R')
            return (
              <g
                key={`${load.id}-${dof}`}
                {...glyphProps(
                  { kind: 'loads', id: load.id },
                  `${loadDisplayLabel(model, load.id)} ${dof} on canvas`,
                )}
              >
                <rect
                  x={Math.min(point.x, point.x + dx) - 8}
                  y={
                    rotational
                      ? point.y - 45
                      : Math.min(point.y, point.y + dy) - 16
                  }
                  width={Math.abs(dx) + 125}
                  height={rotational ? 64 : Math.abs(dy) + 24}
                  fill="transparent"
                />
                {!rotational && (
                  <line
                    x1={point.x}
                    y1={point.y}
                    x2={point.x + dx}
                    y2={point.y + dy}
                    stroke="transparent"
                    strokeWidth="14"
                  />
                )}
                {rotational ? (
                  <path
                    d={`M ${point.x - 20} ${point.y - 10} A 24 24 0 1 ${sign > 0 ? 0 : 1} ${point.x + 20} ${point.y - 10}`}
                    fill="none"
                    stroke="#d64e66"
                    strokeWidth="2.5"
                    markerEnd={`url(#${instanceId}-load-arrow)`}
                  />
                ) : (
                  <line
                    x1={point.x}
                    y1={point.y}
                    x2={point.x + dx}
                    y2={point.y + dy}
                    stroke="#d64e66"
                    strokeWidth="2.5"
                    markerEnd={`url(#${instanceId}-load-arrow)`}
                  />
                )}
                <text
                  x={point.x + (rotational ? 26 : dx + 7)}
                  y={point.y + (rotational ? -26 - index * 12 : dy - 6)}
                  fill="#a42d43"
                  fontSize="10"
                >
                  {loadDisplayLabel(model, load.id)} · {dof}
                </text>
              </g>
            )
          })}
      </>
    )
  }

  return (
    <Box
      sx={{
        position: 'relative',
        minWidth: 0,
        minHeight: 0,
        height: '100%',
        overflow: 'hidden',
        bgcolor: 'background.canvas',
        '& [role=button]:focus-visible': {
          outline: '2px solid',
          outlineColor: 'primary.main',
          outlineOffset: 4,
        },
        '& [role=button]:hover': { filter: 'brightness(0.8)' },
      }}
    >
      <Stack
        direction="row"
        spacing={1}
        sx={{
          position: 'absolute',
          zIndex: 2,
          top: 12,
          left: 12,
          right: 12,
          alignItems: 'flex-start',
          pointerEvents: 'none',
          '& > *': { pointerEvents: 'auto' },
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            flexWrap: 'wrap',
            maxWidth: '100%',
          }}
        >
          {showResultControls && (
            <ToggleButtonGroup
              aria-label="Result quantity"
              sx={{ flexWrap: 'wrap' }}
              exclusive
              size="small"
              value={isFrameDiagram ? quantity : view}
              onChange={(_, value: ResultView | null) =>
                value && onViewChange(value)
              }
            >
              <ToggleButton value="model">Model</ToggleButton>
              <ToggleButton value="deformation" disabled={!result}>
                Deformation
              </ToggleButton>
              <ToggleButton value="reactions" disabled={!result}>
                Reactions
              </ToggleButton>
              {model.model_family === 'frame' ? (
                (['moment', 'shear', 'axial'] as const).map((q) => (
                  <ToggleButton key={q} value={q} disabled={!result}>
                    {frameQuantityLabels[q]}
                  </ToggleButton>
                ))
              ) : (
                <ToggleButton value="internal" disabled={!result}>
                  Internal / stress
                </ToggleButton>
              )}
            </ToggleButtonGroup>
          )}
          {shouldDeform && (
            <Chip
              size="small"
              label={`Deformation × ${formatNumber(deformationScale, 2)}`}
            />
          )}
          {result && (
            <Chip
              size="small"
              color={result.status === 'succeeded' ? 'success' : 'error'}
              label={`Step ${step?.step_index ?? '—'} · λ ${formatNumber(step?.load_factor)}`}
            />
          )}
          {result &&
            !isFinalStep &&
            (view === 'reactions' || view === 'internal') && (
              <Chip
                size="small"
                color="warning"
                label="Recovered fields use the final committed state"
              />
            )}
          {!showResultControls && (
            <Typography variant="caption" color="text.secondary">
              {geometryOnly
                ? 'Geometry · mesh pending'
                : isSurface
                  ? `${meshStatus.sourceLabel} · Q4 mesh`
                  : 'Frame · 2D'}
            </Typography>
          )}
        </Box>
        <Box sx={{ flex: 1 }} />
      </Stack>
      <Paper
        elevation={0}
        sx={{
          position: 'absolute',
          zIndex: 2,
          right: 16,
          bottom: 16,
          display: 'flex',
          alignItems: 'center',
          p: 0.5,
          border: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Tooltip
          title={showGrid ? 'Hide background grid' : 'Show background grid'}
        >
          <IconButton
            aria-label="Show background grid"
            aria-pressed={showGrid}
            size="small"
            onClick={() => setShowGrid((value) => !value)}
            color={showGrid ? 'primary' : 'default'}
          >
            <GridOnRoundedIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Zoom in (+)">
          <IconButton
            aria-label="Zoom in"
            size="small"
            onClick={() => zoom(1.25)}
          >
            <ZoomInRoundedIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Zoom out (−)">
          <IconButton
            aria-label="Zoom out"
            size="small"
            onClick={() => zoom(0.8)}
          >
            <ZoomOutRoundedIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Fit model (F)">
          <IconButton
            aria-label="Fit model"
            size="small"
            onClick={() => setCamera(null)}
          >
            <CenterFocusStrongRoundedIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Pan view · drag or use arrow keys">
          <IconButton
            aria-label="Pan view"
            aria-pressed={panMode}
            size="small"
            color={panMode ? 'primary' : 'default'}
            onClick={() => setPanMode((value) => !value)}
          >
            <PanToolRoundedIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Paper>
      {!readOnly && placement && (
        <Paper
          elevation={0}
          sx={{
            position: 'absolute',
            zIndex: 3,
            top: 44,
            left: '50%',
            transform: 'translateX(-50%)',
            px: 1.5,
            py: 0.75,
            borderRadius: 1,
            width: 'max-content',
            maxWidth: '85%',
            border: '1px solid',
            borderColor: 'divider',
          }}
        >
          <Typography variant="body2">
            {placement.kind === 'load'
              ? placement.loadKind === 'nodal'
                ? 'Click a node to place this point load.'
                : placement.loadKind === 'line'
                  ? isSurface
                    ? 'Click an exposed mesh edge to place this line load.'
                    : 'Click a member to place this line load.'
                  : placement.loadKind === 'surface'
                    ? 'Click a surface element to place this surface load.'
                    : 'First click: node → point load; member / boundary → line load.'
              : 'Click a node to place this support.'}{' '}
            Esc cancels.
          </Typography>
          {placement.kind === 'load' && (
            <TextField
              select
              size="small"
              label="Place load"
              value={placement.loadKind ?? 'auto'}
              sx={{ mt: 1, minWidth: 190 }}
              onChange={(event) =>
                onPlacementChange?.({
                  ...placement,
                  loadKind: event.target
                    .value as NonNullable<PlacementState>['loadKind'],
                })
              }
            >
              <MenuItem value="auto">Auto · node or element</MenuItem>
              <MenuItem value="nodal">Point load · node</MenuItem>
              <MenuItem value="line">Line load · member / edge</MenuItem>
              {(model.model_family === 'plate' ||
                model.model_family === 'shell') && (
                <MenuItem value="surface">Surface load · element</MenuItem>
              )}
            </TextField>
          )}
        </Paper>
      )}
      {!readOnly && cadTool !== 'select' && !placement && (
        <Paper
          elevation={0}
          sx={{
            position: 'absolute',
            zIndex: 3,
            top: 44,
            left: '50%',
            transform: 'translateX(-50%)',
            px: 1.5,
            py: 0.75,
            borderRadius: 1,
            width: 'max-content',
            maxWidth: '85%',
            border: '1px solid',
            borderColor: 'divider',
          }}
        >
          <Typography variant="body2">
            {cadTool === 'draw-outline' &&
              `${outlinePoints.length} vertices · Click corners, then Close outline. Shift aligns the next edge.`}
            {cadTool === 'add-vertex' &&
              'Click the contour to insert a vertex.'}
            {cadTool === 'add-hole' &&
              `Click inside the outline to place the ${holeDimensions.kind} hole center.`}
            {cadTool === 'add-node' &&
              'Click to add a node. Existing nodes snap within 10 px. Esc stops drawing.'}
            {cadTool === 'add-member' &&
              (pendingMember
                ? 'Click the end point or an existing node. Esc stops drawing.'
                : 'Click a start point or an existing node.')}
          </Typography>
          {cadTool === 'draw-outline' && (
            <Stack spacing={1} sx={{ mt: 1 }}>
              <Stack direction="row" spacing={1}>
                <Button
                  size="small"
                  variant="contained"
                  disabled={outlinePoints.length < 3}
                  onClick={finishOutline}
                >
                  Close outline
                </Button>
                <Button
                  size="small"
                  disabled={!outlinePoints.length}
                  onClick={() => {
                    setOutlinePoints((points) => points.slice(0, -1))
                    setCadError('')
                  }}
                >
                  Undo vertex
                </Button>
                <Button size="small" onClick={onStopDrawing}>
                  Cancel outline
                </Button>
              </Stack>
              <Stack direction="row" spacing={1}>
                {(['x', 'y'] as const).map((axis) => (
                  <TextField
                    key={axis}
                    label={`Vertex ${axis.toUpperCase()}`}
                    type="number"
                    size="small"
                    value={coordinate[axis]}
                    slotProps={{ htmlInput: { step: 'any' } }}
                    sx={{ width: 110 }}
                    onChange={(event) =>
                      setCoordinate({
                        ...coordinate,
                        [axis]: event.target.value,
                      })
                    }
                  />
                ))}
                <Button
                  size="small"
                  disabled={
                    !coordinate.x ||
                    !coordinate.y ||
                    !Number.isFinite(Number(coordinate.x)) ||
                    !Number.isFinite(Number(coordinate.y))
                  }
                  onClick={() => {
                    setCamera(activeCamera)
                    appendOutlinePoint([
                      Number(coordinate.x),
                      Number(coordinate.y),
                    ])
                  }}
                >
                  Add point
                </Button>
              </Stack>
            </Stack>
          )}
          {cadError && (
            <Alert severity="error" sx={{ mt: 1 }}>
              {cadError}
            </Alert>
          )}
        </Paper>
      )}
      {isFrameDiagram && (
        <Paper
          role="status"
          sx={{
            position: 'absolute',
            zIndex: 3,
            left: 16,
            right: 16,
            bottom: 66,
            px: 1.5,
            py: 1,
            bgcolor: 'background.paper',
            maxWidth: 510,
            border: '1px solid',
            borderColor: 'divider',
          }}
        >
          {!isFinalStep ? (
            <>
              <Typography variant="body2">
                Section diagrams are recovered for the last accepted state.
              </Typography>
              {lastAcceptedStep >= 0 && (
                <Button
                  size="small"
                  onClick={() => onStepChange?.(lastAcceptedStep)}
                >
                  Show last accepted step
                </Button>
              )}
            </>
          ) : !diagrams.length ? (
            <Typography variant="body2">
              No recovered Frame end actions are available. Run this model to
              generate diagrams.
            </Typography>
          ) : (
            <>
              <Typography variant="subtitle2">
                {frameQuantityLabels[quantity]} ·{' '}
                {quantity === 'moment' ? 'N·m' : 'N'} · max |value|{' '}
                {formatNumber(maximumDiagram)}
              </Typography>
              <Typography variant="caption" sx={{ display: 'block' }}>
                Local +y ordinates · Select a member for end values.
              </Typography>
              {selectedDiagram && (
                <Typography variant="caption" sx={{ display: 'block' }}>
                  {elementDisplayLabel(model, selectedDiagram.elementId)} · i{' '}
                  {formatNumber(selectedDiagram.stations[0][quantity])} · j{' '}
                  {formatNumber(selectedDiagram.stations.at(-1)![quantity])}
                </Typography>
              )}
              {diagrams.some((d) => d.memberLoads) && (
                <Typography
                  variant="caption"
                  color="warning.dark"
                  sx={{ display: 'block' }}
                >
                  Member-load correction uses reference local axes; approximate
                  at large rotation.
                </Typography>
              )}
            </>
          )}
        </Paper>
      )}
      <svg
        ref={svgRef}
        tabIndex={0}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="group"
        aria-label={`${family.label} 2D engineering projection`}
        style={{
          width: '100%',
          height: '100%',
          display: 'block',
          cursor: canvasCursor,
          touchAction: 'none',
        }}
        onClick={handleCanvasClick}
        onPointerDown={(event) => {
          if (panMode || event.button === 1 || event.altKey)
            beginDrag(event, 'pan')
        }}
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            cancelDrag()
            setPanMode(false)
            setOutlinePoints([])
            setCadError('')
            return
          }
          if (
            (event.target !== event.currentTarget &&
              event.key.startsWith('Arrow')) ||
            event.ctrlKey ||
            event.metaKey ||
            event.altKey ||
            event.nativeEvent.isComposing
          )
            return
          if (event.key === 'f' || event.key === 'F') setCamera(null)
          else if (event.key === '+' || event.key === '=') zoom(1.25)
          else if (event.key === '-') zoom(0.8)
          else if (event.key.startsWith('Arrow'))
            setCamera({
              ...activeCamera,
              x:
                activeCamera.x +
                (event.key === 'ArrowRight'
                  ? -40
                  : event.key === 'ArrowLeft'
                    ? 40
                    : 0) /
                  scale,
              y:
                activeCamera.y +
                (event.key === 'ArrowDown'
                  ? 40
                  : event.key === 'ArrowUp'
                    ? -40
                    : 0) /
                  scale,
            })
          else return
          event.preventDefault()
        }}
        onPointerMove={handleCanvasPointerMove}
        onPointerUp={handleCanvasPointerUp}
        onPointerCancel={cancelDrag}
        onLostPointerCapture={() => {
          if (dragRef.current) cancelDrag()
        }}
      >
        <defs>
          <pattern
            id={`${instanceId}-minor-grid`}
            x={origin.x}
            y={origin.y}
            width={gridPixels / 5}
            height={gridPixels / 5}
            patternUnits="userSpaceOnUse"
          >
            <circle cx="0.8" cy="0.8" r="0.65" fill={theme.palette.divider} />
          </pattern>
          <pattern
            id={`${instanceId}-major-grid`}
            x={origin.x}
            y={origin.y}
            width={gridPixels}
            height={gridPixels}
            patternUnits="userSpaceOnUse"
          >
            <path
              d={`M ${gridPixels} 0 L 0 0 0 ${gridPixels}`}
              fill="none"
              stroke={theme.palette.divider}
              strokeWidth="0.65"
            />
          </pattern>
          <marker
            id={`${instanceId}-load-arrow`}
            markerWidth="8"
            markerHeight="8"
            refX="7"
            refY="4"
            orient="auto"
          >
            <path d="M0,0 L8,4 L0,8 z" fill="#d64e66" />
          </marker>
          <marker
            id={`${instanceId}-reaction-arrow`}
            markerWidth="8"
            markerHeight="8"
            refX="7"
            refY="4"
            orient="auto"
          >
            <path d="M0,0 L8,4 L0,8 z" fill={theme.palette.secondary.main} />
          </marker>
        </defs>
        <rect width={WIDTH} height={HEIGHT} fill={CANVAS} />
        {showGrid && (
          <g pointerEvents="none">
            <rect
              width={WIDTH}
              height={HEIGHT}
              fill={`url(#${instanceId}-major-grid)`}
              opacity="0.45"
            />
            <line
              x1={0}
              x2={WIDTH}
              y1={origin.y}
              y2={origin.y}
              stroke={theme.palette.divider}
            />
            <line
              x1={origin.x}
              x2={origin.x}
              y1={0}
              y2={HEIGHT}
              stroke={theme.palette.divider}
            />
          </g>
        )}

        {shouldDeform &&
          model.elements.map((element) => {
            const points = element.node_ids
              .map((id) => referenceScreen.get(id))
              .filter(Boolean) as Array<{ x: number; y: number }>
            if (points.length !== element.node_ids.length) return null
            return isSurface ? (
              <polygon
                key={`reference-${element.id}`}
                points={points
                  .map((point) => `${point.x},${point.y}`)
                  .join(' ')}
                fill="none"
                stroke="#8c96a8"
                strokeDasharray="7 6"
                strokeWidth="2"
                opacity="0.8"
              />
            ) : (
              <line
                key={`reference-${element.id}`}
                x1={points[0].x}
                y1={points[0].y}
                x2={points[1].x}
                y2={points[1].y}
                stroke="#8c96a8"
                strokeDasharray="7 6"
                strokeWidth="2"
                opacity="0.8"
              />
            )
          })}

        {(!geometryOnly ? model.elements : []).map((element) => {
          const points = element.node_ids
            .map((id) => nodeScreen.get(id))
            .filter(Boolean) as Array<{ x: number; y: number }>
          if (points.length !== element.node_ids.length) return null
          const record = resultByElement.get(element.id) as
            Record<string, JsonValue> | undefined
          const forceLevel =
            view === 'internal' && record
              ? elementResultScalar(model.model_family, record) / maxInternal
              : 0
          const color =
            view === 'internal' && !isFrameDiagram
              ? `hsl(${205 - forceLevel * 165} 74% ${46 - forceLevel * 5}%)`
              : shouldDeform
                ? '#6f83c5'
                : '#354b74'
          const selected =
            selection.kind === 'elements' && selection.id === element.id
          const center = points.reduce(
            (sum, point) => ({
              x: sum.x + point.x / points.length,
              y: sum.y + point.y / points.length,
            }),
            { x: 0, y: 0 },
          )
          const action = () => {
            if (placement?.kind === 'load')
              onPlace({
                kind: 'element',
                id: element.id,
                localEdge: nearestBoundaryEdge(
                  model,
                  element.id,
                  model.nodes.find((node) => node.id === element.node_ids[0])!
                    .coordinates,
                ),
              })
            else if (!editingCad)
              onSelection({ kind: 'elements', id: element.id })
          }
          const elementLabel = elementDisplayLabel(model, element.id)
          const showLabel =
            selected || (!isFrameDiagram && !hideMeshNodes && !denseSurfaceMesh)
          return (
            <g
              key={element.id}
              role="button"
              tabIndex={
                (editingCad && placement?.kind !== 'load') || panMode ? -1 : 0
              }
              aria-label={`Select ${elementLabel}`}
              onKeyDown={(event) => activateOnKeyboard(event, action)}
              onClick={(event) => selectElement(event, element.id)}
              style={{
                cursor: editingCad ? canvasCursor : 'pointer',
                pointerEvents:
                  (editingCad && placement?.kind !== 'load') || panMode
                    ? 'none'
                    : 'auto',
              }}
            >
              {isSurface ? (
                <polygon
                  points={points
                    .map((point) => `${point.x},${point.y}`)
                    .join(' ')}
                  fill={alpha(
                    view === 'internal' ? color : theme.palette.primary.main,
                    selected
                      ? 0.18
                      : view === 'internal'
                        ? 0.12 + forceLevel * 0.22
                        : 0.06,
                  )}
                  stroke={selected ? theme.palette.primary.main : color}
                  strokeWidth={
                    selected ? 5 : denseSurfaceMesh || hideMeshNodes ? 1.4 : 3.2
                  }
                  strokeLinejoin="round"
                />
              ) : (
                <>
                  <line
                    x1={points[0].x}
                    y1={points[0].y}
                    x2={points[1].x}
                    y2={points[1].y}
                    stroke="transparent"
                    strokeWidth="18"
                  />
                  <line
                    x1={points[0].x}
                    y1={points[0].y}
                    x2={points[1].x}
                    y2={points[1].y}
                    stroke={selected ? theme.palette.primary.main : color}
                    strokeWidth={selected ? 5 : 3.2}
                    strokeLinecap="round"
                  />
                </>
              )}
              {showLabel && (
                <text
                  x={center.x}
                  y={center.y - 10}
                  textAnchor="middle"
                  fill="#394154"
                  fontSize="12"
                  fontWeight="600"
                >
                  {elementLabel}
                </text>
              )}
              {view === 'internal' && !isFrameDiagram && record && selected && (
                <text
                  x={center.x}
                  y={center.y + 16}
                  textAnchor="middle"
                  fill="#9a5a00"
                  fontSize="10"
                >
                  {elementInternalLabel(model.model_family, record)}
                </text>
              )}
            </g>
          )
        })}

        {!readOnly &&
          cadTool === 'add-member' &&
          pendingMember &&
          pointer &&
          nodeScreen.has(pendingMember) && (
            <line
              aria-label="Member preview"
              pointerEvents="none"
              x1={nodeScreen.get(pendingMember)!.x}
              y1={nodeScreen.get(pendingMember)!.y}
              x2={pointer.x}
              y2={pointer.y}
              stroke={theme.palette.primary.main}
              strokeWidth="2"
              strokeDasharray="7 5"
            />
          )}
        {isFrameDiagram && isFinalStep && (
          <FrameDiagramLayer
            model={model}
            diagrams={diagrams}
            quantity={quantity}
            positions={referenceScreen}
            selection={selection}
            onSelection={onSelection}
          />
        )}
        {!geometryOnly &&
          !isFrameDiagram &&
          distributedGlyphs.map((glyph) => (
            <g
              key={glyph.key}
              {...glyphProps(
                { kind: 'loads', id: glyph.loadId },
                `${loadDisplayLabel(model, glyph.loadId)} distributed ${glyph.key}`,
              )}
            >
              <line
                x1={glyph.x - glyph.dx}
                y1={glyph.y - glyph.dy}
                x2={glyph.x}
                y2={glyph.y}
                stroke="transparent"
                strokeWidth="14"
              />
              <line
                x1={glyph.x - glyph.dx}
                y1={glyph.y - glyph.dy}
                x2={glyph.x}
                y2={glyph.y}
                stroke="#d64e66"
                strokeWidth="2.2"
                markerEnd={`url(#${instanceId}-load-arrow)`}
              />
              {glyph.label && (
                <text
                  x={glyph.x + 7}
                  y={glyph.y - 7}
                  fill="#a42d43"
                  fontSize="10"
                >
                  {glyph.label} · distributed
                </text>
              )}
            </g>
          ))}

        {!hideFeNodes &&
          model.nodes.map((node) => {
            const point = nodeScreen.get(node.id)
            if (!point) return null
            const selected =
              selection.kind === 'nodes' && selection.id === node.id
            const selectNode = () => {
              if (readOnly) {
                onSelection({ kind: 'nodes', id: node.id })
                return
              }
              if (placement) {
                placeNode(node.id)
                return
              }
              if (cadTool === 'add-member') {
                if (!pendingMember) onPendingMember(node.id)
                else if (pendingMember !== node.id) {
                  const next = addFrameMember(model, pendingMember, node.id)
                  onModelChange(next, {
                    kind: 'elements',
                    id: next.elements.at(-1)?.id,
                  })
                  onPendingMember(null)
                }
                return
              }
              onSelection({ kind: 'nodes', id: node.id })
            }
            const nodeLabel = nodeDisplayLabel(model, node.id)
            return (
              <g key={node.id}>
                {renderSupportAndLoad(point, node.id)}
                <circle
                  cx={point.x}
                  cy={point.y}
                  r={
                    selected || pendingMember === node.id
                      ? 6
                      : denseSurfaceMesh
                        ? 2.5
                        : 4.5
                  }
                  fill={
                    selected ? '#ffffff' : theme.palette.background.container
                  }
                  stroke={theme.palette.primary.main}
                  strokeWidth={denseSurfaceMesh ? 1 : 2}
                  role="button"
                  tabIndex={0}
                  aria-label={`Select ${nodeLabel}`}
                  onKeyDown={(event) => activateOnKeyboard(event, selectNode)}
                  onPointerDown={(event) => {
                    event.stopPropagation()
                    if (panMode || event.button === 1 || event.altKey) {
                      beginDrag(event, 'pan')
                      return
                    }
                    if (
                      !readOnly &&
                      !isSurfaceFamily(model) &&
                      cadTool === 'select' &&
                      !placement
                    ) {
                      beginDrag(event, 'frame', node.id)
                    }
                  }}
                  onClick={(event) => {
                    event.stopPropagation()
                    if (skipClickRef.current) {
                      skipClickRef.current = false
                      return
                    }
                    if (!panMode) selectNode()
                  }}
                  style={{
                    cursor: readOnly
                      ? 'pointer'
                      : placement
                        ? 'copy'
                        : 'pointer',
                  }}
                />
                {(selected ||
                  (!denseSurfaceMesh && !hideMeshNodes) ||
                  constrainedNodes.has(node.id) ||
                  loadedNodes.has(node.id)) && (
                  <text
                    pointerEvents="none"
                    x={point.x + 10}
                    y={point.y - 8}
                    fill="#394154"
                    fontSize="11"
                    fontWeight="600"
                  >
                    {nodeLabel}
                  </text>
                )}
              </g>
            )
          })}

        {!readOnly &&
          cadTool !== 'draw-outline' &&
          isSurfaceFamily(model) &&
          sketch.loops.map((loop) => {
            const points =
              loop.shape?.kind === 'circle'
                ? shapePoints(loop.shape, 128).map((p) =>
                    project({ x: p[0], y: p[1] }),
                  )
                : (loop.vertexIds
                    .map((id) => {
                      const vertex = sketch.vertices.find(
                        (item) => item.id === id,
                      )
                      return vertex
                        ? project({
                            x: vertex.coordinates[0],
                            y: vertex.coordinates[1],
                          })
                        : null
                    })
                    .filter(Boolean) as Array<{ x: number; y: number }>)
            if (points.length < 2) return null
            return (
              <polygon
                key={loop.id}
                points={points
                  .map((point) => `${point.x},${point.y}`)
                  .join(' ')}
                fill={
                  loop.kind === 'hole'
                    ? CANVAS
                    : hideMeshNodes
                      ? alpha(theme.palette.primary.main, 0.04)
                      : 'none'
                }
                stroke={loop.kind === 'hole' ? '#b76a00' : '#1f3b73'}
                strokeWidth={loop.kind === 'hole' ? 2 : 2.8}
                strokeDasharray={loop.kind === 'hole' ? '7 5' : undefined}
                pointerEvents="none"
              />
            )
          })}

        {!readOnly &&
          cadTool !== 'draw-outline' &&
          isSurfaceFamily(model) &&
          sketch.vertices
            .filter(
              (vertex) =>
                !sketch.loops.some(
                  (loop) => loop.shape && loop.vertexIds.includes(vertex.id),
                ),
            )
            .map((vertex, index) => {
              const point = project({
                x: vertex.coordinates[0],
                y: vertex.coordinates[1],
              })
              const selected =
                selection.kind === 'geometry' && selection.id === vertex.id
              const node = nodeForSketchVertex(model, vertex)
              return (
                <g key={vertex.id}>
                  <circle
                    cx={point.x}
                    cy={point.y}
                    r={selected ? 8 : 6.5}
                    fill={selected ? '#fff4d6' : '#ffffff'}
                    stroke={selected ? '#b76a00' : '#1f3b73'}
                    strokeWidth={2.4}
                    role="button"
                    tabIndex={0}
                    aria-label={`Geometry vertex ${index + 1}`}
                    onKeyDown={(event) =>
                      activateOnKeyboard(event, () =>
                        placement
                          ? placeNode(node?.id)
                          : onSelection({ kind: 'geometry', id: vertex.id }),
                      )
                    }
                    style={{
                      cursor: placement ? 'copy' : 'grab',
                      pointerEvents: cadTool !== 'select' ? 'none' : 'auto',
                    }}
                    onPointerDown={(event) => {
                      event.stopPropagation()
                      if (panMode || event.button === 1 || event.altKey) {
                        beginDrag(event, 'pan')
                        return
                      }
                      if (readOnly || placement || cadTool !== 'select') return
                      beginDrag(event, 'sketch', vertex.id)
                    }}
                    onClick={(event) => {
                      event.stopPropagation()
                      if (skipClickRef.current) {
                        skipClickRef.current = false
                        return
                      }
                      if (panMode) return
                      if (readOnly) {
                        onSelection({ kind: 'geometry', id: vertex.id })
                        return
                      }
                      if (placement) {
                        placeNode(node?.id)
                        return
                      }
                      onSelection({ kind: 'geometry', id: vertex.id })
                    }}
                  />
                  <text
                    x={point.x - 12}
                    y={point.y - 13}
                    textAnchor="end"
                    fill="#1f3b73"
                    fontSize="11"
                    fontWeight="700"
                  >
                    V{index + 1}
                  </text>
                </g>
              )
            })}

        {!readOnly && cadTool === 'draw-outline' && (
          <g aria-label="Outline preview">
            <polyline
              points={[
                ...outlinePoints.map((p) => project({ x: p[0], y: p[1] })),
                ...(pointer ? [pointer] : []),
              ]
                .map((p) => `${p.x},${p.y}`)
                .join(' ')}
              fill="none"
              stroke={theme.palette.primary.main}
              strokeWidth="2"
              strokeDasharray="6 4"
              pointerEvents="none"
            />
            {outlinePoints.map((p, i) => {
              const screen = project({ x: p[0], y: p[1] })
              return (
                <g key={i} pointerEvents="none">
                  <circle
                    cx={screen.x}
                    cy={screen.y}
                    r={i === 0 ? 7 : 4}
                    fill={theme.palette.background.paper}
                    stroke={theme.palette.primary.main}
                    strokeWidth="2"
                  />
                  <text
                    x={screen.x + 9}
                    y={screen.y - 8}
                    fill={theme.palette.text.primary}
                    fontSize="11"
                  >
                    {i + 1}
                  </text>
                </g>
              )
            })}
          </g>
        )}
        {!readOnly &&
          cadTool === 'select' &&
          !placement &&
          sketch.loops
            .filter((loop) => loop.shape)
            .map((loop, i) => {
              const point = project({
                x: loop.shape!.center[0],
                y: loop.shape!.center[1],
              })
              return (
                <g
                  key={loop.id}
                  {...glyphProps(
                    { kind: 'geometry', id: loop.id },
                    `Hole ${i + 1} on canvas`,
                  )}
                >
                  <circle
                    cx={point.x}
                    cy={point.y}
                    r="9"
                    fill={theme.palette.background.paper}
                    stroke={theme.palette.primary.main}
                  />
                  <path
                    d={`M ${point.x - 5} ${point.y} h 10 M ${point.x} ${point.y - 5} v 10`}
                    stroke={theme.palette.primary.main}
                  />
                </g>
              )
            })}
        {view === 'reactions' &&
          model.nodes.map((node) => {
            if (!constrainedNodes.has(node.id)) return null
            const point = nodeScreen.get(node.id)
            const reaction = reactions.get(node.id)
            if (!point || !reaction) return null
            const arrows = TRANSLATIONAL_DOFS.filter((dof) =>
              dofs.includes(dof),
            )
              .map((dof) => {
                const value = Number(reaction[dof] ?? 0)
                if (dof === 'UX')
                  return { dof, value, dx: (58 * value) / maxReaction, dy: 0 }
                if (dof === 'UY')
                  return { dof, value, dx: 0, dy: (-58 * value) / maxReaction }
                return {
                  dof,
                  value,
                  dx: (40 * value) / maxReaction,
                  dy: (-40 * value) / maxReaction,
                }
              })
              .filter((item) => Math.abs(item.value) > maxReaction * 1e-9)
            const moments = dofs.filter(
              (dof) =>
                dof.startsWith('R') &&
                Math.abs(Number(reaction[dof] ?? 0)) > maxReaction * 1e-9,
            )
            return (
              <g key={`reaction-${node.id}`}>
                {arrows.map((arrow) => (
                  <g key={arrow.dof}>
                    <line
                      x1={point.x}
                      y1={point.y}
                      x2={point.x + arrow.dx}
                      y2={point.y + arrow.dy}
                      stroke={theme.palette.secondary.main}
                      strokeWidth="2.5"
                      markerEnd={`url(#${instanceId}-reaction-arrow)`}
                    />
                    <text
                      x={point.x + arrow.dx + 6}
                      y={point.y + arrow.dy - 5}
                      fill={theme.palette.secondary.dark}
                      fontSize="10"
                    >
                      {arrow.dof} {formatNumber(arrow.value)}
                    </text>
                  </g>
                ))}
                {moments.length > 0 && (
                  <text
                    x={point.x + 12}
                    y={point.y + 35}
                    fill={theme.palette.secondary.dark}
                    fontSize="10"
                  >
                    {moments
                      .map((dof) => `${dof} ${formatNumber(reaction[dof])}`)
                      .join(' · ')}
                  </text>
                )}
              </g>
            )
          })}
      </svg>
      <Box
        sx={{
          position: 'absolute',
          left: 16,
          bottom: 22,
          right: 205,
          pointerEvents: 'none',
          display: 'flex',
          gap: 1.5,
          flexWrap: 'wrap',
        }}
      >
        <Typography variant="caption" color="text.secondary">
          X → Y ↑
        </Typography>
        {hasOutOfPlane && (
          <Typography variant="caption" color="text.secondary">
            UZ ↗
          </Typography>
        )}
        <Typography variant="caption" color="text.secondary">
          {model.units.length} · {model.units.force}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Grid {formatNumber(gridSize)} {model.units.length}
        </Typography>
      </Box>
    </Box>
  )
}
