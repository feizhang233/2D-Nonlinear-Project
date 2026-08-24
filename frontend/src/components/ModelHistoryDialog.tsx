import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded'
import FolderOpenRoundedIcon from '@mui/icons-material/FolderOpenRounded'
import HistoryRoundedIcon from '@mui/icons-material/HistoryRounded'
import SaveRoundedIcon from '@mui/icons-material/SaveRounded'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import IconButton from '@mui/material/IconButton'
import List from '@mui/material/List'
import ListItem from '@mui/material/ListItem'
import ListItemText from '@mui/material/ListItemText'
import Stack from '@mui/material/Stack'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import { useEffect, useState } from 'react'
import type { AuthUser, SavedModel } from '../domain'
import { MODEL_FAMILIES } from '../modelFamilies'
import { EmptyState } from './chrome'

interface Props {
  open: boolean
  user: AuthUser
  entries: SavedModel[]
  loading: boolean
  saving: boolean
  deletingId: string | null
  onClose: () => void
  onSave: () => void
  onOpen: (entry: SavedModel) => void
  onDelete: (entry: SavedModel) => Promise<boolean>
}

export function ModelHistoryDialog({
  open,
  user,
  entries,
  loading,
  saving,
  deletingId,
  onClose,
  onSave,
  onOpen,
  onDelete,
}: Props) {
  const [deleteCandidate, setDeleteCandidate] = useState<SavedModel | null>(null)

  useEffect(() => {
    if (!open) setDeleteCandidate(null)
  }, [open])

  const deleting = Boolean(deleteCandidate && deletingId === deleteCandidate.id)

  if (deleteCandidate) {
    return (
      <Dialog open={open} onClose={deleting ? undefined : () => setDeleteCandidate(null)} fullWidth maxWidth="xs">
        <DialogTitle>Delete saved model?</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            “{deleteCandidate.name}” will be permanently removed from your account history. The model currently open in the workbench will not change.
          </Alert>
          <Typography variant="body2" color="text.secondary">This action cannot be undone.</Typography>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 3 }}>
          <Button autoFocus color="inherit" disabled={deleting} onClick={() => setDeleteCandidate(null)}>Cancel</Button>
          <Button
            color="error"
            variant="contained"
            disabled={deleting}
            sx={{ minWidth: 116 }}
            onClick={() => void onDelete(deleteCandidate).then((deleted) => { if (deleted) setDeleteCandidate(null) })}
          >
            {deleting ? 'Deleting…' : 'Delete model'}
          </Button>
        </DialogActions>
      </Dialog>
    )
  }

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>
        <Stack direction="row" spacing={1.25} sx={{ alignItems: 'center' }}>
          <HistoryRoundedIcon color="primary" />
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="h6">Model history</Typography>
            <Typography variant="body2" color="text.secondary" noWrap>
              Private to {user.display_name} · up to 24 snapshots
            </Typography>
          </Box>
        </Stack>
      </DialogTitle>
      <DialogContent dividers sx={{ minHeight: 280, maxHeight: 'min(62vh, 620px)' }}>
        {loading ? (
          <Stack role="status" spacing={1.5} sx={{ minHeight: 220, alignItems: 'center', justifyContent: 'center' }}>
            <CircularProgress size={28} />
            <Typography variant="body2" color="text.secondary">Loading saved models…</Typography>
          </Stack>
        ) : entries.length === 0 ? (
          <EmptyState
            icon={<HistoryRoundedIcon />}
            title="No saved models yet"
            body="Save the model currently open in the workbench to start your private history."
          />
        ) : (
          <List disablePadding aria-label="Saved models">
            {entries.map((entry, index) => (
              <ListItem
                key={entry.id}
                divider={index < entries.length - 1}
                secondaryAction={(
                  <Stack direction="row" spacing={0.5}>
                    <Tooltip title={`Open ${entry.name}`}>
                      <IconButton aria-label={`Open ${entry.name}`} onClick={() => onOpen(entry)}>
                        <FolderOpenRoundedIcon />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title={`Delete ${entry.name}`}>
                      <IconButton color="error" aria-label={`Delete ${entry.name}`} onClick={() => setDeleteCandidate(entry)}>
                        <DeleteOutlineRoundedIcon />
                      </IconButton>
                    </Tooltip>
                  </Stack>
                )}
                sx={{ py: 1.25, pr: 12 }}
              >
                <ListItemText
                  primary={entry.name}
                  secondary={`${MODEL_FAMILIES[entry.model_family].label} · ${new Date(entry.saved_at).toLocaleString('en-US')}`}
                  slotProps={{ primary: { noWrap: true, sx: { fontWeight: 500 } }, secondary: { noWrap: true } }}
                />
              </ListItem>
            ))}
          </List>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button color="inherit" onClick={onClose}>Close</Button>
        <Button
          variant="contained"
          startIcon={saving ? <CircularProgress size={17} color="inherit" /> : <SaveRoundedIcon />}
          disabled={saving}
          sx={{ minWidth: 144 }}
          onClick={onSave}
        >
          {saving ? 'Saving model…' : 'Save current model'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
