import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle } from '@mui/material'
import type { ComponentProps } from 'react'
import { AnalysisPanel } from './AnalysisPanel'

export function AnalysisSettingsDialog({ open, onClose, ...props }: ComponentProps<typeof AnalysisPanel> & {
  open: boolean; onClose: () => void
}) {
  return <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm" aria-labelledby="analysis-settings-title">
    <DialogTitle id="analysis-settings-title">Analysis settings</DialogTitle>
    <DialogContent dividers>
      <Alert severity="info" sx={{ mb: 2 }}>Set how this model is loaded and solved. Edits join the model draft; apply them from the main action before running.</Alert>
      <AnalysisPanel {...props} />
    </DialogContent>
    <DialogActions><Button variant="outlined" onClick={onClose}>Back to model</Button></DialogActions>
  </Dialog>
}
