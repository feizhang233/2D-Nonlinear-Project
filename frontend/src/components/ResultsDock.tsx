import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded'
import ErrorRoundedIcon from '@mui/icons-material/ErrorRounded'
import ExpandLessRoundedIcon from '@mui/icons-material/ExpandLessRounded'
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded'
import HistoryToggleOffRoundedIcon from '@mui/icons-material/HistoryToggleOffRounded'
import ShowChartRoundedIcon from '@mui/icons-material/ShowChartRounded'
import TableChartRoundedIcon from '@mui/icons-material/TableChartRounded'
import Alert from '@mui/material/Alert'
import Badge from '@mui/material/Badge'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import IconButton from '@mui/material/IconButton'
import LinearProgress from '@mui/material/LinearProgress'
import MenuItem from '@mui/material/MenuItem'
import Stack from '@mui/material/Stack'
import Tab from '@mui/material/Tab'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import Tabs from '@mui/material/Tabs'
import TextField from '@mui/material/TextField'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import { useEffect, useState } from 'react'
import type { AnalysisRecord, ModelInput, ResultTab } from '../domain'
import { elementDisplayLabel } from '../entityLabels'
import { MiniChart } from './MiniChart'
import { EmptyState, StatTile } from './chrome'
import { MODEL_FAMILIES } from '../modelFamilies'
import {
  convergencePoints, elementRecords, elementResultSummary, failureSuggestion,
  formatNumber, loadDisplacementPoints, resultMetricLabels,
} from '../resultUtils'

interface ResultsDockProps {
  model: ModelInput
  record: AnalysisRecord | null
  state: 'idle' | 'validating' | 'running' | 'succeeded' | 'failed'
  error: string | null
  invalidated: boolean
  tab: ResultTab
  selectedStep: number
  onTabChange: (tab: ResultTab) => void
  onStepChange: (step: number) => void
}

const tabLabels: Array<{ value: ResultTab; label: string }> = [
  { value: 'monitor', label: 'Solve monitor' },
  { value: 'curves', label: 'Path and convergence' },
  { value: 'tables', label: 'Result tables' },
  { value: 'failure', label: 'Failure evidence' },
]

export function ResultsDock({ model, record, state, error, invalidated, tab, selectedStep, onTabChange, onStepChange }: ResultsDockProps) {
  const [expanded, setExpanded] = useState(false)
  const result = record?.result ?? null
  const step = result?.steps[selectedStep]
  const convergence = convergencePoints(result)
  const loadPath = loadDisplacementPoints(model, result)
  const failures = result?.failures ?? []
  const failureCount = failures.length + (record?.error && !failures.length ? 1 : 0)
  const elementData = elementRecords(result)
  const elementSummaries = elementData.map((item) => elementResultSummary(model.model_family, item))
  const metricLabels = resultMetricLabels[model.model_family]
  const family = MODEL_FAMILIES[model.model_family]

  useEffect(() => {
    if (state === 'running' || state === 'succeeded' || state === 'failed') setExpanded(true)
  }, [state])

  return (
    <Box sx={{ height: expanded ? 300 : 48, flexShrink: 0, borderTop: '1px solid', borderColor: 'divider', overflow: 'hidden', transition: 'height .18s ease', bgcolor: 'background.paper' }}>
      <Stack direction="row" sx={{ alignItems: 'center', height: 48, borderBottom: expanded ? '1px solid' : 0, borderColor: 'divider', px: 1, bgcolor: 'background.containerLow' }}>
        <Tabs value={tab} onChange={(_, value: ResultTab) => onTabChange(value)} sx={{ minHeight: 48, '& .MuiTab-root': { minHeight: 48, py: 0 } }}>
          {tabLabels.map((item) => (
            <Tab
              key={item.value}
              value={item.value}
              label={item.value === 'failure' && failureCount > 0
                ? <Badge color="error" badgeContent={failureCount} sx={{ '& .MuiBadge-badge': { right: -10, top: 2 } }}>{item.label}</Badge>
                : item.label}
            />
          ))}
        </Tabs>
        <Box sx={{ flex: 1 }} />
        {state === 'running' && <Chip size="small" color="primary" label="Solving" />}
        {state === 'succeeded' && <Chip size="small" color="success" icon={<CheckCircleRoundedIcon />} label={`${record?.progress.accepted_steps ?? 0} accepted steps`} />}
        {state === 'failed' && <Chip size="small" color="error" icon={<ErrorRoundedIcon />} label="Analysis failed" />}
        <Tooltip title={expanded ? 'Collapse results' : 'Expand results'}>
          <IconButton size="small" aria-label={expanded ? 'Collapse results' : 'Expand results'} onClick={() => setExpanded((value) => !value)}>
            {expanded ? <ExpandMoreRoundedIcon /> : <ExpandLessRoundedIcon />}
          </IconButton>
        </Tooltip>
      </Stack>
      {expanded && (
        <Box sx={{ height: 252, overflow: 'auto', p: 1.5 }}>
          {invalidated && !result && <Alert severity="warning" sx={{ mb: 1 }}>The model changed, so the previous results were invalidated and removed from this workspace. Run the analysis again.</Alert>}
          {tab === 'monitor' && (
            <Stack spacing={1.25}>
              {state === 'idle' && !invalidated && (
                <EmptyState
                  icon={<HistoryToggleOffRoundedIcon />}
                  title="Ready to solve"
                  body="Review the model on the left and analysis controls on the right, then choose Run analysis or press Ctrl / ⌘ + Enter."
                />
              )}
              {state === 'running' && (
                <Box>
                  <LinearProgress />
                  <Stack direction="row" spacing={1} useFlexGap sx={{ mt: 1.25, flexWrap: 'wrap' }}>
                    <StatTile label="Status" value={record?.progress.message ?? 'Creating asynchronous analysis job'} color="primary" />
                    <StatTile label="Step" value={String(record?.progress.current_step ?? '—')} />
                    <StatTile label="Iteration" value={String(record?.progress.current_iteration ?? '—')} />
                    <StatTile label="Accepted" value={String(record?.progress.accepted_steps ?? 0)} color="success" />
                  </Stack>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                    API polling updates the job state. Cancellation preserves committed state and discards uncommitted trials.
                  </Typography>
                </Box>
              )}
              {error && state === 'failed' && <Alert severity="error">{error}</Alert>}
              {result && (
                <>
                  <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }} useFlexGap>
                    <Chip size="small" color={result.status === 'succeeded' ? 'success' : 'error'} label={result.status === 'succeeded' ? 'Solve succeeded' : 'Solve failed'} />
                    <Chip size="small" variant="outlined" label={family.label} />
                    <Typography variant="body2">Solver {result.solver_version}</Typography>
                    <Box sx={{ flex: 1 }} />
                    <TextField select label="Current step" value={Math.min(selectedStep, Math.max(0, result.steps.length - 1))} onChange={(event) => onStepChange(Number(event.target.value))} sx={{ minWidth: 168 }}>
                      {result.steps.map((item, index) => <MenuItem key={`${item.step_index}-${index}`} value={index}>Step {item.step_index} · {item.status === 'accepted' ? 'accepted' : 'rejected'}</MenuItem>)}
                    </TextField>
                  </Stack>
                  {step && (
                    <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
                      <StatTile label="Load factor λ" value={formatNumber(step.load_factor)} />
                      <StatTile label="Requested step" value={formatNumber(step.requested_step_size)} />
                      <StatTile label="Commit state" value={step.status === 'accepted' ? 'Accepted / committed' : 'Rejected / rollback'} color={step.status === 'accepted' ? 'success' : 'warning'} />
                      <StatTile label="Iterations" value={String(step.iterations.length)} />
                    </Stack>
                  )}
                  <TableContainer sx={{ maxHeight: 118, borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
                    <Table size="small" stickyHeader aria-label="Iteration records">
                      <TableHead>
                        <TableRow>
                          <TableCell>Iteration</TableCell>
                          <TableCell>Status</TableCell>
                          <TableCell>Residual ‖R‖</TableCell>
                          <TableCell>Correction ‖Δu‖</TableCell>
                          <TableCell>Energy</TableCell>
                          <TableCell>α</TableCell>
                          <TableCell>Tangent</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {step?.iterations.map((iteration) => (
                          <TableRow key={iteration.iteration_index}>
                            <TableCell>{iteration.iteration_index}</TableCell>
                            <TableCell>
                              <Chip size="small" color={iteration.status === 'converged' ? 'success' : iteration.status === 'rejected' ? 'error' : 'default'} label={iteration.status} />
                            </TableCell>
                            <TableCell>{formatNumber(iteration.residual_norm)}</TableCell>
                            <TableCell>{formatNumber(iteration.displacement_correction_norm)}</TableCell>
                            <TableCell>{formatNumber(iteration.energy_norm)}</TableCell>
                            <TableCell>{formatNumber(iteration.accepted_alpha)}</TableCell>
                            <TableCell>{iteration.tangent_reassembled ? 'Reassembled' : 'Reused'}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </>
              )}
            </Stack>
          )}

          {tab === 'curves' && (
            result ? (
              <Stack direction="row" spacing={2}>
                <Box sx={{ flex: 1, minWidth: 0 }}><MiniChart title="Load–displacement path" xLabel="Monitored DOF displacement" yLabel="Load factor λ" series={[{ name: 'Path', color: '#4563b5', points: loadPath }]} /></Box>
                <Box sx={{ flex: 1, minWidth: 0 }}><MiniChart title="Iteration convergence history" xLabel="Global iteration index" yLabel="Norm (log)" logY series={[
                  { name: 'Residual', color: '#c43d4b', points: convergence.map((point) => ({ x: point.x, y: point.y })) },
                  { name: 'Displacement', color: '#4563b5', points: convergence.map((point) => ({ x: point.x, y: point.correction })) },
                  { name: 'Energy', color: '#138a63', points: convergence.map((point) => ({ x: point.x, y: point.energy })) },
                ]} /></Box>
              </Stack>
            ) : (
              <EmptyState icon={<ShowChartRoundedIcon />} title="No path curves yet" body="Successful and failed solves both retain step and iteration records. Run an analysis to compare the load path with convergence norms." />
            )
          )}

          {tab === 'tables' && (
            result ? (
              <Stack direction="row" spacing={2}>
                <TableContainer sx={{ flex: 1, maxHeight: 216, borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
                  <Table size="small" stickyHeader>
                    <TableHead>
                      <TableRow>
                        <TableCell>Step</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell>λ</TableCell>
                        <TableCell>Step size</TableCell>
                        <TableCell>Iterations</TableCell>
                        <TableCell>Termination reason</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {result.steps.map((item, index) => (
                        <TableRow key={`${item.step_index}-${item.state_id}`} hover selected={index === selectedStep} onClick={() => onStepChange(index)} sx={{ cursor: 'pointer' }}>
                          <TableCell>{item.step_index}</TableCell>
                          <TableCell>{item.status}</TableCell>
                          <TableCell>{formatNumber(item.load_factor)}</TableCell>
                          <TableCell>{formatNumber(item.accepted_step_size ?? item.requested_step_size)}</TableCell>
                          <TableCell>{item.iterations.length}</TableCell>
                          <TableCell>{String(item.response.termination_reason ?? item.failure?.code ?? '—')}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
                <TableContainer sx={{ flex: 1, maxHeight: 216, borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
                  <Table size="small" stickyHeader aria-label={`${family.label} element recovery results`}>
                    <TableHead>
                      <TableRow>
                        <TableCell>Element</TableCell>
                        {metricLabels.map((label) => <TableCell key={label}>{label}</TableCell>)}
                        <TableCell>Energy</TableCell>
                        <TableCell>Basis</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {elementSummaries.map((item) => (
                        <TableRow key={item.elementId}>
                          <TableCell>{elementDisplayLabel(model, item.elementId)}</TableCell>
                          {item.metrics.map((value, index) => <TableCell key={`${item.elementId}-${metricLabels[index]}`}>{formatNumber(value)}</TableCell>)}
                          <TableCell>{formatNumber(item.energy)}</TableCell>
                          <TableCell>{item.qualifier ?? 'Element local'}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Stack>
            ) : (
              <EmptyState icon={<TableChartRoundedIcon />} title="No result tables yet" body="Result tables are the exact alternative to the color projection. Step history and recovered element quantities appear here after an analysis." />
            )
          )}

          {tab === 'failure' && (
            <Stack spacing={1}>
              {!failures.length && !record?.error && <Alert severity="success">The current result has no failure records. Rejected steps, if any, remain available in the result tables.</Alert>}
              {(failures.length ? failures : record?.error ? [{ ...record.error, details: record.error.details ?? {} }] : []).map((failure, index) => (
                <Alert key={`${failure.code}-${index}`} severity="error">
                  <Typography variant="subtitle2">{failure.code} · {failure.message}</Typography>
                  {'step_index' in failure && <Typography variant="body2">Location: Step {String(failure.step_index ?? '—')} / Iteration {String(failure.iteration_index ?? '—')} / {String(failure.json_path ?? 'No JSON path')}</Typography>}
                  <Typography variant="body2" sx={{ mt: 0.5 }}>Suggestion: {failureSuggestion(failure.code)}</Typography>
                  <Typography component="pre" variant="caption" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', mt: 0.5, mb: 0 }}>{JSON.stringify(failure.details, null, 2)}</Typography>
                </Alert>
              ))}
              {model.analysis.control_method === 'arc_length' && <Alert severity="warning">Arc-length convergence does not prove path stability, branch uniqueness, or successful branch switching.</Alert>}
            </Stack>
          )}
        </Box>
      )}
    </Box>
  )
}
