import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded'
import Button from '@mui/material/Button'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogContentText from '@mui/material/DialogContentText'
import DialogTitle from '@mui/material/DialogTitle'

interface UnsavedChangesDialogProps {
  open: boolean
  destination: string
  onKeepEditing: () => void
  onApplyAndContinue: () => void
  onDiscardAndContinue: () => void
}

export function UnsavedChangesDialog({
  open,
  destination,
  onKeepEditing,
  onApplyAndContinue,
  onDiscardAndContinue,
}: UnsavedChangesDialogProps) {
  return (
    <Dialog open={open} onClose={onKeepEditing} fullWidth maxWidth="xs" aria-labelledby="unapplied-changes-title">
      <DialogTitle id="unapplied-changes-title" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <WarningAmberRoundedIcon color="warning" /> Unapplied changes
      </DialogTitle>
      <DialogContent>
        <DialogContentText>
          This workspace contains staged edits. Apply them before opening {destination}, discard them, or keep editing.
        </DialogContentText>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2.5, alignItems: 'stretch', flexDirection: 'column-reverse', gap: 1 }}>
        <Button color="inherit" onClick={onKeepEditing}>Keep editing</Button>
        <Button color="error" variant="outlined" onClick={onDiscardAndContinue}>Discard and continue</Button>
        <Button variant="contained" onClick={onApplyAndContinue}>Apply and continue</Button>
      </DialogActions>
    </Dialog>
  )
}
