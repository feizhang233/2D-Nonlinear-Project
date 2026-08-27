import EditNoteRoundedIcon from '@mui/icons-material/EditNoteRounded'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'

interface DraftActionBarProps {
  dirty: boolean
  busy?: boolean
  onApply: () => void
  onCancel: () => void
}

export function DraftActionBar({ dirty, busy = false, onApply, onCancel }: DraftActionBarProps) {
  return (
    <Box sx={{ flexShrink: 0, borderTop: '1px solid', borderColor: dirty ? 'warning.main' : 'divider', bgcolor: dirty ? 'background.paper' : 'background.containerLow', p: 1.25 }}>
      <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
        <EditNoteRoundedIcon color={dirty ? 'warning' : 'disabled'} />
        <Box sx={{ minWidth: 150, flex: 1 }}>
          <Typography variant="body2" sx={{ fontWeight: 700 }}>
            {dirty ? 'Unapplied changes' : 'Committed model'}
          </Typography>
          <Typography variant="caption" color="text.secondary" noWrap sx={{ display: 'block' }}>
            {dirty ? 'Review the form or canvas changes, then apply or cancel them.' : 'New form and canvas edits will be staged here.'}
          </Typography>
        </Box>
        <Button size="small" color="inherit" disabled={!dirty || busy} onClick={onCancel}>Cancel</Button>
        <Button size="small" variant="contained" disabled={!dirty || busy} onClick={onApply}>Apply changes</Button>
      </Stack>
      {busy && <Alert severity="info" sx={{ mt: 1, py: 0 }}>Wait for the active mesh operation before applying changes.</Alert>}
    </Box>
  )
}
