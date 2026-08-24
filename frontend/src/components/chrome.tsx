import Box from '@mui/material/Box'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import type { ReactNode } from 'react'

export function SectionHeader({
  icon,
  title,
  subtitle,
  action,
}: {
  icon?: ReactNode
  title: string
  subtitle?: string
  action?: ReactNode
}) {
  return (
    <Stack direction="row" spacing={1.25} sx={{ alignItems: 'flex-start' }}>
      {icon && (
        <Box
          sx={{
            width: 36,
            height: 36,
            borderRadius: 2.25,
            flexShrink: 0,
            display: 'grid',
            placeItems: 'center',
            bgcolor: 'action.selected',
            color: 'primary.main',
          }}
        >
          {icon}
        </Box>
      )}
      <Box sx={{ minWidth: 0, flex: 1 }}>
        <Typography variant="subtitle1">{title}</Typography>
        {subtitle && (
          <Typography variant="body2" color="text.secondary">
            {subtitle}
          </Typography>
        )}
      </Box>
      {action}
    </Stack>
  )
}

export function EmptyState({ icon, title, body }: { icon: ReactNode; title: string; body: string }) {
  return (
    <Stack spacing={1} sx={{ alignItems: 'center', justifyContent: 'center', py: 3, px: 2, textAlign: 'center' }}>
      <Box
        sx={{
          width: 52,
          height: 52,
          borderRadius: 3,
          mb: 0.5,
          display: 'grid',
          placeItems: 'center',
          bgcolor: 'background.containerHigh',
          color: 'primary.main',
        }}
      >
        {icon}
      </Box>
      <Typography variant="subtitle2">{title}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 440 }}>
        {body}
      </Typography>
    </Stack>
  )
}

export function StatTile({
  label,
  value,
  color,
}: {
  label: string
  value: string
  color?: 'primary' | 'success' | 'warning' | 'error' | 'info'
}) {
  return (
    <Box
      sx={{
        px: 1.5,
        py: 1,
        minWidth: 104,
        flex: 1,
        borderRadius: 2.5,
        bgcolor: 'background.containerLow',
      }}
    >
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography
        variant="subtitle2"
        color={color ? `${color}.main` : 'text.primary'}
        sx={{ fontVariantNumeric: 'tabular-nums' }}
      >
        {value}
      </Typography>
    </Box>
  )
}
