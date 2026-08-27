import CloseRoundedIcon from '@mui/icons-material/CloseRounded'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import IconButton from '@mui/material/IconButton'
import Stack from '@mui/material/Stack'
import Step from '@mui/material/Step'
import StepContent from '@mui/material/StepContent'
import StepLabel from '@mui/material/StepLabel'
import Stepper from '@mui/material/Stepper'
import Typography from '@mui/material/Typography'
import { useState } from 'react'
import type { ModelFamily } from '../domain'
import { MODEL_FAMILIES, MODEL_FAMILY_ORDER } from '../modelFamilies'
import type { WorkflowStep } from './WorkflowBar'

interface GettingStartedDialogProps {
  open: boolean
  currentFamily: ModelFamily
  onClose: () => void
  onDoNotShowAgain: () => void
  onOpenStep: (step: WorkflowStep) => void
  onChooseFamily: (family: ModelFamily) => void
}

const steps: Array<{ title: string; body: string; workflow: WorkflowStep }> = [
  { title: 'Choose a model workspace', body: 'Frame, Continuum, Plate, and Shell keep separate working documents. Move between them from the workspace bar without merging their models.', workflow: 'model' },
  { title: 'Review geometry and topology', body: 'Use the model tree and Properties form as the primary entry points. The canvas provides direct geometry editing when graphical placement is useful.', workflow: 'model' },
  { title: 'Define materials and supports', body: 'Check constitutive parameters. Add a support from Properties, then click a geometry vertex or choose it from the location list.', workflow: 'materials' },
  { title: 'Apply loads', body: 'Add a load from Properties, then use a form location or the canvas. All form and canvas edits remain staged until you choose Apply changes.', workflow: 'loads' },
  { title: 'Prepare the mesh', body: 'Frame uses explicit line elements. Surface workspaces generate an all-Q4 Gmsh mesh; its nodes and elements remain visible but read-only.', workflow: 'mesh' },
  { title: 'Run and inspect the analysis', body: 'Apply staged edits, choose the nonlinear control method, then run the solve. Monitoring, curves, tables, and failure evidence open in the separate Results mode.', workflow: 'solve' },
]

export function GettingStartedDialog({
  open,
  currentFamily,
  onClose,
  onDoNotShowAgain,
  onOpenStep,
  onChooseFamily,
}: GettingStartedDialogProps) {
  const [activeStep, setActiveStep] = useState(0)
  const isLast = activeStep === steps.length - 1

  const close = () => {
    setActiveStep(0)
    onClose()
  }

  const pickFamily = (family: ModelFamily) => {
    onChooseFamily(family)
    setActiveStep(1)
  }

  return (
    <Dialog
      open={open}
      onClose={close}
      fullWidth
      maxWidth="sm"
      aria-labelledby="getting-started-title"
    >
      <DialogTitle id="getting-started-title" sx={{ pr: 7 }}>Getting started with Nonlinear Studio</DialogTitle>
      <IconButton aria-label="Close guide" onClick={close} sx={{ position: 'absolute', right: 12, top: 12 }}>
        <CloseRoundedIcon />
      </IconButton>
      <DialogContent dividers sx={{ py: 2 }}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Build a nonlinear FEM model in six guided steps. The first step is selectable: choose Frame, Continuum, Plate, or Shell.
        </Typography>
        <Stepper activeStep={activeStep} orientation="vertical">
          {steps.map((item, index) => (
            <Step key={item.title} completed={index < activeStep}>
              <StepLabel>{item.title}</StepLabel>
              <StepContent>
                <Typography variant="body2" color="text.secondary">{item.body}</Typography>
                {index === 0 && (
                  <Stack spacing={1} sx={{ mt: 1.5 }}>
                    {MODEL_FAMILY_ORDER.map((family) => {
                      const selected = family === currentFamily
                      return (
                        <Button
                          key={family}
                          type="button"
                          fullWidth
                          variant={selected ? 'contained' : 'outlined'}
                          aria-label={`Use ${MODEL_FAMILIES[family].label} example`}
                          aria-pressed={selected}
                          onClick={() => pickFamily(family)}
                          sx={{ justifyContent: 'flex-start', textAlign: 'left', py: 1.25, px: 1.5 }}
                        >
                          <Box>
                            <Typography variant="body2" sx={{ fontWeight: 700, color: 'inherit' }}>
                              {MODEL_FAMILIES[family].label}
                              {selected ? ' · current' : ''}
                            </Typography>
                            <Typography
                              variant="caption"
                              sx={{
                                display: 'block',
                                whiteSpace: 'normal',
                                color: selected ? 'inherit' : 'text.secondary',
                                opacity: selected ? 0.92 : 1,
                              }}
                            >
                              {MODEL_FAMILIES[family].capability}
                            </Typography>
                          </Box>
                        </Button>
                      )
                    })}
                  </Stack>
                )}
                <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
                  <Button size="small" variant="contained" onClick={() => (isLast ? close() : setActiveStep((value) => value + 1))}>
                    {isLast ? 'Finish' : index === 0 ? 'Keep this family' : 'Continue'}
                  </Button>
                  <Button size="small" onClick={() => { onOpenStep(item.workflow); close() }}>Open this step</Button>
                  <Button size="small" disabled={activeStep === 0} onClick={() => setActiveStep((value) => Math.max(0, value - 1))}>
                    Back
                  </Button>
                </Stack>
              </StepContent>
            </Step>
          ))}
        </Stepper>
      </DialogContent>
      <DialogActions sx={{ justifyContent: 'space-between', px: 3 }}>
        <Button color="inherit" onClick={() => { setActiveStep(0); onDoNotShowAgain() }}>Don't show again</Button>
        <Typography variant="caption" color="text.secondary">Step {activeStep + 1} of {steps.length}</Typography>
      </DialogActions>
    </Dialog>
  )
}
