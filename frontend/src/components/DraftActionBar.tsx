import { Box, Button, Typography } from '@mui/material'

interface DraftActionBarProps {
  dirty: boolean
  busy?: boolean
  onCancel: () => void
}
export function DraftActionBar({ dirty, busy = false, onCancel }: DraftActionBarProps) {
  return (
    <Box
      sx={{
        height: 34,
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        px: 2,
        gap: 1.5,
        borderTop: '1px solid',
        borderColor: 'divider',
        bgcolor: 'background.paper',
      }}
    >
      <Typography variant="caption" role="status" color={dirty ? 'warning.dark' : 'text.secondary'}>
        {busy ? 'Generating mesh…' : dirty ? 'Unapplied changes' : 'All changes applied'}
      </Typography>
      {dirty && (
        <Typography variant="caption" color="text.secondary">
          Apply at the top right to update the model.
        </Typography>
      )}
      <Box sx={{ flex: 1 }} />
      {dirty && (
        <Button size="small" color="inherit" disabled={busy} onClick={onCancel}>
          Cancel
        </Button>
      )}
    </Box>
  )
}
