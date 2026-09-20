import {
  Box,
  Tab,
  Tabs,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import type { ModelFamily } from '../domain'
import { isSpatialWorkspace, workspaceFamily, type WorkspaceId } from '../workspaces'
import { MODEL_FAMILIES, MODEL_FAMILY_ORDER } from '../modelFamilies'

interface WorkspaceSwitcherProps {
  activeFamily: WorkspaceId
  draftFamilies: Set<ModelFamily>
  resultFamilies: Set<ModelFamily>
  onChange: (family: ModelFamily) => void
  onSpatial?: () => void
  onContinuumSpatial?: () => void
  onPlateSpatial?: () => void
  onShellSpatial?: () => void
  onDimensionChange?: (dimension: '2d' | '3d') => void
}

export function WorkspaceSwitcher({
  activeFamily,
  draftFamilies,
  resultFamilies,
  onChange,
  onSpatial,
  onContinuumSpatial,
  onPlateSpatial,
  onShellSpatial,
  onDimensionChange,
}: WorkspaceSwitcherProps) {
  const spatial = isSpatialWorkspace(activeFamily)
  const selected = workspaceFamily(activeFamily)
  const spatialActions = { frame: onSpatial, continuum: onContinuumSpatial, plate: onPlateSpatial, shell: onShellSpatial }
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
      <ToggleButtonGroup
        exclusive
        size="small"
        value={spatial ? '3d' : '2d'}
        aria-label="Model dimension"
        sx={{
          mr: 1,
          '& .MuiToggleButton-root': { py: 0.25, px: 1, fontSize: 12 },
        }}
        onChange={(_, value: '2d' | '3d' | null) => {
          if (!value) return
          if (onDimensionChange) onDimensionChange(value)
          else if (value === '3d') onSpatial?.()
          else onChange(selected)
        }}
      >
        <ToggleButton value="2d">2D</ToggleButton>
        <ToggleButton value="3d" disabled={!onSpatial}>
          3D
        </ToggleButton>
      </ToggleButtonGroup>
      <Tabs
        value={selected}
        onChange={(_, family: ModelFamily) => {
          if (!spatial) onChange(family)
          else spatialActions[family]?.()
        }}
        aria-label="Structural model workspaces"
        sx={{
          flexShrink: 0,
          minHeight: 38,
          '& .MuiTab-root': {
            minHeight: 38,
            minWidth: 82,
            px: 1.5,
            py: 0,
            fontSize: 12,
          },
          '& .MuiTabs-indicator': { height: 2 },
        }}
      >
        {MODEL_FAMILY_ORDER.map((family) => (
          <Tab
            key={family}
            value={family}
            disabled={spatial && !spatialActions[family]}
            title={spatial && !spatialActions[family] ? '3D workspace is not available for this module.' : undefined}
            aria-label={`${MODEL_FAMILIES[family].label}${spatial ? ' 3D' : ''} workspace${!spatial && draftFamilies.has(family) ? ', unapplied changes' : ''}${!spatial && resultFamilies.has(family) ? ', results available' : ''}`}
            label={
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                {MODEL_FAMILIES[family].label}
                {!spatial && draftFamilies.has(family) && (
                  <Typography
                    component="span"
                    color="warning.main"
                    aria-hidden="true"
                  >
                    •
                  </Typography>
                )}
                {!spatial &&
                  !draftFamilies.has(family) &&
                  resultFamilies.has(family) && (
                    <Typography
                      component="span"
                      color="success.main"
                      aria-hidden="true"
                    >
                      ✓
                    </Typography>
                  )}
              </Box>
            }
          />
        ))}
      </Tabs>
    </Box>
  )
}
