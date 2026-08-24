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
    <Box
      aria-label="Modeling workflow progress"
      sx={{
        bgcolor: 'background.paper',
        borderBottom: '1px solid',
        borderColor: 'divider',
        px: 2,
        py: expanded ? 1.25 : 0.75,
      }}
    >
      <Stack direction="row" sx={{ alignItems: 'center', gap: 2 }}>
        <Box sx={{ width: 138, flexShrink: 0 }}>
          <Typography variant="overline" color="text.secondary">Workflow</Typography>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>{completedCount} of 6 complete</Typography>
        </Box>

        {expanded && (
          <Stack
            component="ol"
            direction="row"
            sx={{
              flex: 1,
              minWidth: 0,
              alignItems: 'stretch',
              listStyle: 'none',
              p: 0,
              m: 0,
            }}
          >
            {STEP_COPY.map((step, index) => {
              const isComplete = complete[step.key]
              const isActive = activeStep === step.key
              const isNext = nextStep === step.key
              return (
                <Box
                  component="li"
                  key={step.key}
                  sx={{
                    position: 'relative',
                    flex: 1,
                    minWidth: 0,
                    '&:not(:last-of-type)::after': {
                      content: '""',
                      position: 'absolute',
                      top: 15,
                      left: 'calc(50% + 22px)',
                      right: 'calc(-50% + 22px)',
                      height: 2,
                      bgcolor: isComplete ? 'primary.main' : 'divider',
                    },
                  }}
                >
                  <Box
                    component="button"
                    type="button"
                    aria-current={isActive ? 'step' : undefined}
                    onClick={() => onStepChange(step.key)}
                    sx={{
                      position: 'relative',
                      zIndex: 1,
                      width: '100%',
                      minHeight: 62,
                      border: 0,
                      borderRadius: 2.5,
                      bgcolor: isActive ? 'action.selected' : 'transparent',
                      color: 'text.primary',
                      font: 'inherit',
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: 0.25,
                      px: 0.75,
                      py: 0.25,
                      '&:hover': { bgcolor: isActive ? 'action.selected' : 'action.hover' },
                      '&:focus-visible': {
                        outline: '3px solid',
                        outlineColor: 'primary.light',
                        outlineOffset: 2,
                      },
                    }}
                  >
                    <Box
                      sx={{
                        width: 30,
                        height: 30,
                        borderRadius: '50%',
                        display: 'grid',
                        placeItems: 'center',
                        bgcolor: isComplete || isNext ? 'primary.main' : 'background.containerHigh',
                        color: isComplete || isNext ? 'primary.contrastText' : 'text.secondary',
                        border: isActive ? '3px solid' : '1px solid',
                        borderColor: isActive ? 'primary.light' : 'divider',
                        fontWeight: 700,
                        fontSize: 12,
                      }}
                    >
                      {isComplete ? <CheckRoundedIcon sx={{ fontSize: 18 }} /> : index + 1}
                    </Box>
                    <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center', minWidth: 0 }}>
                      <Typography variant="caption" noWrap sx={{ fontWeight: isActive ? 700 : 600 }}>
                        {step.label}
                      </Typography>
                      {isNext && <Chip label="Next" size="small" color="primary" sx={{ height: 18, '& .MuiChip-label': { px: 0.75, fontSize: 10 } }} />}
                    </Stack>
                    <Typography variant="caption" color="text.secondary" noWrap sx={{ maxWidth: '100%', fontSize: 10 }}>
                      {step.helper}
                    </Typography>
                  </Box>
                </Box>
              )
            })}
          </Stack>
        )}

        {!expanded && (
          <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
            {nextStep ? `Next: ${STEP_COPY.find((step) => step.key === nextStep)?.label}` : 'Workflow complete'}
          </Typography>
        )}

        <Tooltip title={expanded ? 'Hide workflow' : 'Show workflow'}>
          <IconButton
            size="small"
            aria-label={expanded ? 'Hide workflow' : 'Show workflow'}
            aria-expanded={expanded}
            onClick={() => onExpandedChange(!expanded)}
          >
            {expanded ? <ExpandLessRoundedIcon /> : <ExpandMoreRoundedIcon />}
          </IconButton>
        </Tooltip>
      </Stack>
    </Box>
  )
}
