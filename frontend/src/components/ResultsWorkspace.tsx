import InsightsRoundedIcon from '@mui/icons-material/InsightsRounded'
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
  return (
    <Box component="main" aria-label="Analysis results workspace" sx={{ flex: 1, minHeight: 0, p: 1.25, display: 'grid', gridTemplateColumns: 'minmax(480px, 1.15fr) minmax(520px, 1fr)', gap: 1.25 }}>
      <Paper sx={{ minWidth: 0, minHeight: 0, overflow: 'hidden', border: '1px solid', borderColor: 'divider', display: 'flex', flexDirection: 'column' }}>
        <Stack direction="row" spacing={1} sx={{ minHeight: 48, px: 1.5, alignItems: 'center', borderBottom: '1px solid', borderColor: 'divider', bgcolor: 'background.containerLow' }}>
          <InsightsRoundedIcon color="primary" />
          <Typography variant="subtitle2">Result visualization</Typography>
          <Typography variant="caption" color="text.secondary">Committed model · read-only</Typography>
        </Stack>
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
            onSelection={onSelection}
            onModelChange={() => undefined}
            onPlace={() => undefined}
            onPendingMember={() => undefined}
          />
        </Box>
      </Paper>
      <Paper sx={{ minWidth: 0, minHeight: 0, overflow: 'hidden', border: '1px solid', borderColor: 'divider' }}>
        <ResultsDock
          standalone
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
    </Box>
  )
}
