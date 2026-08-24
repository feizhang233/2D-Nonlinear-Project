import AccountTreeRoundedIcon from '@mui/icons-material/AccountTreeRounded'
import AccountCircleRoundedIcon from '@mui/icons-material/AccountCircleRounded'
import ChevronLeftRoundedIcon from '@mui/icons-material/ChevronLeftRounded'
import ChevronRightRoundedIcon from '@mui/icons-material/ChevronRightRounded'
import CodeRoundedIcon from '@mui/icons-material/CodeRounded'
import DownloadRoundedIcon from '@mui/icons-material/DownloadRounded'
import HelpOutlineRoundedIcon from '@mui/icons-material/HelpOutlineRounded'
import HistoryRoundedIcon from '@mui/icons-material/HistoryRounded'
import LogoutRoundedIcon from '@mui/icons-material/LogoutRounded'
import MoreVertRoundedIcon from '@mui/icons-material/MoreVertRounded'
import PlayArrowRoundedIcon from '@mui/icons-material/PlayArrowRounded'
import RestartAltRoundedIcon from '@mui/icons-material/RestartAltRounded'
import SaveRoundedIcon from '@mui/icons-material/SaveRounded'
import StopCircleRoundedIcon from '@mui/icons-material/StopCircleRounded'
import TuneRoundedIcon from '@mui/icons-material/TuneRounded'
import UploadFileRoundedIcon from '@mui/icons-material/UploadFileRounded'
import Alert from '@mui/material/Alert'
import AppBar from '@mui/material/AppBar'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import IconButton from '@mui/material/IconButton'
import LinearProgress from '@mui/material/LinearProgress'
import Menu from '@mui/material/Menu'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Snackbar from '@mui/material/Snackbar'
import Stack from '@mui/material/Stack'
import Tab from '@mui/material/Tab'
import Tabs from '@mui/material/Tabs'
import TextField from '@mui/material/TextField'
import Toolbar from '@mui/material/Toolbar'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import { useCallback, useEffect, useReducer, useRef, useState, type ChangeEvent, type MouseEvent } from 'react'
import { cancelAnalysis, generateSurfaceMesh, getAnalysis, runAnalysis, StudioApiError, validateModel } from './api'
import { AnalysisPanel } from './components/AnalysisPanel'
import { AuthDialog, type AuthDialogMode } from './components/AuthDialog'
import { GeometryPanel } from './components/GeometryPanel'
import { GettingStartedDialog } from './components/GettingStartedDialog'
import { ModelCanvas } from './components/ModelCanvas'
import { ModelNavigator } from './components/ModelNavigator'
import { ModelHistoryDialog } from './components/ModelHistoryDialog'
import { PropertyPanel } from './components/PropertyPanel'
import { ResultsDock } from './components/ResultsDock'
import { WorkflowBar, type WorkflowStep } from './components/WorkflowBar'
import type { AnalysisRecord, AnalysisRestart, ModelFamily, ModelInput, RestartBundle, RunOptions, Selection } from './domain'
import { modelDisplayLabel } from './entityLabels'
import { CadTool, geometryNeedsMesh, PlacementState } from './geometrySketch'
import { useIdentity } from './hooks/useIdentity'
import { useModelHistory } from './hooks/useModelHistory'
import { defaultRunOptions, dofsForModel, MODEL_FAMILIES, MODEL_FAMILY_ORDER } from './modelFamilies'
import { applySurfaceMesh, meshSizeForModel } from './meshing'
import { cloneSampleModel } from './sampleModel'
import { initialStudioState, studioReducer } from './state'
import { addNodalLoadAtNode, addSupportAtNode, moveSupportToNode } from './supports'

interface Toast { message: string; severity: 'success' | 'info' | 'warning' | 'error' }

const CONTROL_LABELS = { load: 'Load control', displacement: 'Displacement control', arc_length: 'Arc-length control' } as const
const GUIDE_STORAGE_KEY = 'nonlinear-studio-guide-hidden-v2'

const isModelDocument = (value: unknown): value is ModelInput => {
  if (!value || typeof value !== 'object') return false
  const record = value as Record<string, unknown>
  return record.schema_version === '1.0.0' && MODEL_FAMILY_ORDER.includes(record.model_family as ModelFamily)
    && Array.isArray(record.nodes) && Array.isArray(record.elements) && Array.isArray(record.materials)
    && typeof record.analysis === 'object'
}

const isAnalysisRestart = (value: unknown): value is AnalysisRestart => {
  if (!value || typeof value !== 'object') return false
  const record = value as Record<string, unknown>
  return record.restart_schema_version === '1.0.0'
    && Boolean(record.committed_state) && typeof record.committed_state === 'object'
}

const isRestartBundle = (value: unknown): value is RestartBundle => {
  if (!value || typeof value !== 'object') return false
  const record = value as Record<string, unknown>
  return record.restart_bundle_schema_version === '1.0.0'
    && isModelDocument(record.model) && isAnalysisRestart(record.restart)
}

const waitForPoll = (signal: AbortSignal, milliseconds = 120) => new Promise<void>((resolve, reject) => {
  const timeout = window.setTimeout(resolve, milliseconds)
  signal.addEventListener('abort', () => {
    window.clearTimeout(timeout)
    reject(new DOMException('analysis polling aborted', 'AbortError'))
  }, { once: true })
})

export default function App() {
  const [state, dispatch] = useReducer(studioReducer, undefined, initialStudioState)
  const [toast, setToast] = useState<Toast | null>(null)
  const showMessage = useCallback((message: string, severity: Toast['severity']) => {
    setToast({ message, severity })
  }, [])
  const [meshing, setMeshing] = useState(false)
  const [workflowExpanded, setWorkflowExpanded] = useState(true)
  const [propertiesCollapsed, setPropertiesCollapsed] = useState(false)
  const [guideOpen, setGuideOpen] = useState(() => {
    try {
      return window.localStorage.getItem(GUIDE_STORAGE_KEY) !== 'true'
    } catch {
      return true
    }
  })
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null)
  const [accountAnchor, setAccountAnchor] = useState<HTMLElement | null>(null)
  const [authOpen, setAuthOpen] = useState(false)
  const [authMode, setAuthMode] = useState<AuthDialogMode>('login')
  const [authReason, setAuthReason] = useState<'save' | 'history' | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [cadTool, setCadTool] = useState<CadTool>('select')
  const [placement, setPlacement] = useState<PlacementState>(null)
  const [pendingMember, setPendingMember] = useState<string | null>(null)
  const pendingAuthActionRef = useRef<'save' | 'history' | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const meshAbortRef = useRef<AbortController | null>(null)
  const analysisIdRef = useRef<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const fileReadTokenRef = useRef(0)
  const identity = useIdentity(showMessage)
  const handleSessionExpired = useCallback(() => {
    identity.sessionExpired()
    setHistoryOpen(false)
    setAuthMode('login')
    setAuthReason('history')
    setAuthOpen(true)
  }, [identity.sessionExpired])
  const modelHistory = useModelHistory(identity.currentUser, {
    showMessage,
    onSessionExpired: handleSessionExpired,
  })

  const changeModel = useCallback((model: ModelInput, selection?: Selection, restart: AnalysisRestart | null = null, runOptions?: RunOptions) => {
    if (analysisIdRef.current) void cancelAnalysis(analysisIdRef.current).catch(() => undefined)
    analysisIdRef.current = null
    abortRef.current?.abort()
    abortRef.current = null
    meshAbortRef.current?.abort()
    meshAbortRef.current = null
    setMeshing(false)
    fileReadTokenRef.current += 1
    dispatch({ type: 'modelChanged', model, selection, restart, runOptions })
  }, [])

  const openAuth = useCallback((reason: 'save' | 'history' | null = null, mode: AuthDialogMode = 'login') => {
    setAuthReason(reason)
    setAuthMode(mode)
    setAuthOpen(true)
  }, [])

  const saveCurrentModel = useCallback(() => {
    if (!identity.currentUser) {
      openAuth('save')
      return
    }
    void modelHistory.save(state.model)
  }, [identity.currentUser, modelHistory.save, openAuth, state.model])

  const openModelHistory = useCallback(() => {
    if (!identity.currentUser) {
      openAuth('history')
      return
    }
    setHistoryOpen(true)
  }, [identity.currentUser, openAuth])

  useEffect(() => {
    if (!identity.currentUser || !pendingAuthActionRef.current) return
    const action = pendingAuthActionRef.current
    pendingAuthActionRef.current = null
    if (action === 'save') void modelHistory.save(state.model)
    else setHistoryOpen(true)
  }, [identity.currentUser, modelHistory.save, state.model])

  const handleGenerateMesh = useCallback(async () => {
    meshAbortRef.current?.abort()
    const controller = new AbortController()
    meshAbortRef.current = controller
    const revision = state.modelRevision
    setMeshing(true)
    try {
      const response = await generateSurfaceMesh(
        state.model,
        meshSizeForModel(state.model),
        controller.signal,
      )
      if (controller.signal.aborted || meshAbortRef.current !== controller
        || revision !== state.modelRevision) return
      meshAbortRef.current = null
      setMeshing(false)
      const nextModel = applySurfaceMesh(state.model, response)
      changeModel(nextModel, { kind: 'mesh' })
      setToast({
        severity: 'success',
        message: `Gmsh mesh generated: ${response.nodes.length} nodes / ${response.elements.length} Q4 elements`,
      })
    } catch (error) {
      if (controller.signal.aborted || (error instanceof DOMException && error.name === 'AbortError')) return
      if (meshAbortRef.current !== controller) return
      meshAbortRef.current = null
      setMeshing(false)
      setToast({ severity: 'error', message: error instanceof Error ? error.message : 'Gmsh mesh generation failed' })
    }
  }, [changeModel, state.model, state.modelRevision])

  useEffect(() => {
    document.title = `${MODEL_FAMILIES[state.model.model_family].shortLabel} — Nonlinear Studio`
  }, [state.model.model_family])

  const loadFamilySample = (family: ModelFamily) => {
    setCadTool('select')
    setPlacement(null)
    setPendingMember(null)
    changeModel(cloneSampleModel(family), { kind: 'model' }, null, defaultRunOptions(family))
    setToast({ severity: 'info', message: `${MODEL_FAMILIES[family].label} verification example loaded` })
  }

  const handlePlace = (nodeId: string) => {
    if (!placement || !nodeId) return
    if (placement.kind === 'support') {
      if (placement.targetId) {
        changeModel(moveSupportToNode(state.model, placement.targetId, nodeId), { kind: 'constraints', id: nodeId })
      } else if (state.model.constraints.some((item) => item.node_id === nodeId)) {
        changeModel(state.model, { kind: 'constraints', id: nodeId })
      } else {
        changeModel(addSupportAtNode(state.model, nodeId, dofsForModel(state.model)), { kind: 'constraints', id: nodeId })
      }
    } else if (placement.targetId) {
      const next = structuredClone(state.model)
      const load = next.loads.find((item) => item.id === placement.targetId)
      if (load) {
        load.kind = 'nodal'
        load.node_id = nodeId
      }
      changeModel(next, { kind: 'loads', id: placement.targetId })
    } else {
      const info = MODEL_FAMILIES[state.model.model_family]
      const added = addNodalLoadAtNode(state.model, nodeId, info.primaryLoadDof, info.primaryLoadDof === 'UX' ? 1 : -1)
      changeModel(added.model, { kind: 'loads', id: added.id })
    }
    setPlacement(null)
  }

  const handleRun = useCallback(async () => {
    if (geometryNeedsMesh(state.model)) {
      setToast({ severity: 'warning', message: 'Geometry changed. Generate a new mesh before solving.' })
      dispatch({ type: 'selectionChanged', selection: { kind: 'mesh' } })
      return
    }
    if (analysisIdRef.current) void cancelAnalysis(analysisIdRef.current).catch(() => undefined)
    analysisIdRef.current = null
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const revision = state.modelRevision
    dispatch({ type: 'analysisStarted' })
    try {
      const validation = await validateModel(state.model, controller.signal)
      if (!validation.valid || !validation.execution_eligible) {
        const first = validation.errors?.[0]
        throw new StudioApiError(first ? `${first.json_path}: ${first.message}` : 'The model did not pass analysis validation', 'MODEL_VALIDATION_FAILED')
      }
      let record = await runAnalysis(state.model, state.runOptions, state.restart, controller.signal)
      analysisIdRef.current = record.analysis_id
      while (record.status === 'queued' || record.status === 'running') {
        dispatch({ type: 'analysisProgressed', record, revision })
        await waitForPoll(controller.signal)
        record = await getAnalysis(record.analysis_id, controller.signal)
      }
      if (controller.signal.aborted || abortRef.current !== controller) return
      abortRef.current = null
      analysisIdRef.current = null
      if (record.status === 'succeeded') {
        dispatch({ type: 'analysisSucceeded', record, revision })
        const acceptedSteps = record.progress.accepted_steps
        setToast({ severity: 'success', message: `Analysis complete: ${acceptedSteps} accepted ${acceptedSteps === 1 ? 'step' : 'steps'}` })
      } else if (record.status === 'cancelled') {
        dispatch({ type: 'analysisCancelled' })
        setToast({ severity: 'info', message: 'Analysis cancelled; uncommitted trial output was discarded' })
      } else {
        dispatch({ type: 'analysisFailed', message: record.error?.message ?? 'Nonlinear analysis failed', record, revision })
        setToast({ severity: 'error', message: `${record.error?.code ?? 'FAILED'}: ${record.error?.message ?? 'Review the failure evidence'}` })
      }
    } catch (error) {
      if (controller.signal.aborted || (error instanceof DOMException && error.name === 'AbortError')) return
      if (abortRef.current !== controller) return
      abortRef.current = null
      const message = error instanceof Error ? error.message : 'The analysis request could not be completed'
      dispatch({ type: 'analysisFailed', message, revision })
      setToast({ severity: 'error', message })
    }
  }, [state.model, state.modelRevision, state.restart, state.runOptions])

  const handleCancel = useCallback(() => {
    const analysisId = analysisIdRef.current
    if (analysisId) void cancelAnalysis(analysisId).catch(() => undefined)
    analysisIdRef.current = null
    abortRef.current?.abort()
    abortRef.current = null
    dispatch({ type: 'analysisCancelled' })
    setToast({ severity: 'info', message: 'Cancellation requested' })
  }, [])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setPlacement(null)
        setCadTool('select')
        setPendingMember(null)
        return
      }
      if (!(event.metaKey || event.ctrlKey) || event.key !== 'Enter') return
      event.preventDefault()
      if (state.analysisState === 'running') handleCancel()
      else void handleRun()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [handleCancel, handleRun, state.analysisState])

  const handleFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    const readToken = fileReadTokenRef.current + 1
    fileReadTokenRef.current = readToken
    try {
      if (file.size > 10 * 1024 * 1024) throw new Error('JSON files must be 10 MB or smaller')
      const parsed = JSON.parse(await file.text()) as unknown
      if (fileReadTokenRef.current !== readToken) return
      const importedModel = isRestartBundle(parsed) ? parsed.model : parsed
      const importedRestart = isRestartBundle(parsed) ? parsed.restart : null
      if (!isModelDocument(importedModel)) throw new Error('This is not a version 1.0.0 Frame, Continuum, Plate, or Shell model/restart bundle')
      const defaults = cloneSampleModel(importedModel.model_family)
      const normalized: ModelInput = {
        ...importedModel,
        loads: Array.isArray(importedModel.loads) ? importedModel.loads : [],
        constraints: Array.isArray(importedModel.constraints) ? importedModel.constraints : [],
        analysis: {
          ...defaults.analysis,
          ...importedModel.analysis,
          tolerances: { ...defaults.analysis.tolerances, ...importedModel.analysis.tolerances },
          step_control: { ...defaults.analysis.step_control, ...importedModel.analysis.step_control },
          line_search: { ...defaults.analysis.line_search, ...importedModel.analysis.line_search },
        },
      }
      changeModel(normalized, { kind: 'model' }, importedRestart, defaultRunOptions(normalized.model_family))
      setToast({ severity: 'success', message: importedRestart ? `Restart bundle imported: ${file.name}` : `Imported ${file.name}` })
    } catch (error) {
      setToast({ severity: 'error', message: error instanceof Error ? error.message : 'JSON import failed' })
    }
  }

  const exportModel = () => {
    const blob = new Blob([`${JSON.stringify(state.model, null, 2)}\n`], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${state.model.model_id || 'nonlinear-model'}.json`
    anchor.click()
    URL.revokeObjectURL(url)
    setToast({ severity: 'success', message: 'Model JSON exported' })
  }

  const resultRestart = state.record?.result?.metadata.restart
  const availableRestart = isAnalysisRestart(resultRestart) ? resultRestart : state.restart
  const exportRestart = () => {
    if (!availableRestart) return
    const bundle: RestartBundle = {
      restart_bundle_schema_version: '1.0.0',
      model: state.model,
      restart: availableRestart,
    }
    const blob = new Blob([`${JSON.stringify(bundle, null, 2)}\n`], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${state.model.model_id || 'nonlinear-model'}-restart.json`
    anchor.click()
    URL.revokeObjectURL(url)
    setToast({ severity: 'success', message: 'Verifiable restart bundle exported' })
  }

  const currentStatus = state.analysisState === 'running'
    ? { label: 'Running', color: 'primary' as const }
    : state.analysisState === 'succeeded'
      ? { label: 'Results current', color: 'success' as const }
      : state.analysisState === 'failed'
        ? { label: 'Review required', color: 'error' as const }
        : state.resultInvalidated
          ? { label: 'Results invalidated', color: 'warning' as const }
          : { label: 'Ready', color: 'default' as const }

  const family = MODEL_FAMILIES[state.model.model_family]
  const closeMenu = () => setMenuAnchor(null)
  const activeWorkflowStep: WorkflowStep = state.inspectorTab === 'analysis'
    ? 'solve'
    : state.selection.kind === 'materials'
      ? 'materials'
      : state.selection.kind === 'constraints'
        ? 'supports'
        : state.selection.kind === 'loads'
          ? 'loads'
          : state.selection.kind === 'mesh'
            ? 'mesh'
            : 'model'

  const openWorkflowStep = (step: WorkflowStep) => {
    if (step === 'solve') {
      dispatch({ type: 'inspectorTabChanged', tab: 'analysis' })
      return
    }
    if (step === 'model') dispatch({ type: 'selectionChanged', selection: { kind: 'model' } })
    if (step === 'materials') dispatch({ type: 'selectionChanged', selection: { kind: 'materials', id: state.model.materials[0]?.id } })
    if (step === 'supports') dispatch({ type: 'selectionChanged', selection: { kind: 'constraints', id: state.model.constraints[0]?.node_id } })
    if (step === 'loads') dispatch({ type: 'selectionChanged', selection: { kind: 'loads', id: state.model.loads[0]?.id } })
    if (step === 'mesh') dispatch({ type: 'selectionChanged', selection: { kind: 'mesh' } })
  }

  const hideGuide = () => {
    try {
      window.localStorage.setItem(GUIDE_STORAGE_KEY, 'true')
    } catch {
      // Private browsing or a restricted test environment may disable storage.
    }
    setGuideOpen(false)
  }

  return (
    <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column', bgcolor: 'background.default' }}>
      <AppBar position="static" sx={{ zIndex: 4, bgcolor: 'background.paper', borderBottom: '1px solid', borderColor: 'divider' }}>
        <Toolbar disableGutters sx={{ px: 2, gap: 1.5 }}>
          <Box sx={{ width: 40, height: 40, borderRadius: 2.5, display: 'grid', placeItems: 'center', bgcolor: 'primary.main', color: 'primary.contrastText' }}>
            <AccountTreeRoundedIcon />
          </Box>
          <Box sx={{ minWidth: 196, flexShrink: 0 }}>
            <Typography variant="h6">Nonlinear Studio</Typography>
            <Typography variant="caption" color="text.secondary">Quasi-static nonlinear FEM workbench</Typography>
          </Box>
          <Box sx={{ flex: 1 }} />
          <input ref={fileInputRef} type="file" accept="application/json,.json" hidden onChange={handleFile} />
          <Button variant="text" startIcon={<UploadFileRoundedIcon />} onClick={() => fileInputRef.current?.click()}>Import</Button>
          <Button variant="text" startIcon={<DownloadRoundedIcon />} onClick={exportModel}>Export</Button>
          <Button variant="text" startIcon={modelHistory.saving ? <CircularProgress size={17} /> : <SaveRoundedIcon />} disabled={modelHistory.saving || identity.loading} onClick={saveCurrentModel}>
            {modelHistory.saving ? 'Saving…' : 'Save'}
          </Button>
          <Button variant="text" startIcon={<HistoryRoundedIcon />} disabled={identity.loading} onClick={openModelHistory}>History</Button>
          <Tooltip title="More actions">
            <IconButton aria-label="More actions" onClick={(event: MouseEvent<HTMLElement>) => setMenuAnchor(event.currentTarget)}>
              <MoreVertRoundedIcon />
            </IconButton>
          </Tooltip>
          <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={closeMenu} anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} transformOrigin={{ vertical: 'top', horizontal: 'right' }}>
            <MenuItem disabled={!availableRestart} onClick={() => { exportRestart(); closeMenu() }}>Export restart bundle</MenuItem>
            <MenuItem onClick={() => { loadFamilySample(state.model.model_family); closeMenu() }}>Reset current family example</MenuItem>
          </Menu>
          <Tooltip title="Getting started guide">
            <IconButton aria-label="Guide" onClick={() => setGuideOpen(true)}>
              <HelpOutlineRoundedIcon />
            </IconButton>
          </Tooltip>
          <Button
            variant="outlined"
            startIcon={identity.loading ? <CircularProgress size={17} /> : <AccountCircleRoundedIcon />}
            disabled={identity.loading}
            aria-label={identity.currentUser ? `Account for ${identity.currentUser.display_name}` : 'Guest account'}
            onClick={(event) => {
              if (identity.currentUser) setAccountAnchor(event.currentTarget)
              else openAuth()
            }}
          >
            {identity.loading ? 'Account' : identity.currentUser?.display_name ?? 'Guest'}
          </Button>
          <Menu
            anchorEl={accountAnchor}
            open={Boolean(accountAnchor)}
            onClose={() => setAccountAnchor(null)}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            transformOrigin={{ vertical: 'top', horizontal: 'right' }}
          >
            {identity.currentUser && (
              <Box sx={{ px: 2, py: 1, maxWidth: 260 }}>
                <Typography variant="subtitle2" noWrap>{identity.currentUser.display_name}</Typography>
                <Typography variant="caption" color="text.secondary" noWrap>{identity.currentUser.email}</Typography>
              </Box>
            )}
            <Divider />
            <MenuItem onClick={() => { setAccountAnchor(null); void identity.signOut().then((signedOut) => { if (signedOut) setHistoryOpen(false) }) }}>
              <LogoutRoundedIcon fontSize="small" sx={{ mr: 1.25 }} /> Sign out
            </MenuItem>
          </Menu>
          <Button
            color={state.analysisState === 'running' ? 'error' : 'primary'}
            variant="contained"
            size="large"
            title={state.analysisState === 'running' ? 'Cancel analysis (Ctrl / ⌘ + Enter)' : 'Run analysis (Ctrl / ⌘ + Enter)'}
            startIcon={state.analysisState === 'running' ? <StopCircleRoundedIcon /> : <PlayArrowRoundedIcon />}
            onClick={state.analysisState === 'running' ? handleCancel : handleRun}
          >
            {state.analysisState === 'running' ? 'Cancel analysis' : 'Run analysis'}
          </Button>
        </Toolbar>
        <Stack
          direction="row"
          spacing={1.5}
          sx={{
            alignItems: 'center',
            px: 2,
            py: 1,
            bgcolor: 'background.containerLow',
            borderTop: '1px solid',
            borderColor: 'divider',
            minHeight: 64,
          }}
        >
          <TextField
            select
            size="small"
            label="Model family"
            value={state.model.model_family}
            onChange={(event) => loadFamilySample(event.target.value as ModelFamily)}
            sx={{ minWidth: 188, flexShrink: 0 }}
          >
            {MODEL_FAMILY_ORDER.map((item) => (
              <MenuItem key={item} value={item}>{MODEL_FAMILIES[item].label}</MenuItem>
            ))}
          </TextField>
          <Box sx={{ minWidth: 140, flex: 1 }}>
            <Typography variant="body2" noWrap sx={{ fontWeight: 500 }}>{state.model.name}</Typography>
            <Typography variant="caption" color="text.secondary">
              {modelDisplayLabel()} · revision {state.modelRevision}
            </Typography>
          </Box>
          <Chip size="small" variant="outlined" label={CONTROL_LABELS[state.model.analysis.control_method]} />
          <Chip size="small" variant="outlined" label={dofsForModel(state.model).join(' / ')} />
          <Chip size="small" color={currentStatus.color} label={currentStatus.label} />
          {state.restart && (
            <Chip size="small" color="info" variant="outlined" label={`Restart step ${String(state.restart.committed_state.step_index ?? '—')}`} />
          )}
        </Stack>
        {state.analysisState === 'running' && <LinearProgress />}
      </AppBar>

      <WorkflowBar
        model={state.model}
        analysisState={state.analysisState}
        activeStep={activeWorkflowStep}
        expanded={workflowExpanded}
        onStepChange={openWorkflowStep}
        onExpandedChange={setWorkflowExpanded}
      />

      <Box sx={{ flex: 1, minHeight: 0, display: 'flex', gap: 1.25, p: 1.25 }}>
        <Paper
          component="aside"
          aria-label="Model and properties workspace"
          sx={{
            width: propertiesCollapsed ? 308 : 600,
            minWidth: propertiesCollapsed ? 308 : 600,
            minHeight: 0,
            overflow: 'hidden',
            display: 'flex',
            border: '1px solid',
            borderColor: 'divider',
            transition: 'width 180ms ease, min-width 180ms ease',
          }}
        >
          <Box sx={{ width: 260, minWidth: 260, overflow: 'hidden', display: 'flex', flexDirection: 'column', borderRight: '1px solid', borderColor: 'divider' }}>
            <GeometryPanel
              model={state.model}
              selection={state.selection}
              cadTool={cadTool}
              onCadToolChange={(tool) => {
                setCadTool(tool)
                setPlacement(null)
                setPendingMember(null)
              }}
              onSelection={(selection) => dispatch({ type: 'selectionChanged', selection })}
              onModelChange={changeModel}
            />
            <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
              <ModelNavigator
                model={state.model}
                selection={state.selection}
                onSelection={(selection) => dispatch({ type: 'selectionChanged', selection })}
                onModelChange={changeModel}
                onEntityDoubleClick={() => setPropertiesCollapsed(true)}
              />
            </Box>
          </Box>

          {propertiesCollapsed ? (
            <Button
              aria-label="Expand Properties"
              onClick={() => setPropertiesCollapsed(false)}
              sx={{
                width: 48,
                minWidth: 48,
                height: '100%',
                borderRadius: 0,
                px: 0,
                py: 1.5,
                flexDirection: 'column',
                justifyContent: 'flex-start',
                gap: 1,
                borderLeft: '1px solid',
                borderColor: 'divider',
                color: 'text.secondary',
              }}
            >
              <ChevronRightRoundedIcon />
              <Typography variant="caption" sx={{ fontWeight: 700, writingMode: 'vertical-rl', transform: 'rotate(180deg)', letterSpacing: 0.8 }}>
                Properties
              </Typography>
            </Button>
          ) : (
            <Box sx={{ width: 340, minWidth: 0, display: 'flex', flexDirection: 'column', minHeight: 0, bgcolor: 'background.paper' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', borderBottom: '1px solid', borderColor: 'divider' }}>
                <Tabs
                  value={state.inspectorTab}
                  onChange={(_, tab: 'properties' | 'analysis') => dispatch({ type: 'inspectorTabChanged', tab })}
                  variant="fullWidth"
                  aria-label="Workspace panels"
                  sx={{ minHeight: 48, pl: 1, flex: 1 }}
                >
                  <Tab value="properties" icon={<CodeRoundedIcon />} iconPosition="start" label="Properties" />
                  <Tab value="analysis" icon={<TuneRoundedIcon />} iconPosition="start" label="Analysis" />
                </Tabs>
                <Tooltip title="Collapse Properties">
                  <IconButton aria-label="Collapse Properties" size="small" onClick={() => setPropertiesCollapsed(true)} sx={{ mr: 0.75 }}>
                    <ChevronLeftRoundedIcon />
                  </IconButton>
                </Tooltip>
              </Box>
              <Box sx={{ p: 2, overflow: 'auto', flex: 1, scrollbarGutter: 'stable' }}>
                {state.inspectorTab === 'properties'
                  ? <PropertyPanel
                      model={state.model}
                      selection={state.selection}
                      onChange={changeModel}
                      onGenerateMesh={handleGenerateMesh}
                      meshing={meshing}
                      meshDisabled={state.analysisState === 'running'}
                      placement={placement}
                      onStartPlacement={(next) => {
                        setPlacement(next)
                        setCadTool('select')
                        setPendingMember(null)
                      }}
                      onCancelPlacement={() => setPlacement(null)}
                    />
                  : <AnalysisPanel model={state.model} runOptions={state.runOptions} onModelChange={changeModel} onRunOptionsChange={(options) => dispatch({ type: 'runOptionsChanged', options })} />}
              </Box>
              {state.resultInvalidated && (
                <Alert severity="warning" square sx={{ borderTop: '1px solid', borderColor: 'warning.light' }}>
                  The model changed; previous results were cleared.
                </Alert>
              )}
            </Box>
          )}
        </Paper>

        <Paper component="main" aria-label="Model space and results" sx={{ flex: 1, minWidth: 0, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden', border: '1px solid', borderColor: 'divider' }}>
          <Box sx={{ flex: 1, minHeight: 0 }}>
            <ModelCanvas
              model={state.model}
              result={state.record?.result ?? null}
              selectedStep={state.selectedStep}
              view={state.resultView}
              selection={state.selection}
              cadTool={cadTool}
              placement={placement}
              pendingMember={pendingMember}
              onViewChange={(view) => {
                dispatch({ type: 'resultViewChanged', view })
                if ((view === 'reactions' || view === 'internal') && state.record?.result?.steps.length) {
                  dispatch({ type: 'stepChanged', step: state.record.result.steps.length - 1 })
                }
              }}
              onSelection={(selection) => dispatch({ type: 'selectionChanged', selection })}
              onModelChange={changeModel}
              onPlace={handlePlace}
              onPendingMember={setPendingMember}
            />
          </Box>
          <ResultsDock
            model={state.model}
            record={state.record}
            state={state.analysisState}
            error={state.error}
            invalidated={state.resultInvalidated}
            tab={state.resultTab}
            selectedStep={state.selectedStep}
            onTabChange={(tab) => dispatch({ type: 'resultTabChanged', tab })}
            onStepChange={(step) => dispatch({ type: 'stepChanged', step })}
          />
        </Paper>
      </Box>

      <Snackbar open={toast !== null} autoHideDuration={4200} onClose={() => setToast(null)}>
        {toast ? <Alert severity={toast.severity} variant="filled" onClose={() => setToast(null)} sx={{ borderRadius: 3 }}>{toast.message}</Alert> : undefined}
      </Snackbar>
      <GettingStartedDialog
        open={guideOpen}
        currentFamily={state.model.model_family}
        onClose={() => setGuideOpen(false)}
        onDoNotShowAgain={hideGuide}
        onOpenStep={openWorkflowStep}
        onChooseFamily={loadFamilySample}
      />
      <AuthDialog
        open={authOpen}
        initialMode={authMode}
        reason={authReason}
        onClose={() => { setAuthOpen(false); setAuthReason(null) }}
        onAuthenticated={(user, isNewAccount) => {
          pendingAuthActionRef.current = authReason
          identity.authenticated(user, isNewAccount)
          setAuthOpen(false)
          setAuthReason(null)
        }}
      />
      {identity.currentUser && (
        <ModelHistoryDialog
          open={historyOpen}
          user={identity.currentUser}
          entries={modelHistory.entries}
          loading={modelHistory.loading}
          saving={modelHistory.saving}
          deletingId={modelHistory.deletingId}
          onClose={() => setHistoryOpen(false)}
          onSave={saveCurrentModel}
          onOpen={(entry) => {
            changeModel(structuredClone(entry.model), { kind: 'model' }, null, defaultRunOptions(entry.model.model_family))
            setHistoryOpen(false)
            showMessage(`Opened “${entry.name}” from model history.`, 'success')
          }}
          onDelete={modelHistory.remove}
        />
      )}
    </Box>
  )
}
