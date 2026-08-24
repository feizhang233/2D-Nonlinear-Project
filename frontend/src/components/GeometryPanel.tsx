import AddRoundedIcon from '@mui/icons-material/AddRounded'
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded'
import PolylineRoundedIcon from '@mui/icons-material/PolylineRounded'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import IconButton from '@mui/material/IconButton'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import type { ModelInput, Selection } from '../domain'
import {
  addFrameMember,
  addFrameNode,
  addOuterVertex,
  addRectangularHole,
  CadTool,
  deleteSketchLoop,
  deleteSketchVertex,
  geometryNeedsMesh,
  geometryNeedsRemesh,
  getSketch,
  isSurfaceFamily,
  moveSketchVertex,
} from '../geometrySketch'
import { SectionHeader } from './chrome'

interface GeometryPanelProps {
  model: ModelInput
  selection: Selection
  cadTool: CadTool
  onCadToolChange: (tool: CadTool) => void
  onSelection: (selection: Selection) => void
  onModelChange: (model: ModelInput, selection?: Selection) => void
}

export function GeometryPanel({
  model,
  selection,
  cadTool,
  onCadToolChange,
  onSelection,
  onModelChange,
}: GeometryPanelProps) {
  const sketch = getSketch(model)
  const outer = sketch.loops.find((loop) => loop.kind === 'outer')
  const holes = sketch.loops.filter((loop) => loop.kind === 'hole')
  const selectedId = selection.kind === 'geometry' ? selection.id : undefined
  const surface = isSurfaceFamily(model)
  const dirty = geometryNeedsMesh(model)

  const tools: Array<{ id: CadTool; label: string }> = surface
    ? [
        { id: 'select', label: 'Select' },
        { id: 'add-vertex', label: 'Add vertex' },
        { id: 'add-hole', label: 'Add hole' },
      ]
    : [
        { id: 'select', label: 'Select' },
        { id: 'add-node', label: 'Add node' },
        { id: 'add-member', label: 'Add member' },
      ]

  return (
    <Box sx={{ borderBottom: '1px solid', borderColor: 'divider', p: 1.25, display: 'flex', flexDirection: 'column', gap: 1, minHeight: 0, maxHeight: '46%' }}>
      <SectionHeader
        icon={<PolylineRoundedIcon fontSize="small" />}
        title="Geometry"
        subtitle={surface ? 'Editable contour and holes' : 'Frame nodes and members'}
      />
      <ToggleButtonGroup
        exclusive
        size="small"
        fullWidth
        value={cadTool}
        onChange={(_, value: CadTool | null) => value && onCadToolChange(value)}
        aria-label="Geometry tools"
      >
        {tools.map((tool) => (
          <ToggleButton key={tool.id} value={tool.id} sx={{ fontSize: 11, px: 0.5 }}>
            {tool.label}
          </ToggleButton>
        ))}
      </ToggleButtonGroup>
      {dirty && (
        <Alert severity="warning" sx={{ py: 0.25 }}>
          {geometryNeedsRemesh(model)
            ? 'Geometry changed. Generate a new mesh before solving.'
            : 'This contour needs a Gmsh mesh before it can be solved.'}
        </Alert>
      )}
      {surface ? (
        <Box sx={{ overflow: 'auto', minHeight: 0 }}>
          <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>Outer contour</Typography>
          {outer?.vertexIds.map((id, index) => {
            const vertex = sketch.vertices.find((item) => item.id === id)
            if (!vertex) return null
            const selected = selectedId === id
            return (
              <Stack key={id} direction="row" spacing={0.5} sx={{ alignItems: 'center', mt: 0.5 }}>
                <Button
                  size="small"
                  variant={selected ? 'contained' : 'text'}
                  onClick={() => onSelection({ kind: 'geometry', id })}
                  sx={{ minWidth: 36, px: 0.5 }}
                >
                  {index + 1}
                </Button>
                <TextField
                  size="small"
                  label="X"
                  type="number"
                  value={vertex.coordinates[0]}
                  onFocus={() => onSelection({ kind: 'geometry', id })}
                  onChange={(event) => onModelChange(moveSketchVertex(model, id, [Number(event.target.value), vertex.coordinates[1], ...vertex.coordinates.slice(2)]))}
                  sx={{ flex: 1 }}
                />
                <TextField
                  size="small"
                  label="Y"
                  type="number"
                  value={vertex.coordinates[1]}
                  onFocus={() => onSelection({ kind: 'geometry', id })}
                  onChange={(event) => onModelChange(moveSketchVertex(model, id, [vertex.coordinates[0], Number(event.target.value), ...vertex.coordinates.slice(2)]))}
                  sx={{ flex: 1 }}
                />
                <Tooltip title="Delete vertex">
                  <span>
                    <IconButton
                      size="small"
                      aria-label={`Delete vertex ${index + 1}`}
                      disabled={(outer?.vertexIds.length ?? 0) <= 3}
                      onClick={() => onModelChange(deleteSketchVertex(model, id))}
                    >
                      <DeleteOutlineRoundedIcon fontSize="small" />
                    </IconButton>
                  </span>
                </Tooltip>
              </Stack>
            )
          })}
          <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
            <Button
              size="small"
              startIcon={<AddRoundedIcon />}
              onClick={() => {
                const last = sketch.vertices.at(-1)?.coordinates ?? [0, 0]
                onModelChange(addOuterVertex(model, [last[0] + 0.25, last[1]]))
              }}
            >
              Vertex
            </Button>
            <Button
              size="small"
              startIcon={<AddRoundedIcon />}
              onClick={() => {
                const xs = sketch.vertices.map((vertex) => vertex.coordinates[0])
                const ys = sketch.vertices.map((vertex) => vertex.coordinates[1])
                const width = Math.max(...xs) - Math.min(...xs)
                const height = Math.max(...ys) - Math.min(...ys)
                onModelChange(addRectangularHole(model, [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2], Math.min(width, height) * 0.28))
              }}
            >
              Hole
            </Button>
          </Stack>
          {holes.map((hole, holeIndex) => (
            <Box key={hole.id} sx={{ mt: 1.25 }}>
              <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
                <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>Hole {holeIndex + 1}</Typography>
                <IconButton size="small" aria-label={`Delete hole ${holeIndex + 1}`} onClick={() => onModelChange(deleteSketchLoop(model, hole.id))}>
                  <DeleteOutlineRoundedIcon fontSize="small" />
                </IconButton>
              </Stack>
              {hole.vertexIds.map((id, index) => {
                const vertex = sketch.vertices.find((item) => item.id === id)
                if (!vertex) return null
                return (
                  <Stack key={id} direction="row" spacing={0.5} sx={{ alignItems: 'center', mt: 0.5 }}>
                    <Typography variant="caption" sx={{ width: 28 }}>{index + 1}</Typography>
                    <TextField size="small" label="X" type="number" value={vertex.coordinates[0]} onChange={(event) => onModelChange(moveSketchVertex(model, id, [Number(event.target.value), vertex.coordinates[1]]))} sx={{ flex: 1 }} />
                    <TextField size="small" label="Y" type="number" value={vertex.coordinates[1]} onChange={(event) => onModelChange(moveSketchVertex(model, id, [vertex.coordinates[0], Number(event.target.value)]))} sx={{ flex: 1 }} />
                  </Stack>
                )
              })}
            </Box>
          ))}
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
            Drag vertices on the canvas, or click in Add vertex / Add hole mode.
          </Typography>
        </Box>
      ) : (
        <Stack spacing={1}>
          <Typography variant="caption" color="text.secondary">
            Drag nodes on the canvas. Use the tools above, or add from here.
          </Typography>
          <Stack direction="row" spacing={1}>
            <Button
              size="small"
              startIcon={<AddRoundedIcon />}
              onClick={() => {
                const last = model.nodes.at(-1)?.coordinates ?? [0, 0]
                const added = addFrameNode(model, [last[0] + 0.25, last[1]])
                onModelChange(added.model, { kind: 'nodes', id: added.nodeId })
              }}
            >
              Node
            </Button>
            <Button
              size="small"
              startIcon={<AddRoundedIcon />}
              disabled={model.nodes.length < 2}
              onClick={() => {
                const start = model.nodes.at(-2)?.id
                const end = model.nodes.at(-1)?.id
                if (start && end) onModelChange(addFrameMember(model, start, end), { kind: 'elements' })
              }}
            >
              Member
            </Button>
          </Stack>
        </Stack>
      )}
    </Box>
  )
}
