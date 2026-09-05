import AccountCircleRoundedIcon from '@mui/icons-material/AccountCircleRounded'
import AccountTreeRoundedIcon from '@mui/icons-material/AccountTreeRounded'
import ChevronLeftRoundedIcon from '@mui/icons-material/ChevronLeftRounded'
import ChevronRightRoundedIcon from '@mui/icons-material/ChevronRightRounded'
import CodeRoundedIcon from '@mui/icons-material/CodeRounded'
import DownloadRoundedIcon from '@mui/icons-material/DownloadRounded'
import FunctionsRoundedIcon from '@mui/icons-material/FunctionsRounded'
import HelpOutlineRoundedIcon from '@mui/icons-material/HelpOutlineRounded'
import HistoryRoundedIcon from '@mui/icons-material/HistoryRounded'
import LogoutRoundedIcon from '@mui/icons-material/LogoutRounded'
import MoreVertRoundedIcon from '@mui/icons-material/MoreVertRounded'
import PlayArrowRoundedIcon from '@mui/icons-material/PlayArrowRounded'
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
import Snackbar from '@mui/material/Snackbar'
import Stack from '@mui/material/Stack'
import Tab from '@mui/material/Tab'
import Tabs from '@mui/material/Tabs'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import Toolbar from '@mui/material/Toolbar'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import { useCallback, useEffect, useMemo, useReducer, useRef, useState, type ChangeEvent, type MouseEvent } from 'react'
import { cancelAnalysis, generateSurfaceMesh, getAnalysis, runAnalysis, StudioApiError, validateModel } from './api'
import { waitForPoll } from './asyncTasks'
import { AnalysisPanel } from './components/AnalysisPanel'
import { AuthDialog, type AuthDialogMode } from './components/AuthDialog'
import { DraftActionBar } from './components/DraftActionBar'
import { GeometryPanel } from './components/GeometryPanel'
import { GettingStartedDialog } from './components/GettingStartedDialog'
import { ModelCanvas } from './components/ModelCanvas'
import { ModelHistoryDialog } from './components/ModelHistoryDialog'
import { MathCoreDialog } from './components/MathCoreDialog'
import { ModelNavigator } from './components/ModelNavigator'
import { PropertyPanel } from './components/PropertyPanel'
import { ResultsWorkspace } from './components/ResultsWorkspace'
import { UnsavedChangesDialog } from './components/UnsavedChangesDialog'
import { WorkflowBar, type WorkflowStep } from './components/WorkflowBar'
import { WorkspaceSwitcher } from './components/WorkspaceSwitcher'
import type { AnalysisRestart, ModelFamily, ModelInput, RestartBundle, RunOptions, Selection } from './domain'
import { CadTool, geometryNeedsMesh, PlacementState } from './geometrySketch'
import { useIdentity } from './hooks/useIdentity'
import { useModelHistory } from './hooks/useModelHistory'
import { defaultRunOptions, dofsForModel, MODEL_FAMILIES, MODEL_FAMILY_ORDER } from './modelFamilies'
import { applySurfaceMesh, meshSizeForModel } from './meshing'
import { cloneSampleModel } from './sampleModel'
import {
  activeWorkspace,
  editingModel,
  editingRunOptions,
  initialStudioState,
  studioReducer,
  workspaceHasDraft,
  type StudioMode,
} from './state'
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

export default function App() {
  const [state, dispatch] = useReducer(studioReducer, undefined, initialStudioState)
  const workspace = activeWorkspace(state)
  const model = editingModel(workspace)
  const runOptions = editingRunOptions(workspace)
  const hasDraft = workspaceHasDraft(workspace)
  const [toast, setToast] = useState<Toast | null>(null)
  const [meshing, setMeshing] = useState(false)
  const [meshError, setMeshError] = useState<string | null>(null)
  const [cancelling, setCancelling] = useState(false)
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
  const [mathCoreOpen, setMathCoreOpen] = useState(false)
  const [cadTool, setCadTool] = useState<CadTool>('select')
  const [placement, setPlacement] = useState<PlacementState>(null)
  const [pendingMember, setPendingMember] = useState<string | null>(null)
  const [pendingDestination, setPendingDestination] = useState('another workspace')
  const [unsavedDialogOpen, setUnsavedDialogOpen] = useState(false)
  const pendingNavigationRef = useRef<(() => void) | null>(null)
  const pendingAuthActionRef = useRef<'save' | 'history' | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const meshAbortRef = useRef<AbortController | null>(null)
  const analysisIdRef = useRef<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const fileReadTokenRef = useRef(0)

  const showMessage = useCallback((message: string, severity: Toast['severity']) => {
    setToast({ message, severity })
  }, [])
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

  const resetEditTools = useCallback(() => {
    setCadTool('select')
    setPlacement(null)
    setPendingMember(null)
  }, [])

  const stopActiveTasks = useCallback((family: ModelFamily, cancelRunning: boolean) => {
    if (analysisIdRef.current) void cancelAnalysis(analysisIdRef.current).catch((error: unknown) => {
      showMessage(`The previous analysis could not be cancelled: ${error instanceof Error ? error.message : 'connection failed'}. Server completion is unknown.`, 'warning')
    })
    analysisIdRef.current = null
    abortRef.current?.abort()
    abortRef.current = null
    meshAbortRef.current?.abort()
    meshAbortRef.current = null
    setMeshing(false)
    setMeshError(null)
    setCancelling(false)
    fileReadTokenRef.current += 1
    if (cancelRunning) dispatch({ type: 'analysisCancelled', family })
  }, [showMessage])

  useEffect(() => () => {
    abortRef.current?.abort()
    meshAbortRef.current?.abort()
    if (analysisIdRef.current) void cancelAnalysis(analysisIdRef.current).catch(() => undefined)
  }, [])

  const replaceDocument = useCallback((nextModel: ModelInput, selection?: Selection, restart: AnalysisRestart | null = null, nextRunOptions?: RunOptions) => {
    stopActiveTasks(state.activeFamily, workspace.analysisState === 'running')
    resetEditTools()
    dispatch({ type: 'documentReplaced', model: nextModel, selection, restart, runOptions: nextRunOptions })
  }, [resetEditTools, state.activeFamily, stopActiveTasks, workspace.analysisState])

  const stageModelChange = useCallback((nextModel: ModelInput, selection?: Selection) => {
    if (workspace.analysisState === 'running') stopActiveTasks(state.activeFamily, true)
    meshAbortRef.current?.abort()
    meshAbortRef.current = null
    setMeshing(false)
    fileReadTokenRef.current += 1
    dispatch({ type: 'modelDraftChanged', model: nextModel, selection })
  }, [state.activeFamily, stopActiveTasks, workspace.analysisState])

  const applyDraft = useCallback(() => {
    if (!hasDraft || meshing) return
    fileReadTokenRef.current += 1
    resetEditTools()
    dispatch({ type: 'draftApplied' })
    setToast({ severity: 'success', message: 'Changes applied to the committed model' })
  }, [hasDraft, meshing, resetEditTools])

  const cancelDraft = useCallback(() => {
    if (!hasDraft) return
    meshAbortRef.current?.abort()
    meshAbortRef.current = null
    setMeshing(false)
    fileReadTokenRef.current += 1
    resetEditTools()
    dispatch({ type: 'draftCancelled' })
    setToast({ severity: 'info', message: 'Unapplied changes discarded' })
  }, [hasDraft, resetEditTools])

  const requestNavigation = useCallback((destination: string, action: () => void) => {
    if (!hasDraft) {
      action()
      return
    }
    pendingNavigationRef.current = action
    setPendingDestination(destination)
    setUnsavedDialogOpen(true)
  }, [hasDraft])

  const continuePendingNavigation = (apply: boolean) => {
    const action = pendingNavigationRef.current
    pendingNavigationRef.current = null
    setUnsavedDialogOpen(false)
    meshAbortRef.current?.abort()
    meshAbortRef.current = null
    setMeshing(false)
    if (apply) dispatch({ type: 'draftApplied' })
    else dispatch({ type: 'draftCancelled' })
    resetEditTools()
    action?.()
  }

  const openWorkspace = (family: ModelFamily) => {
    if (family === state.activeFamily) return
    const currentFamily = state.activeFamily
    const wasRunning = workspace.analysisState === 'running'
    requestNavigation(`${MODEL_FAMILIES[family].label} workspace`, () => {
      stopActiveTasks(currentFamily, wasRunning)
      resetEditTools()
      dispatch({ type: 'workspaceChanged', family })
    })
  }

  useEffect(() => {
    if (!hasDraft) return undefined
    const warnBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', warnBeforeUnload)
    return () => window.removeEventListener('beforeunload', warnBeforeUnload)
  }, [hasDraft])

  const openAuth = useCallback((reason: 'save' | 'history' | null = null, mode: AuthDialogMode = 'login') => {
    setAuthReason(reason)
    setAuthMode(mode)
    setAuthOpen(true)
  }, [])

  const saveCurrentModel = useCallback(() => {
    if (hasDraft) {
      showMessage('Apply or cancel staged changes before saving.', 'warning')
      return
    }
    if (!identity.currentUser) {
      openAuth('save')
      return
    }
    void modelHistory.save(workspace.model)
  }, [hasDraft, identity.currentUser, modelHistory.save, openAuth, showMessage, workspace.model])

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
    if (action === 'save') void modelHistory.save(workspace.model)
    else setHistoryOpen(true)
  }, [identity.currentUser, modelHistory.save, workspace.model])

  const handleGenerateMesh = useCallback(async () => {
    meshAbortRef.current?.abort()
    const controller = new AbortController()
    meshAbortRef.current = controller
    setMeshing(true)
    setMeshError(null)
    try {
      const response = await generateSurfaceMesh(model, meshSizeForModel(model), controller.signal)
      if (controller.signal.aborted || meshAbortRef.current !== controller) return
      meshAbortRef.current = null
      setMeshing(false)
      stageModelChange(applySurfaceMesh(model, response), { kind: 'mesh' })
      setToast({
        severity: 'success',
        message: `Gmsh mesh staged: ${response.nodes.length} nodes / ${response.elements.length} Q4 elements. Apply changes to commit it.`,
      })
    } catch (error) {
      if (controller.signal.aborted || (error instanceof DOMException && error.name === 'AbortError')) return
      if (meshAbortRef.current !== controller) return
      meshAbortRef.current = null
      setMeshing(false)
      setMeshError(error instanceof Error ? error.message : 'Gmsh mesh generation failed')
    }
  }, [model, stageModelChange])

  useEffect(() => {
    document.title = `${MODEL_FAMILIES[state.activeFamily].shortLabel} workspace — Nonlinear Studio`
  }, [state.activeFamily])

  const resetCurrentWorkspace = () => {
    const family = state.activeFamily
    requestNavigation(`${MODEL_FAMILIES[family].label} verification example`, () => {
      replaceDocument(cloneSampleModel(family), { kind: 'model' }, null, defaultRunOptions(family))
      setToast({ severity: 'info', message: `${MODEL_FAMILIES[family].label} verification example restored` })
    })
  }

  const handlePlace = (nodeId: string) => {
    if (!placement || !nodeId) return
    if (placement.kind === 'support') {
      if (placement.targetId) {
        stageModelChange(moveSupportToNode(model, placement.targetId, nodeId), { kind: 'constraints', id: nodeId })
      } else if (model.constraints.some((item) => item.node_id === nodeId)) {
        dispatch({ type: 'selectionChanged', selection: { kind: 'constraints', id: nodeId } })
      } else {
        stageModelChange(addSupportAtNode(model, nodeId, dofsForModel(model)), { kind: 'constraints', id: nodeId })
      }
    } else if (placement.targetId) {
      const next = structuredClone(model)
      const load = next.loads.find((item) => item.id === placement.targetId)
      if (load) {
        load.kind = 'nodal'
        load.node_id = nodeId
      }
      stageModelChange(next, { kind: 'loads', id: placement.targetId })
    } else {
      const info = MODEL_FAMILIES[model.model_family]
      const added = addNodalLoadAtNode(model, nodeId, info.primaryLoadDof, info.primaryLoadDof === 'UX' ? 1 : -1)
      stageModelChange(added.model, { kind: 'loads', id: added.id })
    }
    setPlacement(null)
  }

  const handleRun = useCallback(async () => {
    if (abortRef.current || meshing) return
    setCancelling(false)
    if (hasDraft) {
      setToast({ severity: 'warning', message: 'Apply or cancel staged changes before running the analysis.' })
      return
    }
    if (geometryNeedsMesh(workspace.model)) {
      setToast({ severity: 'warning', message: 'Geometry changed. Generate and apply a new mesh before solving.' })
      dispatch({ type: 'selectionChanged', selection: { kind: 'mesh' } })
      dispatch({ type: 'modeChanged', mode: 'model' })
      return
    }
    if (analysisIdRef.current) void cancelAnalysis(analysisIdRef.current).catch(() => undefined)
    analysisIdRef.current = null
    const controller = new AbortController()
    abortRef.current = controller
    const family = state.activeFamily
    const revision = workspace.modelRevision
    dispatch({ type: 'analysisStarted', family })
    try {
      const validation = await validateModel(workspace.model, controller.signal)
      if (!validation.valid || !validation.execution_eligible) {
        const first = validation.errors?.[0]
        throw new StudioApiError(first ? `${first.json_path}: ${first.message}` : validation.limit_error?.message ?? 'The model did not pass analysis validation', validation.limit_error?.code ?? 'MODEL_VALIDATION_FAILED')
      }
      if (controller.signal.aborted || abortRef.current !== controller) return
      // Keep the submission response so a cancellation during POST can cancel the created job.
      let record = await runAnalysis(workspace.model, workspace.runOptions, workspace.restart)
      if (controller.signal.aborted || abortRef.current !== controller) {
        if (record.status === 'queued' || record.status === 'running') {
          await cancelAnalysis(record.analysis_id).catch((error: unknown) => {
            setToast({ severity: 'error', message: `The previous job could not be cancelled: ${error instanceof Error ? error.message : 'connection failed'}. Server completion is unknown.` })
          })
        }
        return
      }
      analysisIdRef.current = record.analysis_id
      while (record.status === 'queued' || record.status === 'running') {
        if (controller.signal.aborted || abortRef.current !== controller) return
        dispatch({ type: 'analysisProgressed', family, record, revision })
        await waitForPoll(controller.signal)
        record = await getAnalysis(record.analysis_id, controller.signal)
      }
      if (controller.signal.aborted || abortRef.current !== controller) return
      abortRef.current = null
      analysisIdRef.current = null
      setCancelling(false)
      if (record.status === 'succeeded') {
        dispatch({ type: 'analysisSucceeded', family, record, revision })
        const acceptedSteps = record.progress.accepted_steps
        setToast({ severity: 'success', message: `Analysis complete: ${acceptedSteps} accepted ${acceptedSteps === 1 ? 'step' : 'steps'}` })
      } else if (record.status === 'cancelled') {
        dispatch({ type: 'analysisCancelled', family, record })
        setToast({ severity: 'info', message: 'Analysis cancelled; uncommitted trial output was discarded' })
      } else {
        dispatch({ type: 'analysisFailed', family, message: record.error?.message ?? 'Nonlinear analysis failed', record, revision })
        setToast({ severity: 'error', message: `${record.error?.code ?? 'FAILED'}: ${record.error?.message ?? 'Review the failure evidence'}` })
      }
    } catch (error) {
      if (controller.signal.aborted || (error instanceof DOMException && error.name === 'AbortError')) return
      if (abortRef.current !== controller) return
      abortRef.current = null
      setCancelling(false)
      const message = error instanceof Error ? error.message : 'The analysis request could not be completed'
      dispatch({ type: 'analysisFailed', family, message, revision })
      setToast({ severity: 'error', message })
    }
  }, [hasDraft, meshing, state.activeFamily, workspace])

  const handleCancel = useCallback(async () => {
    if (cancelling) return
    const analysisId = analysisIdRef.current
    const controller = abortRef.current
    if (!analysisId) {
      controller?.abort()
      abortRef.current = null
      dispatch({ type: 'analysisCancelled', family: state.activeFamily })
      setToast({ severity: 'info', message: 'Cancellation requested; any pending submission will be cancelled when acknowledged.' })
      return
    }
    setCancelling(true)
    try {
      await cancelAnalysis(analysisId)
      if (abortRef.current !== controller) return
      setToast({ severity: 'info', message: 'Cancellation requested. Waiting for the solver to stop.' })
      // Keep polling until the API confirms a terminal status and preserves accepted evidence.
    } catch (error) {
      if (abortRef.current !== controller) return
      setCancelling(false)
      setToast({ severity: 'error', message: `Cancellation was not confirmed: ${error instanceof Error ? error.message : 'connection failed'}. The solve is still being monitored; retry Cancel.` })
    }
  }, [cancelling, state.activeFamily])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.isComposing || event.repeat) return
      if (mathCoreOpen || authOpen || historyOpen || guideOpen || unsavedDialogOpen || menuAnchor || accountAnchor) return
      const target = event.target as HTMLElement | null
      if (target?.closest('input, textarea, select, [contenteditable=true], [role=combobox], [role=dialog]')) return
      if (event.key === 'Escape') {
        setPlacement(null)
        setCadTool('select')
        setPendingMember(null)
        return
      }
      if (!(event.metaKey || event.ctrlKey) || event.key !== 'Enter') return
      event.preventDefault()
      if (workspace.analysisState === 'running') void handleCancel()
      else void handleRun()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [handleCancel, handleRun, mathCoreOpen, authOpen, historyOpen, guideOpen, unsavedDialogOpen, menuAnchor, accountAnchor, workspace.analysisState])

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
      const validation = await validateModel(normalized)
      if (fileReadTokenRef.current !== readToken) return
      if (!validation.valid) {
        const first = validation.errors?.[0]
        throw new Error(first ? `${first.json_path}: ${first.message}` : 'The imported model failed schema validation.')
      }
      requestNavigation(`the imported ${MODEL_FAMILIES[normalized.model_family].label} model`, () => {
        replaceDocument(normalized, { kind: 'model' }, importedRestart, defaultRunOptions(normalized.model_family))
        setToast({ severity: 'success', message: importedRestart ? `Restart bundle imported: ${file.name}` : `Imported ${file.name}` })
      })
    } catch (error) {
      setToast({ severity: 'error', message: error instanceof Error ? error.message : 'JSON import failed' })
    }
  }

  const exportModel = () => {
    const blob = new Blob([`${JSON.stringify(workspace.model, null, 2)}\n`], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${workspace.model.model_id || 'nonlinear-model'}.json`
    anchor.click()
    URL.revokeObjectURL(url)
    setToast({ severity: 'success', message: 'Committed model JSON exported' })
  }

  const resultRestart = workspace.record?.result?.metadata.restart
  const availableRestart = isAnalysisRestart(resultRestart) ? resultRestart : workspace.restart
  const exportRestart = () => {
    if (!availableRestart) return
    const bundle: RestartBundle = {
      restart_bundle_schema_version: '1.0.0',
      model: workspace.model,
      restart: availableRestart,
    }
    const blob = new Blob([`${JSON.stringify(bundle, null, 2)}\n`], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${workspace.model.model_id || 'nonlinear-model'}-restart.json`
    anchor.click()
    URL.revokeObjectURL(url)
    setToast({ severity: 'success', message: 'Verifiable restart bundle exported' })
  }

  const currentStatus = workspace.analysisState === 'running'
    ? { label: cancelling ? 'Stopping' : 'Running', color: 'primary' as const }
    : workspace.record?.status === 'cancelled'
      ? { label: 'Cancelled', color: 'warning' as const }
    : workspace.analysisState === 'succeeded'
      ? { label: 'Results current', color: 'success' as const }
      : workspace.analysisState === 'failed'
        ? { label: 'Review required', color: 'error' as const }
        : workspace.resultInvalidated
          ? { label: 'Results invalidated', color: 'warning' as const }
          : hasDraft
            ? { label: 'Draft changes', color: 'warning' as const }
            : { label: 'Ready', color: 'default' as const }

  const family = MODEL_FAMILIES[state.activeFamily]
  const closeMenu = () => setMenuAnchor(null)
  const activeWorkflowStep: WorkflowStep = workspace.inspectorTab === 'analysis'
    ? 'solve'
    : workspace.selection.kind === 'materials'
      ? 'materials'
      : workspace.selection.kind === 'constraints'
        ? 'supports'
        : workspace.selection.kind === 'loads'
          ? 'loads'
          : workspace.selection.kind === 'mesh'
            ? 'mesh'
            : 'model'

  const openWorkflowStep = (step: WorkflowStep) => {
    setPropertiesCollapsed(false)
    resetEditTools()
    dispatch({ type: 'modeChanged', mode: 'model' })
    if (step === 'solve') {
      dispatch({ type: 'inspectorTabChanged', tab: 'analysis' })
      return
    }
    if (step === 'model') dispatch({ type: 'selectionChanged', selection: { kind: 'model' } })
    if (step === 'materials') dispatch({ type: 'selectionChanged', selection: { kind: 'materials', id: model.materials[0]?.id } })
    if (step === 'supports') dispatch({ type: 'selectionChanged', selection: { kind: 'constraints', id: model.constraints[0]?.node_id } })
    if (step === 'loads') dispatch({ type: 'selectionChanged', selection: { kind: 'loads', id: model.loads[0]?.id } })
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

  const draftFamilies = useMemo(() => new Set(MODEL_FAMILY_ORDER.filter((item) => workspaceHasDraft(state.workspaces[item]))), [state.workspaces])
  const resultFamilies = useMemo(() => new Set(MODEL_FAMILY_ORDER.filter((item) => state.workspaces[item].record?.status === 'succeeded')), [state.workspaces])
  const selectEntity = (selection: Selection) => {
    setPropertiesCollapsed(false)
    dispatch({ type: 'selectionChanged', selection })
  }
  const resultsAvailable = Boolean(workspace.record) || workspace.analysisState !== 'idle' || workspace.resultInvalidated

  const changeMode = (mode: StudioMode) => {
    if (mode === 'results' && hasDraft) {
      setToast({ severity: 'warning', message: 'Apply or cancel staged changes before opening Results.' })
      return
    }
    if (mode === 'results' && !resultsAvailable) return
    dispatch({ type: 'modeChanged', mode })
  }

  return (
    <Box sx={{ height: '100dvh', minWidth: 1120, display: 'flex', flexDirection: 'column', bgcolor: 'background.default' }}>
      <AppBar position="static" sx={{ zIndex: 4, bgcolor: 'background.paper', borderBottom: '1px solid', borderColor: 'divider' }}>
        <Toolbar disableGutters sx={{ px: 2, gap: 0.75, bgcolor: '#17343b', color: '#f4f9f7', '& .MuiIconButton-root, & .MuiButton-text': { color: '#d3e3de' }, '& .MuiButton-outlined': { color: '#e8f2ef', borderColor: '#536d71' } }}>
          <Box sx={{ width: 32, height: 32, borderRadius: 1, display: 'grid', placeItems: 'center', bgcolor: 'primary.main', color: 'primary.contrastText' }}>
            <AccountTreeRoundedIcon />
          </Box>
          <Box sx={{ width: 190, flexShrink: 0 }}>
            <Typography variant="h6">Nonlinear Studio</Typography>
            <Typography variant="caption" noWrap sx={{ display: 'block', color: '#b8ceca', letterSpacing: 0.8, fontSize: 8 }}>STRUCTURAL ANALYSIS WORKBENCH</Typography>
          </Box>
          <ToggleButtonGroup exclusive size="small" value={state.mode} onChange={(_, mode: StudioMode | null) => mode && changeMode(mode)} aria-label="Workbench mode">
            <ToggleButton value="model">Model</ToggleButton>
            <ToggleButton value="results" disabled={!resultsAvailable || hasDraft}>Results</ToggleButton>
          </ToggleButtonGroup>
          <Box sx={{ flex: 1 }} />
          <input ref={fileInputRef} type="file" accept="application/json,.json" hidden onChange={handleFile} />
          <Tooltip title="Import model JSON"><IconButton aria-label="Import" onClick={() => fileInputRef.current?.click()}><UploadFileRoundedIcon /></IconButton></Tooltip>
          <Tooltip title={hasDraft ? 'Apply or cancel changes before exporting' : 'Export committed model'}>
            <span><IconButton aria-label="Export" disabled={hasDraft} onClick={exportModel}><DownloadRoundedIcon /></IconButton></span>
          </Tooltip>
          <Tooltip title={workspace.analysisState === 'running' ? 'Math Core tools are unavailable during analysis' : 'Open Step 2 Math Core reference tools'}>
            <span><IconButton aria-label="Math Core" disabled={workspace.analysisState === 'running'} onClick={() => setMathCoreOpen(true)}><FunctionsRoundedIcon /></IconButton></span>
          </Tooltip>
          <Button variant="text" startIcon={modelHistory.saving ? <CircularProgress size={17} /> : <SaveRoundedIcon />} disabled={modelHistory.saving || identity.loading || hasDraft} onClick={saveCurrentModel}>
            {modelHistory.saving ? 'Saving…' : 'Save'}
          </Button>
          <Button variant="text" startIcon={<HistoryRoundedIcon />} disabled={identity.loading} onClick={openModelHistory}>History</Button>
          <Tooltip title="More actions">
            <IconButton aria-label="More actions" onClick={(event: MouseEvent<HTMLElement>) => setMenuAnchor(event.currentTarget)}><MoreVertRoundedIcon /></IconButton>
          </Tooltip>
          <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={closeMenu} anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} transformOrigin={{ vertical: 'top', horizontal: 'right' }}>
            <MenuItem disabled={!availableRestart || hasDraft} onClick={() => { exportRestart(); closeMenu() }}>Export restart bundle</MenuItem>
            <MenuItem onClick={() => { resetCurrentWorkspace(); closeMenu() }}>Reset current workspace example</MenuItem>
          </Menu>
          <Tooltip title="Getting started guide"><IconButton aria-label="Guide" onClick={() => setGuideOpen(true)}><HelpOutlineRoundedIcon /></IconButton></Tooltip>
          <Button
            variant="outlined"
            startIcon={identity.loading ? <CircularProgress size={17} /> : <AccountCircleRoundedIcon />}
            disabled={identity.loading}
            aria-label={identity.currentUser ? `Account for ${identity.currentUser.display_name}` : 'Guest account'}
            onClick={(event) => identity.currentUser ? setAccountAnchor(event.currentTarget) : openAuth()}
          >
            {identity.loading ? 'Account' : identity.currentUser?.display_name ?? 'Guest'}
          </Button>
          <Menu anchorEl={accountAnchor} open={Boolean(accountAnchor)} onClose={() => setAccountAnchor(null)} anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} transformOrigin={{ vertical: 'top', horizontal: 'right' }}>
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
          <Tooltip title={hasDraft ? 'Apply or cancel staged changes before running' : workspace.analysisState === 'running' ? 'Cancel analysis (Ctrl / ⌘ + Enter)' : 'Run analysis (Ctrl / ⌘ + Enter)'}>
            <span>
              <Button
                color={workspace.analysisState === 'running' ? 'error' : 'primary'}
                variant="contained"
                size="large"
                sx={{ minWidth: 148 }}
                disabled={cancelling || ((hasDraft || meshing) && workspace.analysisState !== 'running')}
                startIcon={workspace.analysisState === 'running' ? <StopCircleRoundedIcon /> : <PlayArrowRoundedIcon />}
                onClick={workspace.analysisState === 'running' ? handleCancel : handleRun}
              >
                {workspace.analysisState === 'running' ? cancelling ? 'Stopping…' : 'Cancel' : 'Run analysis'}
              </Button>
            </span>
          </Tooltip>
        </Toolbar>
        <Stack direction="row" sx={{ alignItems: 'stretch', bgcolor: 'background.containerLow', borderTop: '1px solid', borderColor: 'divider', minHeight: 54 }}>
          <WorkspaceSwitcher activeFamily={state.activeFamily} draftFamilies={draftFamilies} resultFamilies={resultFamilies} onChange={openWorkspace} />
          <Stack direction="row" spacing={1} sx={{ flex: 1, minWidth: 0, px: 1.5, alignItems: 'center' }}>
            <Box sx={{ minWidth: 150, flex: 1 }}>
              <Typography variant="body2" noWrap sx={{ fontWeight: 700 }}>{model.name}</Typography>
              <Typography variant="caption" color="text.secondary" noWrap sx={{ display: 'block' }}>
                {family.label} workspace · {CONTROL_LABELS[model.analysis.control_method]}
              </Typography>
            </Box>
            <Chip size="small" variant="outlined" label={`rev ${workspace.modelRevision}`} />
            <Chip size="small" variant="outlined" label={dofsForModel(model).join(' / ')} sx={{ display: { xs: 'none', xl: 'inline-flex' } }} />
            <Chip size="small" color={currentStatus.color} label={currentStatus.label} />
            {workspace.restart && <Chip size="small" color="info" variant="outlined" label={`Restart ${String(workspace.restart.committed_state.step_index ?? '—')}`} />}
          </Stack>
        </Stack>
        <Box sx={{ height: 3, bgcolor: 'background.container' }}>{workspace.analysisState === 'running' && <LinearProgress />}</Box>
      </AppBar>

      {state.mode === 'model' ? (
        <>
          <WorkflowBar
            model={model}
            analysisState={workspace.analysisState}
            activeStep={activeWorkflowStep}
            expanded={workflowExpanded}
            onStepChange={openWorkflowStep}
            onExpandedChange={setWorkflowExpanded}
          />
          <Box sx={{ flex: 1, minHeight: 0, display: 'flex' }}>
            <Box component="aside" aria-label="Model navigator" sx={{ width: 240, minWidth: 240, minHeight: 0, display: 'flex', flexDirection: 'column', bgcolor: 'background.paper', borderRight: '1px solid', borderColor: 'divider' }}>
                  <GeometryPanel
                    model={model}
                    selection={workspace.selection}
                    cadTool={cadTool}
                    onCadToolChange={(tool) => { setCadTool(tool); setPlacement(null); setPendingMember(null) }}
                    onSelection={selectEntity}
                    onModelChange={stageModelChange}
                  />
                  <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
                    <ModelNavigator
                      model={model}
                      selection={workspace.selection}
                      onSelection={selectEntity}
                      onModelChange={stageModelChange}
                      onEntityDoubleClick={() => setPropertiesCollapsed(true)}
                    />
                  </Box>
            </Box>
            <Box component="main" aria-label="Model editing canvas" sx={{ flex: 1, minWidth: 0, minHeight: 0, overflow: 'hidden' }}>
              <ModelCanvas
                key={`${state.activeFamily}-${model.model_id}`}
                model={model}
                result={null}
                selectedStep={0}
                view="model"
                selection={workspace.selection}
                cadTool={cadTool}
                placement={placement}
                pendingMember={pendingMember}
                onViewChange={() => undefined}
                onSelection={selectEntity}
                onModelChange={stageModelChange}
                onPlace={handlePlace}
                onPendingMember={setPendingMember}
              />
            </Box>
            <Box component="aside" aria-label="Model properties" sx={{ width: propertiesCollapsed ? 40 : 312, minWidth: propertiesCollapsed ? 40 : 312, display: 'flex', minHeight: 0, bgcolor: 'background.paper', borderLeft: '1px solid', borderColor: 'divider' }}>
                {propertiesCollapsed ? (
                  <Button
                    aria-label="Expand Properties"
                    onClick={() => setPropertiesCollapsed(false)}
                    sx={{ width: 40, minWidth: 40, height: '100%', borderRadius: 0, px: 0, py: 1.5, flexDirection: 'column', justifyContent: 'flex-start', gap: 1, color: 'text.secondary' }}
                  >
                    <ChevronRightRoundedIcon />
                    <Typography variant="caption" sx={{ fontWeight: 700, writingMode: 'vertical-rl', transform: 'rotate(180deg)', letterSpacing: 0.8 }}>Properties</Typography>
                  </Button>
                ) : (
                  <Box sx={{ width: 312, minWidth: 0, display: 'flex', flexDirection: 'column', minHeight: 0, bgcolor: 'background.paper' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', borderBottom: '1px solid', borderColor: 'divider' }}>
                      <Tabs value={workspace.inspectorTab} onChange={(_, tab: 'properties' | 'analysis') => dispatch({ type: 'inspectorTabChanged', tab })} variant="fullWidth" aria-label="Model forms" sx={{ minHeight: 48, pl: 1, flex: 1 }}>
                        <Tab value="properties" icon={<CodeRoundedIcon />} iconPosition="start" label="Properties" />
                        <Tab value="analysis" icon={<TuneRoundedIcon />} iconPosition="start" label="Analysis" />
                      </Tabs>
                      <Tooltip title="Collapse Properties"><IconButton aria-label="Collapse Properties" size="small" onClick={() => setPropertiesCollapsed(true)} sx={{ mr: 0.75 }}><ChevronLeftRoundedIcon /></IconButton></Tooltip>
                    </Box>
                    <Box sx={{ p: 1.75, overflow: 'auto', flex: 1, scrollbarGutter: 'stable' }}>
                      {workspace.inspectorTab === 'properties'
                        ? <PropertyPanel
                            model={model}
                            selection={workspace.selection}
                            onChange={stageModelChange}
                            onGenerateMesh={handleGenerateMesh}
                            meshing={meshing}
                            meshDisabled={workspace.analysisState === 'running'}
                            placement={placement}
                            onStartPlacement={(next) => { setPlacement(next); setCadTool('select'); setPendingMember(null) }}
                            onCancelPlacement={() => setPlacement(null)}
                          />
                        : <AnalysisPanel
                            model={model}
                            runOptions={runOptions}
                            onModelChange={stageModelChange}
                            onRunOptionsChange={(options) => {
                              if (workspace.analysisState === 'running') stopActiveTasks(state.activeFamily, true)
                              fileReadTokenRef.current += 1
                              dispatch({ type: 'runOptionsDraftChanged', options })
                            }}
                          />}
                    </Box>
                    {meshError && <Alert severity="error" onClose={() => setMeshError(null)} sx={{ m: 1 }}>{meshError}</Alert>}
                    {workspace.resultInvalidated && <Alert severity="warning" square sx={{ borderTop: '1px solid', borderColor: 'warning.light' }}>Applied model changes invalidated the previous results.</Alert>}
                  </Box>
                )}
            </Box>
          </Box>
          <DraftActionBar dirty={hasDraft} busy={meshing} onApply={applyDraft} onCancel={cancelDraft} />
        </>
      ) : (
        <ResultsWorkspace
          model={workspace.model}
          record={workspace.record}
          analysisState={workspace.analysisState}
          error={workspace.error}
          invalidated={workspace.resultInvalidated}
          resultTab={workspace.resultTab}
          resultView={workspace.resultView}
          selectedStep={workspace.selectedStep}
          selection={workspace.selection}
          onResultTabChange={(tab) => dispatch({ type: 'resultTabChanged', tab })}
          onResultViewChange={(view) => dispatch({ type: 'resultViewChanged', view })}
          onStepChange={(step) => dispatch({ type: 'stepChanged', step })}
          onSelection={selectEntity}
        />
      )}

      <Snackbar key={toast?.message ?? 'empty-toast'} open={toast !== null} autoHideDuration={4200} onClose={() => setToast(null)}>
        {toast ? <Alert severity={toast.severity} variant="filled" onClose={() => setToast(null)} sx={{ borderRadius: 3 }}>{toast.message}</Alert> : undefined}
      </Snackbar>
      <UnsavedChangesDialog
        open={unsavedDialogOpen}
        destination={pendingDestination}
        onKeepEditing={() => { pendingNavigationRef.current = null; setUnsavedDialogOpen(false) }}
        onApplyAndContinue={() => continuePendingNavigation(true)}
        onDiscardAndContinue={() => continuePendingNavigation(false)}
      />
      <GettingStartedDialog
        open={guideOpen}
        currentFamily={state.activeFamily}
        onClose={() => setGuideOpen(false)}
        onDoNotShowAgain={hideGuide}
        onOpenStep={openWorkflowStep}
        onChooseFamily={openWorkspace}
      />
      <MathCoreDialog open={mathCoreOpen} onClose={() => setMathCoreOpen(false)} />
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
            requestNavigation(`“${entry.name}” from model history`, () => {
              replaceDocument(structuredClone(entry.model), { kind: 'model' }, null, defaultRunOptions(entry.model.model_family))
              setHistoryOpen(false)
              showMessage(`Opened “${entry.name}” from model history.`, 'success')
            })
          }}
          onDelete={modelHistory.remove}
        />
      )}
    </Box>
  )
}
