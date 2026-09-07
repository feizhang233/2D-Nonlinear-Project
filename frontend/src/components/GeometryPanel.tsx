import { Alert, Box, Button, Stack, Typography } from '@mui/material'
import type { ModelInput, Selection } from '../domain'
import {
  type CadTool,
  geometryNeedsMesh,
  getSketch,
  isSurfaceFamily,
} from '../geometrySketch'
import {
  type HoleDimensions,
  defaultHoleDimensions,
  holeDimensionError,
} from '../cadGeometry'
import { HoleFields } from './HoleFields'

export function GeometryPanel({
  model,
  selection,
  cadTool,
  onCadToolChange,
  onSelection,
  holeDimensions = defaultHoleDimensions,
  onHoleDimensionsChange,
}: {
  model: ModelInput
  selection: Selection
  cadTool: CadTool
  onCadToolChange: (tool: CadTool) => void
  onSelection: (selection: Selection) => void
  onModelChange: (model: ModelInput, selection?: Selection) => void
  holeDimensions?: HoleDimensions
  onHoleDimensionsChange?: (value: HoleDimensions) => void
}) {
  const sketch = getSketch(model)
  if (!isSurfaceFamily(model))
    return (
      <Typography variant="caption" sx={{ p: 2 }}>
        Use Node or Member to draw directly on the canvas.
      </Typography>
    )
  const holes = sketch.loops.filter((loop) => loop.kind === 'hole')
  return (
    <Stack spacing={1.5} sx={{ p: 1.5 }}>
      <Typography variant="subtitle2">Outline & holes</Typography>
      <Button
        variant={cadTool === 'draw-outline' ? 'contained' : 'outlined'}
        onClick={() => onCadToolChange('draw-outline')}
      >
        Draw outline
      </Button>
      <Button
        variant={cadTool === 'add-vertex' ? 'contained' : 'text'}
        onClick={() => onCadToolChange('add-vertex')}
      >
        Insert vertex
      </Button>
      {cadTool === 'draw-outline' && (
        <Typography variant="caption" color="text.secondary">
          Click corners, then close the outline. A new outline replaces the
          previous contour, holes, supports and loads. Cancel restores the
          model.
        </Typography>
      )}
      <Button
        variant={cadTool === 'add-hole' ? 'contained' : 'outlined'}
        onClick={() => onCadToolChange('add-hole')}
      >
        Add hole
      </Button>
      {cadTool === 'add-hole' && (
        <>
          <HoleFields
            value={holeDimensions}
            onChange={(value) => onHoleDimensionsChange?.(value)}
          />
          <Typography variant="caption" color="text.secondary">
            Dimensions in {model.units.length}. Click the canvas to place the
            center.
          </Typography>
          {holeDimensionError(holeDimensions) && (
            <Alert severity="error">{holeDimensionError(holeDimensions)}</Alert>
          )}
        </>
      )}
      {holes.map((hole, i) => (
        <Button
          key={hole.id}
          variant={selection.id === hole.id ? 'contained' : 'text'}
          onClick={() =>
            onSelection({
              kind: 'geometry',
              id: hole.shape ? hole.id : hole.vertexIds[0],
            })
          }
        >
          Hole {i + 1} · {hole.shape?.kind ?? 'polygon'}
        </Button>
      ))}
      <Box>
        <Typography variant="caption" color="text.secondary">
          Select a vertex to edit X / Y. Select a hole to edit its center and
          dimensions.
        </Typography>
      </Box>
      {geometryNeedsMesh(model) && (
        <Alert severity="warning">
          Generate a mesh after geometry changes.
        </Alert>
      )}
      {cadTool !== 'select' && (
        <Button onClick={() => onCadToolChange('select')}>Stop drawing</Button>
      )}
    </Stack>
  )
}
