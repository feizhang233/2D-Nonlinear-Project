import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded'
import CircleOutlinedIcon from '@mui/icons-material/CircleOutlined'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import Tab from '@mui/material/Tab'
import Tabs from '@mui/material/Tabs'
import Typography from '@mui/material/Typography'
import type { ModelFamily } from '../domain'
import { MODEL_FAMILIES, MODEL_FAMILY_ORDER } from '../modelFamilies'

interface WorkspaceSwitcherProps {
  activeFamily: ModelFamily
  draftFamilies: Set<ModelFamily>
  resultFamilies: Set<ModelFamily>
  onChange: (family: ModelFamily) => void
}

export function WorkspaceSwitcher({ activeFamily, draftFamilies, resultFamilies, onChange }: WorkspaceSwitcherProps) {
  return (
    <Box sx={{ minWidth: 610, borderRight: '1px solid', borderColor: 'divider' }}>
      <Tabs
        value={activeFamily}
        onChange={(_, family: ModelFamily) => onChange(family)}
        aria-label="Structural model workspaces"
        sx={{ minHeight: 64, '& .MuiTab-root': { minHeight: 64, minWidth: 146, px: 1.5 } }}
      >
        {MODEL_FAMILY_ORDER.map((family) => {
          const info = MODEL_FAMILIES[family]
          const hasDraft = draftFamilies.has(family)
          const hasResults = resultFamilies.has(family)
          return (
            <Tab
              key={family}
              value={family}
              aria-label={`${info.label} workspace${hasDraft ? ', unapplied changes' : ''}${hasResults ? ', results available' : ''}`}
              label={
                <Box sx={{ width: '100%', textAlign: 'left' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                    {hasResults
                      ? <CheckCircleRoundedIcon color="success" sx={{ fontSize: 16 }} />
                      : <CircleOutlinedIcon sx={{ fontSize: 15, color: 'text.disabled' }} />}
                    <Typography component="span" variant="body2" sx={{ fontWeight: 700 }}>{info.label}</Typography>
                    {hasDraft && <Chip size="small" color="warning" label="Draft" sx={{ height: 20 }} />}
                  </Box>
                  <Typography component="span" variant="caption" color="text.secondary" noWrap sx={{ display: 'block', pl: 2.9 }}>
                    {info.formulation}
                  </Typography>
                </Box>
              }
            />
          )
        })}
      </Tabs>
    </Box>
  )
}
