import TableChartOutlinedIcon from '@mui/icons-material/TableChartOutlined'
import CloseRoundedIcon from '@mui/icons-material/CloseRounded'
import { Button } from '@mui/material'
import { useEffect, useState } from 'react'
import Box from '@mui/material/Box'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import type { AnalysisRecord, ModelInput, ResultTab, ResultView, Selection } from '../domain'
import { ModelCanvas } from './ModelCanvas'
import { ResultsDock } from './ResultsDock'

interface ResultsWorkspaceProps {
  model: ModelInput
  record: AnalysisRecord | null
  analysisState: 'idle' | 'validating' | 'running' | 'succeeded' | 'failed'
  error: string | null
  invalidated: boolean
  resultTab: ResultTab
  resultView: ResultView
  selectedStep: number
  selection: Selection
  onResultTabChange: (tab: ResultTab) => void
  onResultViewChange: (view: ResultView) => void
  onStepChange: (step: number) => void
  onSelection: (selection: Selection) => void
}

export function ResultsWorkspace({
  model,
  record,
  analysisState,
  error,
  invalidated,
  resultTab,
  resultView,
  selectedStep,
  selection,
  onResultTabChange,
  onResultViewChange,
  onStepChange,
  onSelection,
}: ResultsWorkspaceProps) {
  const [detailsOpen, setDetailsOpen] = useState(analysisState !== 'succeeded')
  useEffect(() => {
    setDetailsOpen(analysisState !== 'succeeded')
  }, [analysisState])
  return (
    <Box
      component="main"
      aria-label="Analysis results workspace"
      sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}
    >
      <Stack
        direction="row"
        sx={{
          height: 46,
          px: 2,
          alignItems: 'center',
          borderBottom: '1px solid',
          borderColor: 'divider',
          bgcolor: 'background.paper',
          gap: 1.5,
        }}
      >
        <Typography variant="subtitle2">Results</Typography>
        <Typography variant="caption" color="text.secondary">
          Read-only
        </Typography>
        <Box sx={{ flex: 1 }} />
        <Button
          size="small"
          color="inherit"
          startIcon={detailsOpen ? <CloseRoundedIcon /> : <TableChartOutlinedIcon />}
          aria-label={detailsOpen ? 'Hide result details' : 'Show result details'}
          aria-expanded={detailsOpen}
          onClick={() => setDetailsOpen((value) => !value)}
        >
          {detailsOpen ? 'Hide details' : 'Results & tables'}
        </Button>
      </Stack>
      <Box sx={{ flex: 1, minHeight: 0, display: 'flex' }}>
        <Box sx={{ flex: 1, minWidth: 0, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <Box sx={{ flex: 1, minHeight: 0 }}>
            <ModelCanvas
              readOnly
              showResultControls
              model={model}
              result={record?.result ?? null}
              selectedStep={selectedStep}
              view={resultView}
              selection={selection}
              cadTool="select"
              placement={null}
              pendingMember={null}
              onViewChange={onResultViewChange}
              onStepChange={onStepChange}
              onSelection={onSelection}
              onModelChange={() => undefined}
              onPlace={() => undefined}
              onPendingMember={() => undefined}
            />
          </Box>
        </Box>
        {detailsOpen && (
          <Paper
            component="aside"
            aria-label="Result details"
            square
            sx={{
              width: 460,
              flexShrink: 0,
              minWidth: 0,
              minHeight: 0,
              overflow: 'hidden',
              borderLeft: '1px solid',
              borderColor: 'divider',
            }}
          >
            <ResultsDock
              standalone
              selection={selection}
              onSelection={onSelection}
              model={model}
              record={record}
              state={analysisState}
              error={error}
              invalidated={invalidated}
              tab={resultTab}
              selectedStep={selectedStep}
              onTabChange={onResultTabChange}
              onStepChange={onStepChange}
            />
          </Paper>
        )}
      </Box>
    </Box>
  )
}
