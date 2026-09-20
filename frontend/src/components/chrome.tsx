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
            width: 20,
            height: 24,
            borderRadius: 1,
            flexShrink: 0,
            display: 'grid',
            placeItems: 'center',
            bgcolor: 'transparent',
            color: 'primary.main',
          }}
        >
          {icon}
        </Box>
      )}
      <Box sx={{ minWidth: 0, flex: 1 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
          {title}
        </Typography>
        {subtitle &&
          (subtitle.length > 95 ? (
            <Box
              component="details"
              sx={{
                mt: 0.5,
                color: 'text.secondary',
                fontSize: 12,
                '& summary': { cursor: 'pointer' },
              }}
            >
              <summary>Details</summary>
              <Typography variant="caption" sx={{ display: 'block', mt: 0.5 }}>
                {subtitle}
              </Typography>
            </Box>
          ) : (
            <Typography variant="caption" color="text.secondary">
              {subtitle}
            </Typography>
          ))}
      </Box>
      {action}
    </Stack>
  )
}

export function EmptyState({
  icon,
  title,
  body,
}: {
  icon: ReactNode
  title: string
  body: string
}) {
  return (
    <Stack
      spacing={1}
      sx={{ alignItems: 'center', justifyContent: 'center', py: 3, px: 2, textAlign: 'center' }}
    >
      <Box
        sx={{
          width: 52,
          height: 52,
          borderRadius: 1,
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
        minWidth: 0,
        flex: '1 1 calc(50% - 8px)',
        borderBottom: '1px solid',
        borderColor: 'divider',
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
