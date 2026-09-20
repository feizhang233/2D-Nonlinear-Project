import { Box } from '@mui/material'
import type { ModelFamily } from '../domain'
import { workspaceFamily, type SpatialFamily } from '../workspaces'
import { SpatialWorkbench } from '../spatial/SpatialWorkbench'
import { SolidWorkbench } from '../continuum3d/SolidWorkbench'
import { PlateWorkbench } from '../plate3d/PlateWorkbench'
import { ShellWorkbench } from '../shell3d/ShellWorkbench'
import { ConfirmProvider } from '../spatial/ConfirmProvider'

export function SpatialWorkspaces({ active, visited, onOpen, on2D, draftFamilies, resultFamilies }: {
  active: SpatialFamily | false
  visited: ReadonlySet<SpatialFamily>
  onOpen: (family: SpatialFamily) => void
  on2D: (family: ModelFamily) => void
  draftFamilies: Set<ModelFamily>
  resultFamilies: Set<ModelFamily>
}) {
  return [...visited].map(id => {
    const common = { active: active === id, on2D: () => on2D(workspaceFamily(id)) }
    const onFrame = () => onOpen('frame3d')
    const onContinuum = () => onOpen('continuum3d')
    const onPlate = () => onOpen('plate3d')
    const onShell = () => onOpen('shell3d')
    return <Box key={id} sx={{ display: active === id ? 'block' : 'none' }}>
      {id === 'frame3d' && <ConfirmProvider><SpatialWorkbench active={common.active}
        draftFamilies={draftFamilies} resultFamilies={resultFamilies}
        onShellSpatial={onShell} onPlateSpatial={onPlate} onContinuumSpatial={onContinuum}
        onDimensionChange={dimension => { if (dimension === '2d') common.on2D() }}
        onWorkspaceChange={on2D} /></ConfirmProvider>}
      {id === 'continuum3d' && <SolidWorkbench {...common} onFrame={onFrame} onPlate={onPlate} onShell={onShell} />}
      {id === 'plate3d' && <PlateWorkbench {...common} onFrame={onFrame} onContinuum={onContinuum} onShell={onShell} />}
      {id === 'shell3d' && <ShellWorkbench {...common} onFrame={onFrame} onContinuum={onContinuum} onPlate={onPlate} />}
    </Box>
  })
}
