import {
  Alert,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Stack,
  Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'

export function SaveProjectDialog({
  open,
  onClose,
  name,
  hasResults,
  signedIn,
  saving,
  error,
  onDownload,
  onAccountSave,
}: {
  open: boolean
  onClose: () => void
  name: string
  hasResults: boolean
  signedIn: boolean
  saving: boolean
  error?: string | null
  onDownload: (includeResults: boolean) => void
  onAccountSave: (includeResults: boolean) => void
}) {
  const [includeResults, setIncludeResults] = useState(hasResults)
  useEffect(() => {
    if (open) setIncludeResults(hasResults)
  }, [open, hasResults])
  return (
    <Dialog
      open={open}
      onClose={saving ? undefined : onClose}
      fullWidth
      maxWidth="sm"
      aria-labelledby="save-project-title"
    >
      <DialogTitle id="save-project-title">Save project</DialogTitle>
      <DialogContent>
        <Stack spacing={2}>
          {error && <Alert severity="error">{error}</Alert>}
          <Typography variant="h6">{name}</Typography>
          <Typography variant="body2" color="text.secondary">
            Keep the model, sections, assignments and analysis settings
            together. Open the project file later to continue working.
          </Typography>
          <FormControlLabel
            control={
              <Checkbox
                disabled={!hasResults || saving}
                checked={includeResults}
                onChange={(event) => setIncludeResults(event.target.checked)}
              />
            }
            label="Include analysis results and current result view"
          />
          {!hasResults && (
            <Alert severity="info">
              No completed analysis is available. The model and analysis
              settings will be saved.
            </Alert>
          )}
          <Alert severity="info">
            Download a project file to your computer, or save a private snapshot
            to your account. Project files can be opened with Open. Maximum file
            size: 20 MB.
          </Alert>
        </Stack>
      </DialogContent>
      <DialogActions sx={{ flexWrap: 'wrap', gap: 1 }}>
        <Button disabled={saving} onClick={onClose}>
          Cancel
        </Button>
        <Button
          variant="outlined"
          disabled={saving}
          onClick={() => onAccountSave(includeResults)}
        >
          {saving
            ? 'Saving…'
            : signedIn
              ? 'Save to account'
              : 'Sign in to save'}
        </Button>
        <Button
          variant="contained"
          disabled={saving}
          onClick={() => onDownload(includeResults)}
        >
          Download project
        </Button>
      </DialogActions>
    </Dialog>
  )
}
