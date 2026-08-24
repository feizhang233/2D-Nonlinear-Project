import CloseRoundedIcon from '@mui/icons-material/CloseRounded'
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
import type { WorkflowStep } from './WorkflowBar'

interface GettingStartedDialogProps {
  open: boolean
  onClose: () => void
  onDoNotShowAgain: () => void
  onOpenStep: (step: WorkflowStep) => void
}

const steps: Array<{ title: string; body: string; workflow: WorkflowStep }> = [
  { title: 'Choose the model family', body: 'Select Frame, Continuum, Plate, or Shell. Loading a family replaces the complete working model.', workflow: 'model' },
  { title: 'Review geometry and topology', body: 'Open Nodes and Elements. Select once to edit Properties; double-click an item when you want more canvas space.', workflow: 'model' },
  { title: 'Define materials and supports', body: 'Check constitutive parameters and boundary conditions before applying reference loads.', workflow: 'materials' },
  { title: 'Apply loads', body: 'Add concentrated or distributed loading and verify its direction, target, and units.', workflow: 'loads' },
  { title: 'Prepare the mesh', body: 'Frame uses explicit line elements. Continuum, Plate, and Shell can generate an all-Q4 Gmsh mesh.', workflow: 'mesh' },
  { title: 'Run and inspect the analysis', body: 'Choose the nonlinear control method, run the solve, then review committed steps, convergence, tables, and failure evidence.', workflow: 'solve' },
]

export function GettingStartedDialog({ open, onClose, onDoNotShowAgain, onOpenStep }: GettingStartedDialogProps) {
  const [activeStep, setActiveStep] = useState(0)
  const step = steps[activeStep]
  const isLast = activeStep === steps.length - 1

  const close = () => {
    setActiveStep(0)
    onClose()
  }

  return (
    <Dialog open={open} onClose={close} fullWidth maxWidth="sm" aria-labelledby="getting-started-title">
      <DialogTitle id="getting-started-title" sx={{ pr: 7 }}>Getting started with Nonlinear Studio</DialogTitle>
      <IconButton aria-label="Close guide" onClick={close} sx={{ position: 'absolute', right: 12, top: 12 }}>
        <CloseRoundedIcon />
      </IconButton>
      <DialogContent dividers sx={{ py: 2 }}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Build a nonlinear FEM model in six guided steps. Rename numbered entities from Properties without changing solver IDs. Guest mode is ready immediately; sign in only when you want private model history.
        </Typography>
        <Stepper activeStep={activeStep} orientation="vertical">
          {steps.map((item, index) => (
            <Step key={item.title} completed={index < activeStep}>
              <StepLabel>{item.title}</StepLabel>
              <StepContent>
                <Typography variant="body2" color="text.secondary">{item.body}</Typography>
                <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
                  <Button size="small" variant="contained" onClick={() => isLast ? close() : setActiveStep((value) => value + 1)}>
                    {isLast ? 'Finish' : 'Continue'}
                  </Button>
                  <Button size="small" onClick={() => { onOpenStep(item.workflow); close() }}>Open this step</Button>
                  <Button size="small" disabled={activeStep === 0} onClick={() => setActiveStep((value) => Math.max(0, value - 1))}>Back</Button>
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
