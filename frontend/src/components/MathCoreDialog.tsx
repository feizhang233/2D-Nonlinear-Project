import FunctionsRoundedIcon from '@mui/icons-material/FunctionsRounded'
import ReplayRoundedIcon from '@mui/icons-material/ReplayRounded'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { executeMathCore, listMathCores } from '../api'
import type { JsonValue, MathCoreCatalog, MathCoreResponse } from '../mathCore'
import { EmptyState, SectionHeader } from './chrome'

interface Props {
  open: boolean
  onClose: () => void
}

const formatParameters = (value: Record<string, JsonValue>) => JSON.stringify(value, null, 2)

export function MathCoreDialog({ open, onClose }: Props) {
  const [catalog, setCatalog] = useState<MathCoreCatalog | null>(null)
  const [selectedCoreId, setSelectedCoreId] = useState('')
  const [selectedOperationName, setSelectedOperationName] = useState('')
  const [parameters, setParameters] = useState('{}')
  const [catalogLoading, setCatalogLoading] = useState(false)
  const [catalogError, setCatalogError] = useState<string | null>(null)
  const [editorError, setEditorError] = useState<string | null>(null)
  const [executionError, setExecutionError] = useState<string | null>(null)
  const [response, setResponse] = useState<MathCoreResponse | null>(null)
  const [running, setRunning] = useState(false)
  const catalogRequestRef = useRef<AbortController | null>(null)
  const executionRequestRef = useRef<AbortController | null>(null)
  const editorRef = useRef<HTMLInputElement | null>(null)

  const selectedCore = useMemo(
    () => catalog?.cores.find((core) => core.core_id === selectedCoreId) ?? null,
    [catalog, selectedCoreId],
  )
  const selectedOperation = useMemo(
    () => selectedCore?.operations.find((operation) => operation.name === selectedOperationName) ?? null,
    [selectedCore, selectedOperationName],
  )

  const selectCore = (coreId: string, nextCatalog = catalog) => {
    const core = nextCatalog?.cores.find((item) => item.core_id === coreId)
    const operation = core?.operations[0]
    setSelectedCoreId(coreId)
    setSelectedOperationName(operation?.name ?? '')
    setParameters(formatParameters(operation?.example_parameters ?? {}))
    setEditorError(null)
    setExecutionError(null)
    setResponse(null)
  }

  const loadCatalog = () => {
    catalogRequestRef.current?.abort()
    const controller = new AbortController()
    catalogRequestRef.current = controller
    setCatalogLoading(true)
    setCatalogError(null)
    void listMathCores(controller.signal)
      .then((nextCatalog) => {
        if (controller.signal.aborted || catalogRequestRef.current !== controller) return
        setCatalog(nextCatalog)
        selectCore(nextCatalog.cores[0]?.core_id ?? '', nextCatalog)
      })
      .catch((error) => {
        if (controller.signal.aborted) return
        setCatalogError(error instanceof Error ? error.message : 'Math Core metadata could not be loaded.')
      })
      .finally(() => {
        if (catalogRequestRef.current === controller) {
          catalogRequestRef.current = null
          setCatalogLoading(false)
        }
      })
  }

  useEffect(() => {
    if (!open) return undefined
    setCatalog(null)
    setResponse(null)
    setExecutionError(null)
    loadCatalog()
    return () => catalogRequestRef.current?.abort()
    // The dialog intentionally reloads the server-owned catalog on every open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  useEffect(() => () => {
    catalogRequestRef.current?.abort()
    executionRequestRef.current?.abort()
  }, [])

  const selectOperation = (operationName: string) => {
    const operation = selectedCore?.operations.find((item) => item.name === operationName)
    setSelectedOperationName(operationName)
    setParameters(formatParameters(operation?.example_parameters ?? {}))
    setEditorError(null)
    setExecutionError(null)
    setResponse(null)
  }

  const resetExample = () => {
    setParameters(formatParameters(selectedOperation?.example_parameters ?? {}))
    setEditorError(null)
    setExecutionError(null)
    setResponse(null)
    editorRef.current?.focus()
  }

  const execute = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (running || !selectedCore || !selectedOperation) return
    let parsed: unknown
    try {
      parsed = JSON.parse(parameters)
    } catch {
      setEditorError('Enter valid JSON. Property names and string values must use double quotes.')
      editorRef.current?.focus()
      return
    }
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      setEditorError('Parameters must be one JSON object, for example {}.')
      editorRef.current?.focus()
      return
    }

    executionRequestRef.current?.abort()
    const controller = new AbortController()
    executionRequestRef.current = controller
    setRunning(true)
    setEditorError(null)
    setExecutionError(null)
    setResponse(null)
    try {
      const nextResponse = await executeMathCore({
        schema_version: '1.0.0',
        core: selectedCore.core_id,
        operation: selectedOperation.name,
        parameters: parsed as Record<string, JsonValue>,
      }, controller.signal)
      if (!controller.signal.aborted && executionRequestRef.current === controller) {
        setResponse(nextResponse)
      }
    } catch (error) {
      if (controller.signal.aborted) return
      setExecutionError(error instanceof Error ? error.message : 'The Math Core request could not be completed.')
    } finally {
      if (executionRequestRef.current === controller) {
        executionRequestRef.current = null
        setRunning(false)
      }
    }
  }

  const close = () => {
    catalogRequestRef.current?.abort()
    executionRequestRef.current?.abort()
    setRunning(false)
    onClose()
  }

  return (
    <Dialog open={open} onClose={close} fullWidth maxWidth="lg">
      <DialogTitle sx={{ position: 'absolute', width: 1, height: 1, p: 0, m: -1, overflow: 'hidden', clip: 'rect(0 0 0 0)', whiteSpace: 'nowrap', border: 0 }}>
        Step 2 Math Core
      </DialogTitle>
      <Box sx={{ px: 3, pt: 2.5, pb: 1.5 }}>
        <SectionHeader
          icon={<FunctionsRoundedIcon />}
          title="Step 2 Math Core"
          subtitle="Run bounded reference operations without changing the active model or analysis state."
          action={catalog ? <Chip size="small" variant="outlined" label={`Interface ${catalog.schema_version}`} /> : undefined}
        />
      </Box>
      <DialogContent dividers sx={{ minHeight: 560, p: 2.5 }}>
        {catalogLoading ? (
          <Stack role="status" spacing={1.5} sx={{ minHeight: 500, alignItems: 'center', justifyContent: 'center' }}>
            <CircularProgress size={30} />
            <Typography variant="body2" color="text.secondary">Loading Math Core contracts…</Typography>
          </Stack>
        ) : catalogError ? (
          <Stack spacing={2} sx={{ minHeight: 500, alignItems: 'center', justifyContent: 'center' }}>
            <Alert severity="error" sx={{ width: '100%', maxWidth: 620 }}>{catalogError}</Alert>
            <Button variant="outlined" startIcon={<ReplayRoundedIcon />} onClick={loadCatalog}>Retry loading contracts</Button>
          </Stack>
        ) : selectedCore && selectedOperation ? (
          <Box component="form" noValidate onSubmit={execute} sx={{ display: 'grid', gridTemplateColumns: 'minmax(270px, 0.78fr) minmax(460px, 1.35fr)', gap: 2.5 }}>
            <Stack spacing={2} sx={{ minWidth: 0 }}>
              <TextField select fullWidth label="Mathematical core" value={selectedCoreId} onChange={(event) => selectCore(event.target.value)}>
                {catalog?.cores.map((core) => <MenuItem key={core.core_id} value={core.core_id}>{core.title}</MenuItem>)}
              </TextField>
              <Box>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 0.75, flexWrap: 'wrap' }}>
                  <Typography variant="subtitle2">{selectedCore.title}</Typography>
                  <Chip size="small" label={`Core ${selectedCore.version}`} />
                </Stack>
                <Typography variant="body2" color="text.secondary">{selectedCore.scope}</Typography>
              </Box>
              <TextField select fullWidth label="Operation" value={selectedOperationName} onChange={(event) => selectOperation(event.target.value)}>
                {selectedCore.operations.map((operation) => <MenuItem key={operation.name} value={operation.name}>{operation.name}</MenuItem>)}
              </TextField>
              <Box>
                <Typography variant="body2" sx={{ mb: 1 }}>{selectedOperation.summary}</Typography>
                <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 0.75 }}>
                  {selectedOperation.required_parameters.map((parameter) => <Chip key={parameter} size="small" color="primary" variant="outlined" label={`required · ${parameter}`} />)}
                  {selectedOperation.optional_parameters.map((parameter) => <Chip key={parameter} size="small" variant="outlined" label={`optional · ${parameter}`} />)}
                  {selectedOperation.required_parameters.length === 0 && <Chip size="small" color="success" variant="outlined" label="No parameters required" />}
                </Stack>
              </Box>
              <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2, bgcolor: 'background.containerLow' }}>
                <Typography variant="overline" color="text.secondary">Residual convention</Typography>
                <Typography variant="body2" sx={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace', overflowWrap: 'anywhere' }}>
                  {selectedCore.residual_convention}
                </Typography>
                <Typography variant="overline" color="text.secondary" sx={{ display: 'block', mt: 1.5 }}>State protocol</Typography>
                <Typography variant="body2">{selectedCore.state_protocol}</Typography>
              </Paper>
              <Alert severity="info" variant="outlined">
                {selectedCore.verification_meaning}
              </Alert>
            </Stack>

            <Stack spacing={1.5} sx={{ minWidth: 0 }}>
              <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
                <Box>
                  <Typography variant="subtitle2">Request parameters</Typography>
                  <Typography variant="caption" color="text.secondary">JSON object · server limit {catalog?.limits.max_parameter_values.toLocaleString('en-US')} values</Typography>
                </Box>
                <Button type="button" size="small" color="inherit" startIcon={<ReplayRoundedIcon />} onClick={resetExample}>Reset example</Button>
              </Stack>
              <TextField
                inputRef={editorRef}
                fullWidth
                multiline
                rows={13}
                label="Parameters (JSON)"
                value={parameters}
                error={Boolean(editorError)}
                helperText={editorError ?? 'Edit the executable example or run it as provided.'}
                onChange={(event) => {
                  setParameters(event.target.value)
                  setEditorError(null)
                  setExecutionError(null)
                  setResponse(null)
                }}
                slotProps={{
                  htmlInput: { spellCheck: false, 'aria-describedby': 'math-core-parameters-help' },
                  formHelperText: { id: 'math-core-parameters-help' },
                }}
                sx={{
                  '& textarea': {
                    resize: 'none',
                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                    fontSize: '0.78rem',
                    lineHeight: 1.55,
                  },
                }}
              />
              <Button type="submit" variant="contained" disabled={running} startIcon={running ? <CircularProgress size={17} color="inherit" /> : <FunctionsRoundedIcon />} sx={{ alignSelf: 'flex-start', minWidth: 178 }}>
                {running ? 'Running operation…' : 'Run operation'}
              </Button>
              <Box aria-live="polite" sx={{ minHeight: 190 }}>
                {executionError ? (
                  <Alert severity="error" role="alert">{executionError}</Alert>
                ) : response ? (
                  <Paper variant="outlined" sx={{ overflow: 'hidden', borderRadius: 2 }}>
                    <Stack direction="row" sx={{ px: 1.5, py: 1, alignItems: 'center', justifyContent: 'space-between', bgcolor: 'background.containerLow', borderBottom: '1px solid', borderColor: 'divider' }}>
                      <Typography variant="subtitle2">Response envelope</Typography>
                      <Chip size="small" color={response.status === 'ok' ? 'success' : 'error'} label={response.status === 'ok' ? 'Completed' : response.error?.code ?? 'Error'} />
                    </Stack>
                    {response.status === 'error' && response.error && (
                      <Alert severity="error" square>{response.error.message}</Alert>
                    )}
                    <Box component="pre" sx={{ m: 0, p: 1.5, maxHeight: 260, overflow: 'auto', scrollbarGutter: 'stable', bgcolor: 'background.canvas', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace', fontSize: '0.75rem', lineHeight: 1.55, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
                      {JSON.stringify(response, null, 2)}
                    </Box>
                  </Paper>
                ) : (
                  <Paper variant="outlined" sx={{ borderRadius: 2 }}>
                    <EmptyState icon={<FunctionsRoundedIcon />} title="No operation result yet" body="Run the selected reference operation to inspect its stable response envelope and diagnostics." />
                  </Paper>
                )}
              </Box>
            </Stack>
          </Box>
        ) : (
          <EmptyState icon={<FunctionsRoundedIcon />} title="No Math Core contracts found" body="The server returned an empty Math Core catalog." />
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Typography variant="caption" color="text.secondary" sx={{ mr: 'auto' }}>
          Reference tools only · does not prove stability or design strength
        </Typography>
        <Button color="inherit" onClick={close}>Close</Button>
      </DialogActions>
    </Dialog>
  )
}
