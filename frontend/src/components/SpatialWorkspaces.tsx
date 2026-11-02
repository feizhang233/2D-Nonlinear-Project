import { Alert, Box, Button, CircularProgress, Stack, Typography } from '@mui/material'
import { Component, lazy, Suspense, useMemo, useReducer, type ComponentType, type ReactNode } from 'react'
import type { ModelFamily } from '../domain'
import { workspaceFamily, type SpatialFamily } from '../workspaces'
import { WorkspaceSwitcher } from './WorkspaceSwitcher'

interface WorkbenchProps {
  active: boolean
  onOpen: (family: SpatialFamily) => void
  on2D: (family: ModelFamily) => void
  draftFamilies: Set<ModelFamily>
  resultFamilies: Set<ModelFamily>
}

type WorkspaceLoader = () => Promise<{ default: ComponentType<WorkbenchProps> }>

// Keep each family out of the initial bundle. Once visited, its mounted document
// still owns the camera, results and unfinished property fields.
const workspaceLoaders: Record<SpatialFamily, WorkspaceLoader> = {
  frame3d: () => Promise.all([
    import('../spatial/SpatialWorkbench'),
    import('../spatial/ConfirmProvider'),
  ]).then(([{ SpatialWorkbench }, { ConfirmProvider }]) => ({
    default: ({ active, onOpen, on2D, draftFamilies, resultFamilies }) => (
      <ConfirmProvider><SpatialWorkbench active={active}
        draftFamilies={draftFamilies} resultFamilies={resultFamilies}
        onShellSpatial={() => onOpen('shell3d')}
        onPlateSpatial={() => onOpen('plate3d')}
        onContinuumSpatial={() => onOpen('continuum3d')}
        onDimensionChange={dimension => { if (dimension === '2d') on2D('frame') }}
        onWorkspaceChange={on2D} /></ConfirmProvider>
    ),
  })),
  continuum3d: () => import('../continuum3d/SolidWorkbench').then(({ SolidWorkbench }) => ({
    default: ({ active, onOpen, on2D }) => <SolidWorkbench active={active}
      on2D={() => on2D('continuum')} onFrame={() => onOpen('frame3d')}
      onPlate={() => onOpen('plate3d')} onShell={() => onOpen('shell3d')} />,
  })),
  plate3d: () => import('../plate3d/PlateWorkbench').then(({ PlateWorkbench }) => ({
    default: ({ active, onOpen, on2D }) => <PlateWorkbench active={active}
      on2D={() => on2D('plate')} onFrame={() => onOpen('frame3d')}
      onContinuum={() => onOpen('continuum3d')} onShell={() => onOpen('shell3d')} />,
  })),
  shell3d: () => import('../shell3d/ShellWorkbench').then(({ ShellWorkbench }) => ({
    default: ({ active, onOpen, on2D }) => <ShellWorkbench active={active}
      on2D={() => on2D('shell')} onFrame={() => onOpen('frame3d')}
      onContinuum={() => onOpen('continuum3d')} onPlate={() => onOpen('plate3d')} />,
  })),
}

class WorkspaceErrorBoundary extends Component<{
  children: ReactNode
  fallback: ReactNode
}, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() { return this.state.failed ? this.props.fallback : this.props.children }
}

function DeferredWorkspace({ family, ...props }: WorkbenchProps & { family: SpatialFamily }) {
  const [attempt, retry] = useReducer((value: number) => value + 1, 0)
  const Workbench = useMemo(() => lazy(workspaceLoaders[family]), [family, attempt])
  const fallback = (failed = false) => (
    <Box sx={{ height: '100dvh', minWidth: 1120, display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ height: 56, px: 2, display: 'flex', alignItems: 'center', borderBottom: '1px solid', borderColor: 'divider' }}>
        <Typography variant="h6" sx={{ fontSize: 16 }}>Nonlinear Studio</Typography>
      </Box>
      <Box sx={{ px: 1, minHeight: 38, borderBottom: '1px solid', borderColor: 'divider' }}>
        <WorkspaceSwitcher activeFamily={family} draftFamilies={props.draftFamilies}
          resultFamilies={props.resultFamilies} onChange={props.on2D}
          onSpatial={() => props.onOpen('frame3d')}
          onContinuumSpatial={() => props.onOpen('continuum3d')}
          onPlateSpatial={() => props.onOpen('plate3d')}
          onShellSpatial={() => props.onOpen('shell3d')}
          onDimensionChange={dimension => {
            if (dimension === '2d') props.on2D(workspaceFamily(family))
          }} />
      </Box>
      <Stack spacing={2} sx={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
        {failed ? <>
          <Alert severity="error">This workspace could not be loaded. Check your connection and retry.</Alert>
          <Button variant="outlined" onClick={retry}>Retry loading workspace</Button>
        </> : <Stack role="status" spacing={2} sx={{ alignItems: 'center' }}>
          <CircularProgress size={28} />
          <Typography variant="body2">Loading {workspaceFamily(family)} 3D workspace…</Typography>
        </Stack>}
      </Stack>
    </Box>
  )
  return <WorkspaceErrorBoundary key={attempt} fallback={fallback(true)}>
    <Suspense fallback={fallback()}><Workbench {...props} /></Suspense>
  </WorkspaceErrorBoundary>
}

export function SpatialWorkspaces({ active, visited, onOpen, on2D, draftFamilies, resultFamilies }: {
  active: SpatialFamily | false
  visited: ReadonlySet<SpatialFamily>
  onOpen: (family: SpatialFamily) => void
  on2D: (family: ModelFamily) => void
  draftFamilies: Set<ModelFamily>
  resultFamilies: Set<ModelFamily>
}) {
  return [...visited].map(id => <Box key={id} sx={{ display: active === id ? 'block' : 'none' }}>
    <DeferredWorkspace family={id} active={active === id} onOpen={onOpen} on2D={on2D}
      draftFamilies={draftFamilies} resultFamilies={resultFamilies} />
  </Box>)
}
