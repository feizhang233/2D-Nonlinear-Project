import CheckRoundedIcon from '@mui/icons-material/CheckRounded'
import ExpandLessRoundedIcon from '@mui/icons-material/ExpandLessRounded'
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import IconButton from '@mui/material/IconButton'
import Stack from '@mui/material/Stack'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import type { ModelInput } from '../domain'
import { meshStatusForModel } from '../meshing'

export type WorkflowStep = 'model' | 'materials' | 'supports' | 'loads' | 'mesh' | 'solve'

interface WorkflowBarProps {
  model: ModelInput
  analysisState: 'idle' | 'validating' | 'running' | 'succeeded' | 'failed'
  activeStep: WorkflowStep
  expanded: boolean
  onStepChange: (step: WorkflowStep) => void
  onExpandedChange: (expanded: boolean) => void
}

const STEP_COPY: Array<{ key: WorkflowStep; label: string; helper: string }> = [
  { key: 'model', label: 'Model', helper: 'Family and CAD geometry' },
  { key: 'materials', label: 'Materials', helper: 'Constitutive data' },
  { key: 'supports', label: 'Supports', helper: 'Boundary conditions' },
  { key: 'loads', label: 'Loads', helper: 'Reference loading' },
  { key: 'mesh', label: 'Mesh', helper: 'Topology and Gmsh' },
  { key: 'solve', label: 'Solve', helper: 'Controls and results' },
]

export function WorkflowBar({
  model,
  analysisState,
  activeStep,
  expanded,
  onStepChange,
  onExpandedChange,
}: WorkflowBarProps) {
  const meshStatus = meshStatusForModel(model)
  const complete: Record<WorkflowStep, boolean> = {
    model: model.nodes.length > 0 && model.elements.length > 0,
    materials: model.materials.length > 0,
    supports: model.constraints.length > 0,
    loads: model.loads.length > 0,
    mesh: model.model_family === 'frame'
      ? model.elements.length > 0
      : meshStatus.generatedByGmsh,
    solve: analysisState === 'succeeded',
  }
  const completedCount = STEP_COPY.filter((step) => complete[step.key]).length
  const nextStep = STEP_COPY.find((step) => !complete[step.key])?.key ?? null

  return (
    <Box aria-label="Modeling workflow progress" sx={{ bgcolor: 'background.paper', borderBottom: '1px solid', borderColor: 'divider', px: 2, py: 0.75 }}>
      <Stack direction="row" sx={{ alignItems: 'center', gap: 2 }}>
        <Box sx={{ width: 208, flexShrink: 0 }}>
          <Typography variant="overline" color="text.secondary" sx={{ mr: 1 }}>Workflow</Typography>
          <Typography component="span" variant="caption" sx={{ fontWeight: 600 }}>{completedCount} of 6 complete</Typography>
        </Box>
        {expanded ? (
          <Stack component="ol" direction="row" sx={{ flex: 1, minWidth: 0, listStyle: 'none', p: 0, m: 0, gap: 0.5 }}>
            {STEP_COPY.map((step, index) => (
              <Box component="li" key={step.key} sx={{ flex: 1, minWidth: 0 }}>
                <Tooltip title={step.helper}>
                  <Box component="button" type="button" aria-label={step.label} aria-current={activeStep === step.key ? 'step' : undefined} onClick={() => onStepChange(step.key)} sx={{ width: '100%', height: 34, border: 0, borderRadius: 1, px: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.75, font: 'inherit', color: activeStep === step.key ? 'primary.main' : 'text.secondary', bgcolor: activeStep === step.key ? 'action.selected' : 'transparent', cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' }, '&:focus-visible': { outline: '2px solid', outlineColor: 'primary.main' } }}>
                    <Box component="span" sx={{ width: 20, height: 20, borderRadius: 0.75, display: 'grid', placeItems: 'center', bgcolor: complete[step.key] ? 'background.container' : 'background.containerLow', color: complete[step.key] ? 'primary.main' : 'text.secondary', fontSize: 10, fontWeight: 700 }}>
                      {complete[step.key] ? <CheckRoundedIcon sx={{ fontSize: 14 }} /> : index + 1}
                    </Box>
                    <Typography component="span" variant="caption" sx={{ fontWeight: activeStep === step.key ? 700 : 500 }}>{step.label}</Typography>
                    {nextStep === step.key && <Chip label="Next" size="small" variant="outlined" sx={{ height: 18, '& .MuiChip-label': { px: 0.5, fontSize: 9 } }} />}
                  </Box>
                </Tooltip>
              </Box>
            ))}
          </Stack>
        ) : <Typography variant="caption" color="text.secondary" sx={{ flex: 1 }}>{nextStep ? `Next: ${STEP_COPY.find((step) => step.key === nextStep)?.label}` : 'Workflow complete'}</Typography>}
        <Tooltip title={expanded ? 'Hide workflow' : 'Show workflow'}>
          <IconButton size="small" aria-label={expanded ? 'Hide workflow' : 'Show workflow'} aria-expanded={expanded} onClick={() => onExpandedChange(!expanded)}>{expanded ? <ExpandLessRoundedIcon /> : <ExpandMoreRoundedIcon />}</IconButton>
        </Tooltip>
      </Stack>
    </Box>
  )
}
