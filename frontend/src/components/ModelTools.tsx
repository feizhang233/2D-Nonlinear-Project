import NearMeOutlinedIcon from '@mui/icons-material/NearMeOutlined'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import PolylineRoundedIcon from '@mui/icons-material/PolylineRounded'
import { Button, Divider, Stack } from '@mui/material'
import type { ModelInput, Selection } from '../domain'
import {
  geometryNeedsMesh,
  type CadTool,
  type PlacementState,
} from '../geometrySketch'

export function ModelTools({
  model,
  tool,
  placement,
  onTool,
  onSelection,
  onPlace,
}: {
  model: ModelInput
  tool: CadTool
  placement: PlacementState
  onTool: (tool: CadTool) => void
  onSelection: (selection: Selection) => void
  onPlace: (placement: PlacementState) => void
}) {
  const frame = model.model_family === 'frame'
  const selected = (value: CadTool) => !placement && tool === value
  return (
    <Stack
      component="nav"
      aria-label="Model operations"
      direction="row"
      spacing={0.5}
      sx={{
        alignItems: 'center',
        flex: 1,
        '& .MuiButton-root': {
          color: 'text.secondary',
          px: 1,
          minWidth: 0,
          fontSize: 12,
          '&[aria-pressed=true]': {
            color: 'primary.main',
            bgcolor: 'action.selected',
          },
        },
      }}
    >
      <Button
        size="small"
        startIcon={<NearMeOutlinedIcon />}
        aria-pressed={selected('select')}
        onClick={() => onTool('select')}
      >
        Select
      </Button>
      <Button
        size="small"
        startIcon={<AddRoundedIcon />}
        aria-pressed={selected(frame ? 'add-node' : 'draw-outline')}
        onClick={() => onTool(frame ? 'add-node' : 'draw-outline')}
      >
        {frame ? 'Node' : 'Outline'}
      </Button>
      <Button
        size="small"
        startIcon={<PolylineRoundedIcon />}
        aria-pressed={selected(frame ? 'add-member' : 'add-hole')}
        disabled={frame && !model.materials.length}
        onClick={() => onTool(frame ? 'add-member' : 'add-hole')}
      >
        {frame ? 'Member' : 'Hole'}
      </Button>
      <Divider orientation="vertical" flexItem sx={{ mx: 0.5, my: 0.75 }} />
      <Button
        size="small"
        aria-pressed={placement?.kind === 'support'}
        disabled={!model.nodes.length || geometryNeedsMesh(model)}
        onClick={() => {
          onSelection({ kind: 'constraints' })
          onPlace({ kind: 'support' })
        }}
      >
        Support
      </Button>
      <Button
        size="small"
        aria-pressed={placement?.kind === 'load'}
        disabled={!model.nodes.length || geometryNeedsMesh(model)}
        onClick={() => {
          onSelection({ kind: 'loads' })
          onPlace({ kind: 'load' })
        }}
      >
        Load
      </Button>
    </Stack>
  )
}
