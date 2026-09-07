import { Box, Tab, Tabs, Typography } from '@mui/material'
import type { ModelFamily } from '../domain'
import { MODEL_FAMILIES, MODEL_FAMILY_ORDER } from '../modelFamilies'

interface WorkspaceSwitcherProps {
  activeFamily: ModelFamily
  draftFamilies: Set<ModelFamily>
  resultFamilies: Set<ModelFamily>
  onChange: (family: ModelFamily) => void
}

export function WorkspaceSwitcher({
  activeFamily,
  draftFamilies,
  resultFamilies,
  onChange,
}: WorkspaceSwitcherProps) {
  return (
    <Tabs
      value={activeFamily}
      onChange={(_, family: ModelFamily) => onChange(family)}
      aria-label="Structural model workspaces"
      sx={{
        flexShrink: 0,
        minHeight: 38,
        '& .MuiTab-root': { minHeight: 38, minWidth: 82, px: 1.5, py: 0, fontSize: 12 },
        '& .MuiTabs-indicator': { height: 2 },
      }}
    >
      {MODEL_FAMILY_ORDER.map((family) => (
        <Tab
          key={family}
          value={family}
          aria-label={`${MODEL_FAMILIES[family].label} workspace${draftFamilies.has(family) ? ', unapplied changes' : ''}${resultFamilies.has(family) ? ', results available' : ''}`}
          label={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              {MODEL_FAMILIES[family].label}
              {draftFamilies.has(family) && (
                <Typography component="span" color="warning.main" aria-hidden="true">
                  •
                </Typography>
              )}
              {!draftFamilies.has(family) && resultFamilies.has(family) && (
                <Typography component="span" color="success.main" aria-hidden="true">
                  ✓
                </Typography>
              )}
            </Box>
          }
        />
      ))}
    </Tabs>
  )
}
