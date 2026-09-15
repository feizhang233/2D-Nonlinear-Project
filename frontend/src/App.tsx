import { SaveProjectDialog } from './components/SaveProjectDialog'
import { ModelTools } from './components/ModelTools'
import { deleteSelection } from './modelOperations'
import { sectionError } from './sections'
import {
  downloadJson,
  isProjectDocument,
  type ProjectDocument,
  type WorkspaceArchive,
} from './projectFiles'
import AccountCircleRoundedIcon from '@mui/icons-material/AccountCircleRounded'
import AccountTreeRoundedIcon from '@mui/icons-material/AccountTreeRounded'
import TuneRoundedIcon from '@mui/icons-material/TuneRounded'
import KeyboardArrowDownRoundedIcon from '@mui/icons-material/KeyboardArrowDownRounded'
import CloseRoundedIcon from '@mui/icons-material/CloseRounded'
import DownloadRoundedIcon from '@mui/icons-material/DownloadRounded'
import FunctionsRoundedIcon from '@mui/icons-material/FunctionsRounded'
import HelpOutlineRoundedIcon from '@mui/icons-material/HelpOutlineRounded'
import HistoryRoundedIcon from '@mui/icons-material/HistoryRounded'
import LogoutRoundedIcon from '@mui/icons-material/LogoutRounded'
import PlayArrowRoundedIcon from '@mui/icons-material/PlayArrowRounded'
import SaveRoundedIcon from '@mui/icons-material/SaveRounded'
import StopCircleRoundedIcon from '@mui/icons-material/StopCircleRounded'
import UploadFileRoundedIcon from '@mui/icons-material/UploadFileRounded'
import Alert from '@mui/material/Alert'
import AppBar from '@mui/material/AppBar'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import IconButton from '@mui/material/IconButton'
import LinearProgress from '@mui/material/LinearProgress'
import Menu from '@mui/material/Menu'
import MenuItem from '@mui/material/MenuItem'
import Snackbar from '@mui/material/Snackbar'
import Stack from '@mui/material/Stack'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import Toolbar from '@mui/material/Toolbar'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  type ChangeEvent,
} from 'react'
import {
  cancelAnalysis,
  generateSurfaceMesh,
  getAnalysis,
  runAnalysis,
  StudioApiError,
  validateModel,
  validateProject,
} from './api'
import { waitForPoll } from './asyncTasks'
import { AnalysisSettingsDialog } from './components/AnalysisSettingsDialog'
import { hasNonFiniteNumber } from './inputValidation'
import { analysisSettingsError } from './analysisValidation'
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
import { type WorkflowStep } from './components/WorkflowBar'
import { WorkspaceSwitcher } from './components/WorkspaceSwitcher'
import type {
  AnalysisRestart,
  ModelFamily,
  ModelInput,
  RestartBundle,
  RunOptions,
  Selection,
} from './domain'
import { defaultHoleDimensions, sketchError } from './cadGeometry'
import {
  CadTool,
  geometryNeedsMesh,
  getSketch,
  isSurfaceFamily,
  PlacementState,
} from './geometrySketch'
import { useIdentity } from './hooks/useIdentity'
import { useModelHistory } from './hooks/useModelHistory'
import {
  defaultRunOptions,
  dofsForModel,
  MODEL_FAMILIES,
  MODEL_FAMILY_ORDER,
} from './modelFamilies'
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
import { placeLoad, type PlacementTarget } from './loadPlacement'
import { addSupportAtNode, moveSupportToNode } from './supports'

interface Toast {
  message: string
  severity: 'success' | 'info' | 'warning' | 'error'
}

const GUIDE_STORAGE_KEY = 'nonlinear-studio-guide-hidden-v2'

const isModelDocument = (value: unknown): value is ModelInput => {
  if (!value || typeof value !== 'object') return false
  const record = value as Record<string, unknown>
  return (
    record.schema_version === '1.0.0' &&
    MODEL_FAMILY_ORDER.includes(record.model_family as ModelFamily) &&
    Array.isArray(record.nodes) &&
    Array.isArray(record.elements) &&
    Array.isArray(record.materials) &&
    typeof record.analysis === 'object'
  )
}

const isAnalysisRestart = (value: unknown): value is AnalysisRestart => {
  if (!value || typeof value !== 'object') return false
  const record = value as Record<string, unknown>
  return (
    record.restart_schema_version === '1.0.0' &&
    Boolean(record.committed_state) &&
    typeof record.committed_state === 'object'
  )
}

const isRestartBundle = (value: unknown): value is RestartBundle => {
  if (!value || typeof value !== 'object') return false
  const record = value as Record<string, unknown>
  return (
    record.restart_bundle_schema_version === '1.0.0' &&
    isModelDocument(record.model) &&
    isAnalysisRestart(record.restart)
  )
}

export default function App() {
  const [state, dispatch] = useReducer(
    studioReducer,
    undefined,
    initialStudioState,
  )
  const workspace = activeWorkspace(state)
  const model = editingModel(workspace)
  const runOptions = editingRunOptions(workspace)
  const hasDraft = workspaceHasDraft(workspace)
  const sectionValidationError =
    sectionError(model) ??
    (isSurfaceFamily(model) ? sketchError(getSketch(model)) : null) ??
    (hasNonFiniteNumber(model) || hasNonFiniteNumber(runOptions)
      ? 'Complete the numeric field. Scientific notation such as -2.5e4 is supported.'
      : null) ?? analysisSettingsError(model, runOptions)
  const [toast, setToast] = useState<Toast | null>(null)
  const [meshing, setMeshing] = useState(false)
  const [meshError, setMeshError] = useState<string | null>(null)
  const [cancelling, setCancelling] = useState(false)
  const [saveOpen, setSaveOpen] = useState(false)
  const [analysisSettingsOpen, setAnalysisSettingsOpen] = useState(false)
  const pendingArchiveRef = useRef<WorkspaceArchive | undefined>(undefined)
  const [propertiesCollapsed, setPropertiesCollapsed] = useState(true)
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
  const [holeDimensions, setHoleDimensions] = useState(defaultHoleDimensions)
  const [cadTool, setCadTool] = useState<CadTool>('select')
  const [placement, setPlacement] = useState<PlacementState>(null)
  const [pendingMember, setPendingMember] = useState<string | null>(null)
  const [pendingDestination, setPendingDestination] =
    useState('another workspace')
  const [unsavedDialogOpen, setUnsavedDialogOpen] = useState(false)
  const pendingNavigationRef = useRef<(() => void) | null>(null)
  const pendingAuthActionRef = useRef<'save' | 'history' | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const meshAbortRef = useRef<AbortController | null>(null)
  const analysisIdRef = useRef<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const fileReadTokenRef = useRef(0)

  const showMessage = useCallback(
    (message: string, severity: Toast['severity']) => {
      setToast({ message, severity })
    },
    [],
  )
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

  const stopActiveTasks = useCallback(
    (family: ModelFamily, cancelRunning: boolean) => {
      if (analysisIdRef.current)
        void cancelAnalysis(analysisIdRef.current).catch((error: unknown) => {
          showMessage(
            `The previous analysis could not be cancelled: ${error instanceof Error ? error.message : 'connection failed'}. Server completion is unknown.`,
            'warning',
          )
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
    },
    [showMessage],
  )

  useEffect(
    () => () => {
      abortRef.current?.abort()
      meshAbortRef.current?.abort()
      if (analysisIdRef.current)
        void cancelAnalysis(analysisIdRef.current).catch(() => undefined)
    },
    [],
  )

  const replaceDocument = useCallback(
    (
      nextModel: ModelInput,
      selection?: Selection,
      restart: AnalysisRestart | null = null,
      nextRunOptions?: RunOptions,
    ) => {
      stopActiveTasks(state.activeFamily, workspace.analysisState === 'running')
      resetEditTools()
      dispatch({
        type: 'documentReplaced',
        model: nextModel,
        selection,
        restart,
        runOptions: nextRunOptions,
      })
    },
    [
      resetEditTools,
      state.activeFamily,
      stopActiveTasks,
      workspace.analysisState,
    ],
  )

  const stageModelChange = useCallback(
    (nextModel: ModelInput, selection?: Selection) => {
      if (nextModel === model && selection) {
        dispatch({ type: 'selectionChanged', selection })
        return
      }
      if (workspace.analysisState === 'running')
        stopActiveTasks(state.activeFamily, true)
      meshAbortRef.current?.abort()
      meshAbortRef.current = null
      setMeshing(false)
      fileReadTokenRef.current += 1
      if (
        selection &&
        (selection.kind === 'sections' ||
          selection.kind === 'materials' ||
          (cadTool === 'select' && !placement))
      )
        setPropertiesCollapsed(false)
      dispatch({ type: 'modelDraftChanged', model: nextModel, selection })
    },
    [
      model,
      state.activeFamily,
      stopActiveTasks,
      workspace.analysisState,
      cadTool,
      placement,
    ],
  )

  const applyDraft = useCallback(() => {
    if (!hasDraft || meshing) return
    if (cadTool === 'draw-outline') {
      showMessage(
        'Close or cancel the outline before applying changes.',
        'info',
      )
      return
    }
    if (sectionValidationError) {
      showMessage(sectionValidationError, 'error')
      return
    }
    fileReadTokenRef.current += 1
    resetEditTools()
    dispatch({ type: 'draftApplied' })
    setToast({
      severity: 'success',
      message: 'Changes applied to the committed model',
    })
  }, [
    hasDraft,
    meshing,
    resetEditTools,
    sectionValidationError,
    showMessage,
    cadTool,
  ])

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

  const requestNavigation = useCallback(
    (destination: string, action: () => void) => {
      if (!hasDraft) {
        action()
        return
      }
      pendingNavigationRef.current = action
      setPendingDestination(destination)
      setUnsavedDialogOpen(true)
    },
    [hasDraft],
  )

  const continuePendingNavigation = (apply: boolean) => {
    if (apply && sectionValidationError) {
      showMessage(sectionValidationError, 'error')
      return
    }
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

  const openAuth = useCallback(
    (
      reason: 'save' | 'history' | null = null,
      mode: AuthDialogMode = 'login',
    ) => {
      setAuthReason(reason)
      setAuthMode(mode)
      setAuthOpen(true)
    },
    [],
  )

  const archiveFor = useCallback(
    (includeResults = true): WorkspaceArchive => ({
      run_options: workspace.runOptions,
      record:
        includeResults &&
        workspace.record &&
        !['queued', 'running'].includes(workspace.record.status)
          ? workspace.record
          : null,
      selected_step: workspace.selectedStep,
      result_view: workspace.resultView,
      result_tab: workspace.resultTab,
    }),
    [
      workspace.runOptions,
      workspace.record,
      workspace.selectedStep,
      workspace.resultView,
      workspace.resultTab,
    ],
  )

  const saveCurrentModel = useCallback(
    (includeResults = true) => {
      if (hasDraft) {
        showMessage('Apply or cancel staged changes before saving.', 'warning')
        return
      }
      pendingArchiveRef.current = archiveFor(includeResults)
      if (!identity.currentUser) {
        setSaveOpen(false)
        openAuth('save')
        return
      }
      void modelHistory
        .save(workspace.model, pendingArchiveRef.current)
        .then((entry) => {
          if (entry) setSaveOpen(false)
        })
    },
    [
      archiveFor,
      hasDraft,
      identity.currentUser,
      modelHistory.save,
      openAuth,
      showMessage,
      workspace.model,
    ],
  )

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
    if (action === 'save')
      void modelHistory.save(workspace.model, pendingArchiveRef.current)
    else setHistoryOpen(true)
  }, [identity.currentUser, modelHistory.save, workspace.model])

  const handleGenerateMesh = useCallback(async () => {
    meshAbortRef.current?.abort()
    const controller = new AbortController()
    meshAbortRef.current = controller
    setMeshing(true)
    setMeshError(null)
    try {
      const response = await generateSurfaceMesh(
        model,
        meshSizeForModel(model),
        controller.signal,
      )
      if (controller.signal.aborted || meshAbortRef.current !== controller)
        return
      meshAbortRef.current = null
      setMeshing(false)
      stageModelChange(applySurfaceMesh(model, response), { kind: 'mesh' })
      setToast({
        severity: 'success',
        message: `Gmsh mesh staged: ${response.nodes.length} nodes / ${response.elements.length} Q4 elements. Apply changes to commit it.`,
      })
    } catch (error) {
      if (
        controller.signal.aborted ||
        (error instanceof DOMException && error.name === 'AbortError')
      )
        return
      if (meshAbortRef.current !== controller) return
      meshAbortRef.current = null
      setMeshing(false)
      setMeshError(
        error instanceof Error ? error.message : 'Gmsh mesh generation failed',
      )
    }
  }, [model, stageModelChange])

  useEffect(() => {
    document.title = `${MODEL_FAMILIES[state.activeFamily].shortLabel} workspace — Nonlinear Studio`
  }, [state.activeFamily])

  const resetCurrentWorkspace = () => {
    const family = state.activeFamily
    requestNavigation(
      `${MODEL_FAMILIES[family].label} verification example`,
      () => {
        replaceDocument(
          cloneSampleModel(family),
          { kind: 'model' },
          null,
          defaultRunOptions(family),
        )
        setToast({
          severity: 'info',
          message: `${MODEL_FAMILIES[family].label} verification example restored`,
        })
      },
    )
  }

  const startDrawing = (tool: CadTool) => {
    setCadTool(tool)
    setPlacement(null)
    setPendingMember(null)
    if (
      tool === 'draw-outline' ||
      tool === 'add-hole' ||
      tool === 'add-vertex'
    ) {
      dispatch({ type: 'selectionChanged', selection: { kind: 'geometry' } })
    }
    setPropertiesCollapsed(true)
  }
  const startPlacement = (next: PlacementState) => {
    setPlacement(next)
    setCadTool('select')
    setPendingMember(null)
    setPropertiesCollapsed(true)
  }
  const handlePlace = (target: PlacementTarget) => {
    if (!placement) return
    try {
      if (placement.kind === 'support') {
        if (target.kind !== 'node') return
        const nodeId = target.id
        if (placement.targetId) {
          stageModelChange(
            moveSupportToNode(model, placement.targetId, nodeId),
            { kind: 'constraints', id: nodeId },
          )
        } else if (model.constraints.some((item) => item.node_id === nodeId)) {
          dispatch({
            type: 'selectionChanged',
            selection: { kind: 'constraints', id: nodeId },
          })
        } else
          stageModelChange(
            addSupportAtNode(model, nodeId, dofsForModel(model)),
            { kind: 'constraints', id: nodeId },
          )
      } else {
        const added = placeLoad(model, target, placement)
        stageModelChange(added.model, { kind: 'loads', id: added.id })
      }
      setPlacement(null)
      setPropertiesCollapsed(false)
    } catch (error) {
      setToast({
        severity: 'warning',
        message:
          error instanceof Error
            ? error.message
            : 'Choose a valid load location.',
      })
    }
  }

  const handleRun = useCallback(async () => {
    if (abortRef.current || meshing || cadTool === 'draw-outline') return
    setCancelling(false)
    if (hasDraft) {
      setToast({
        severity: 'warning',
        message: 'Apply or cancel staged changes before running the analysis.',
      })
      return
    }
    if (geometryNeedsMesh(workspace.model)) {
      setPropertiesCollapsed(false)
      setToast({
        severity: 'warning',
        message:
          'Geometry changed. Generate and apply a new mesh before solving.',
      })
      dispatch({ type: 'selectionChanged', selection: { kind: 'mesh' } })
      dispatch({ type: 'modeChanged', mode: 'model' })
      return
    }
    if (analysisIdRef.current)
      void cancelAnalysis(analysisIdRef.current).catch(() => undefined)
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
        throw new StudioApiError(
          first
            ? `${first.json_path}: ${first.message}`
            : (validation.limit_error?.message ??
                'The model did not pass analysis validation'),
          validation.limit_error?.code ?? 'MODEL_VALIDATION_FAILED',
        )
      }
      if (controller.signal.aborted || abortRef.current !== controller) return
      // Keep the submission response so a cancellation during POST can cancel the created job.
      let record = await runAnalysis(
        workspace.model,
        workspace.runOptions,
        workspace.restart,
      )
      if (controller.signal.aborted || abortRef.current !== controller) {
        if (record.status === 'queued' || record.status === 'running') {
          await cancelAnalysis(record.analysis_id).catch((error: unknown) => {
            setToast({
              severity: 'error',
              message: `The previous job could not be cancelled: ${error instanceof Error ? error.message : 'connection failed'}. Server completion is unknown.`,
            })
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
        setToast({
          severity: 'success',
          message: `Analysis complete: ${acceptedSteps} accepted ${acceptedSteps === 1 ? 'step' : 'steps'}`,
        })
      } else if (record.status === 'cancelled') {
        dispatch({ type: 'analysisCancelled', family, record })
        setToast({
          severity: 'info',
          message: 'Analysis cancelled; uncommitted trial output was discarded',
        })
      } else {
        dispatch({
          type: 'analysisFailed',
          family,
          message: record.error?.message ?? 'Nonlinear analysis failed',
          record,
          revision,
        })
        setToast({
          severity: 'error',
          message: `${record.error?.code ?? 'FAILED'}: ${record.error?.message ?? 'Review the failure evidence'}`,
        })
      }
    } catch (error) {
      if (
        controller.signal.aborted ||
        (error instanceof DOMException && error.name === 'AbortError')
      )
        return
      if (abortRef.current !== controller) return
      abortRef.current = null
      setCancelling(false)
      const message =
        error instanceof Error
          ? error.message
          : 'The analysis request could not be completed'
      dispatch({ type: 'analysisFailed', family, message, revision })
      setToast({ severity: 'error', message })
    }
  }, [hasDraft, meshing, state.activeFamily, workspace, cadTool])

  const handleCancel = useCallback(async () => {
    if (cancelling) return
    const analysisId = analysisIdRef.current
    const controller = abortRef.current
    if (!analysisId) {
      controller?.abort()
      abortRef.current = null
      dispatch({ type: 'analysisCancelled', family: state.activeFamily })
      setToast({
        severity: 'info',
        message:
          'Cancellation requested; any pending submission will be cancelled when acknowledged.',
      })
      return
    }
    setCancelling(true)
    try {
      await cancelAnalysis(analysisId)
      if (abortRef.current !== controller) return
      setToast({
        severity: 'info',
        message: 'Cancellation requested. Waiting for the solver to stop.',
      })
      // Keep polling until the API confirms a terminal status and preserves accepted evidence.
    } catch (error) {
      if (abortRef.current !== controller) return
      setCancelling(false)
      setToast({
        severity: 'error',
        message: `Cancellation was not confirmed: ${error instanceof Error ? error.message : 'connection failed'}. The solve is still being monitored; retry Cancel.`,
      })
    }
  }, [cancelling, state.activeFamily])

  const removeSelected = useCallback(
    (selection = workspace.selection) => {
      if (
        state.mode !== 'model' ||
        meshing ||
        workspace.analysisState === 'running'
      )
        return
      try {
        stageModelChange(deleteSelection(model, selection), {
          kind: selection.kind,
        })
        resetEditTools()
        showMessage(
          'Item removed from the draft. Cancel restores the committed model.',
          'info',
        )
      } catch (error) {
        showMessage(
          error instanceof Error ? error.message : 'Cannot delete this item.',
          'warning',
        )
      }
    },
    [
      workspace.selection,
      workspace.analysisState,
      state.mode,
      meshing,
      model,
      stageModelChange,
      resetEditTools,
      showMessage,
    ],
  )

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.isComposing || event.repeat) return
      if (
        analysisSettingsOpen ||
        saveOpen ||
        mathCoreOpen ||
        authOpen ||
        historyOpen ||
        guideOpen ||
        unsavedDialogOpen ||
        menuAnchor ||
        accountAnchor
      )
        return
      const target = event.target instanceof Element ? event.target : null
      if (
        target?.closest(
          'input, textarea, select, [contenteditable=true], [role=combobox], [role=dialog]',
        )
      )
        return
      if (event.key === 'Escape') {
        setPlacement(null)
        setCadTool('select')
        setPendingMember(null)
        return
      }
      if (
        ['Delete', 'Backspace'].includes(event.key) &&
        !event.metaKey &&
        !event.ctrlKey &&
        !event.altKey &&
        workspace.selection.id &&
        state.mode === 'model'
      ) {
        event.preventDefault()
        removeSelected()
        return
      }
      if (!(event.metaKey || event.ctrlKey) || event.key !== 'Enter') return
      event.preventDefault()
      if (workspace.analysisState === 'running') void handleCancel()
      else if (hasDraft) applyDraft()
      else void handleRun()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [
    analysisSettingsOpen,
    hasDraft,
    applyDraft,
    removeSelected,
    state.mode,
    workspace.selection.id,
    saveOpen,
    handleCancel,
    handleRun,
    mathCoreOpen,
    authOpen,
    historyOpen,
    guideOpen,
    unsavedDialogOpen,
    menuAnchor,
    accountAnchor,
    workspace.analysisState,
  ])

  const handleFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    const readToken = fileReadTokenRef.current + 1
    fileReadTokenRef.current = readToken
    try {
      if (file.size > 20 * 1024 * 1024)
        throw new Error('Project files must be 20 MB or smaller')
      const parsed = JSON.parse(await file.text()) as unknown
      if (fileReadTokenRef.current !== readToken) return
      if (isProjectDocument(parsed)) {
        const project = await validateProject(parsed)
        if (fileReadTokenRef.current !== readToken) return
        requestNavigation(`the project “${project.model.name}”`, () => {
          replaceDocument(
            project.model,
            { kind: 'model' },
            null,
            project.workspace.run_options,
          )
          dispatch({ type: 'archiveRestored', archive: project.workspace })
          showMessage(
            `Opened ${file.name}${project.workspace.record ? ' with saved results' : ''}.`,
            'success',
          )
        })
        return
      }
      const importedModel = isRestartBundle(parsed) ? parsed.model : parsed
      const importedRestart = isRestartBundle(parsed) ? parsed.restart : null
      if (!isModelDocument(importedModel))
        throw new Error(
          'This is not a version 1.0.0 Frame, Continuum, Plate, or Shell model/restart bundle',
        )
      const defaults = cloneSampleModel(importedModel.model_family)
      const normalized: ModelInput = {
        ...importedModel,
        loads: Array.isArray(importedModel.loads) ? importedModel.loads : [],
        constraints: Array.isArray(importedModel.constraints)
          ? importedModel.constraints
          : [],
        analysis: {
          ...defaults.analysis,
          ...importedModel.analysis,
          tolerances: {
            ...defaults.analysis.tolerances,
            ...importedModel.analysis.tolerances,
          },
          step_control: {
            ...defaults.analysis.step_control,
            ...importedModel.analysis.step_control,
          },
          line_search: {
            ...defaults.analysis.line_search,
            ...importedModel.analysis.line_search,
          },
        },
      }
      const validation = await validateModel(normalized)
      if (fileReadTokenRef.current !== readToken) return
      if (!validation.valid) {
        const first = validation.errors?.[0]
        throw new Error(
          first
            ? `${first.json_path}: ${first.message}`
            : 'The imported model failed schema validation.',
        )
      }
      requestNavigation(
        `the imported ${MODEL_FAMILIES[normalized.model_family].label} model`,
        () => {
          replaceDocument(
            normalized,
            { kind: 'model' },
            importedRestart,
            defaultRunOptions(normalized.model_family),
          )
          setToast({
            severity: 'success',
            message: importedRestart
              ? `Restart bundle imported: ${file.name}`
              : `Imported ${file.name}`,
          })
        },
      )
    } catch (error) {
      setToast({
        severity: 'error',
        message: error instanceof Error ? error.message : 'JSON import failed',
      })
    }
  }

  const exportModel = () => {
    const blob = new Blob([`${JSON.stringify(workspace.model, null, 2)}\n`], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${workspace.model.model_id || 'nonlinear-model'}.json`
    anchor.click()
    URL.revokeObjectURL(url)
    setToast({ severity: 'success', message: 'Committed model JSON exported' })
  }

  const resultRestart = workspace.record?.result?.metadata.restart
  const availableRestart = isAnalysisRestart(resultRestart)
    ? resultRestart
    : workspace.restart
  const exportRestart = () => {
    if (!availableRestart) return
    const bundle: RestartBundle = {
      restart_bundle_schema_version: '1.0.0',
      model: workspace.model,
      restart: availableRestart,
    }
    const blob = new Blob([`${JSON.stringify(bundle, null, 2)}\n`], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${workspace.model.model_id || 'nonlinear-model'}-restart.json`
    anchor.click()
    URL.revokeObjectURL(url)
    setToast({
      severity: 'success',
      message: 'Verifiable restart bundle exported',
    })
  }

  const currentStatus =
    workspace.analysisState === 'running'
      ? {
          label: cancelling ? 'Stopping' : 'Running',
          color: 'primary' as const,
        }
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

  const closeMenu = () => setMenuAnchor(null)
  const openWorkflowStep = (step: WorkflowStep) => {
    resetEditTools()
    dispatch({ type: 'modeChanged', mode: 'model' })
    if (step === 'solve') {
      setAnalysisSettingsOpen(true)
      return
    }
    setPropertiesCollapsed(false)
    if (step === 'model')
      dispatch({ type: 'selectionChanged', selection: { kind: 'model' } })
    if (step === 'materials')
      dispatch({
        type: 'selectionChanged',
        selection: { kind: 'materials', id: model.materials[0]?.id },
      })
    if (step === 'supports')
      dispatch({
        type: 'selectionChanged',
        selection: { kind: 'constraints', id: model.constraints[0]?.node_id },
      })
    if (step === 'loads')
      dispatch({
        type: 'selectionChanged',
        selection: { kind: 'loads', id: model.loads[0]?.id },
      })
    if (step === 'mesh')
      dispatch({ type: 'selectionChanged', selection: { kind: 'mesh' } })
  }

  const hideGuide = () => {
    try {
      window.localStorage.setItem(GUIDE_STORAGE_KEY, 'true')
    } catch {
      // Private browsing or a restricted test environment may disable storage.
    }
    setGuideOpen(false)
  }

  const draftFamilies = useMemo(
    () =>
      new Set(
        MODEL_FAMILY_ORDER.filter((item) =>
          workspaceHasDraft(state.workspaces[item]),
        ),
      ),
    [state.workspaces],
  )
  const resultFamilies = useMemo(
    () =>
      new Set(
        MODEL_FAMILY_ORDER.filter(
          (item) => state.workspaces[item].record?.status === 'succeeded',
        ),
      ),
    [state.workspaces],
  )
  const selectEntity = (selection: Selection) => {
    setPropertiesCollapsed(
      !selection.id &&
        !['model', 'mesh', 'sections', 'constraints', 'loads'].includes(
          selection.kind,
        ),
    )
    dispatch({ type: 'selectionChanged', selection })
  }
  const resultsAvailable =
    Boolean(workspace.record) ||
    workspace.analysisState !== 'idle' ||
    workspace.resultInvalidated

  const changeMode = (mode: StudioMode) => {
    if (mode === 'results' && hasDraft) {
      setToast({
        severity: 'warning',
        message: 'Apply or cancel staged changes before opening Results.',
      })
      return
    }
    if (mode === 'results' && !resultsAvailable) return
    dispatch({ type: 'modeChanged', mode })
  }

  return (
    <Box
      sx={{
        height: '100dvh',
        minWidth: 1120,
        display: 'flex',
        flexDirection: 'column',
        bgcolor: 'background.default',
      }}
    >
      <AppBar
        position="static"
        sx={{
          zIndex: 4,
          bgcolor: 'background.paper',
          borderBottom: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Toolbar
          disableGutters
          sx={{
            px: 2,
            gap: 0.75,
            bgcolor: 'background.paper',
            color: 'text.primary',
          }}
        >
          <AccountTreeRoundedIcon
            sx={{ color: 'primary.main', fontSize: 23, mr: 0.25 }}
          />
          <Typography
            variant="h6"
            sx={{ fontSize: 16, mr: 2, whiteSpace: 'nowrap' }}
          >
            Nonlinear Studio
          </Typography>
          <Button
            color="inherit"
            aria-label="More actions"
            aria-haspopup="menu"
            aria-expanded={Boolean(menuAnchor)}
            endIcon={<KeyboardArrowDownRoundedIcon />}
            onClick={(event) => setMenuAnchor(event.currentTarget)}
          >
            Project
          </Button>
          <Box sx={{ flex: 1 }} />
          <ToggleButtonGroup
            exclusive
            size="small"
            value={state.mode}
            onChange={(_, mode: StudioMode | null) => mode && changeMode(mode)}
            aria-label="Workbench mode"
          >
            <ToggleButton value="model">Model</ToggleButton>
            <ToggleButton
              value="results"
              disabled={!resultsAvailable || hasDraft}
            >
              Results
            </ToggleButton>
          </ToggleButtonGroup>
          <Box sx={{ flex: 1 }} />
          <input
            ref={fileInputRef}
            type="file"
            accept="application/json,.json"
            hidden
            onChange={handleFile}
          />
          <Menu
            anchorEl={menuAnchor}
            open={Boolean(menuAnchor)}
            onClose={closeMenu}
          >
            <MenuItem
              onClick={() => {
                closeMenu()
                fileInputRef.current?.click()
              }}
            >
              <UploadFileRoundedIcon fontSize="small" sx={{ mr: 1.5 }} />
              Open
            </MenuItem>
            <MenuItem
              disabled={hasDraft}
              onClick={() => {
                exportModel()
                closeMenu()
              }}
            >
              <DownloadRoundedIcon fontSize="small" sx={{ mr: 1.5 }} />
              Export model
            </MenuItem>
            <MenuItem
              disabled={identity.loading}
              onClick={() => {
                closeMenu()
                openModelHistory()
              }}
            >
              <HistoryRoundedIcon fontSize="small" sx={{ mr: 1.5 }} />
              History
            </MenuItem>
            <MenuItem
              disabled={!availableRestart || hasDraft}
              onClick={() => {
                exportRestart()
                closeMenu()
              }}
            >
              Export restart bundle
            </MenuItem>
            <Divider />
            <MenuItem
              disabled={workspace.analysisState === 'running'}
              onClick={() => {
                closeMenu()
                setMathCoreOpen(true)
              }}
            >
              <FunctionsRoundedIcon fontSize="small" sx={{ mr: 1.5 }} />
              Math Core
            </MenuItem>
            <MenuItem
              onClick={() => {
                closeMenu()
                setGuideOpen(true)
              }}
            >
              <HelpOutlineRoundedIcon fontSize="small" sx={{ mr: 1.5 }} />
              Guide
            </MenuItem>
            <Divider />
            <MenuItem
              onClick={() => {
                resetCurrentWorkspace()
                closeMenu()
              }}
            >
              Reset current workspace example
            </MenuItem>
          </Menu>
          <Button
            color="inherit"
            startIcon={<SaveRoundedIcon sx={{ fontSize: 18 }} />}
            disabled={
              hasDraft ||
              cadTool === 'draw-outline' ||
              meshing ||
              workspace.analysisState === 'running'
            }
            onClick={() => setSaveOpen(true)}
          >
            Save project
          </Button>
          <Button
            color="inherit"
            aria-label="Analysis settings"
            startIcon={<TuneRoundedIcon sx={{ fontSize: 18 }} />}
            onClick={() => openWorkflowStep('solve')}
          >
            Analysis
          </Button>
          <Tooltip
            title={
              identity.currentUser
                ? identity.currentUser.display_name
                : 'Guest · sign in'
            }
          >
            <IconButton
              disabled={identity.loading}
              aria-label={
                identity.currentUser
                  ? `Account for ${identity.currentUser.display_name}`
                  : 'Guest account'
              }
              onClick={(event) =>
                identity.currentUser
                  ? setAccountAnchor(event.currentTarget)
                  : openAuth()
              }
            >
              {identity.loading ? (
                <CircularProgress size={20} />
              ) : (
                <AccountCircleRoundedIcon />
              )}
            </IconButton>
          </Tooltip>
          <Menu
            anchorEl={accountAnchor}
            open={Boolean(accountAnchor)}
            onClose={() => setAccountAnchor(null)}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            transformOrigin={{ vertical: 'top', horizontal: 'right' }}
          >
            {identity.currentUser && (
              <Box sx={{ px: 2, py: 1, maxWidth: 260 }}>
                <Typography variant="subtitle2" noWrap>
                  {identity.currentUser.display_name}
                </Typography>
                <Typography variant="caption" color="text.secondary" noWrap>
                  {identity.currentUser.email}
                </Typography>
              </Box>
            )}
            <Divider />
            <MenuItem
              onClick={() => {
                setAccountAnchor(null)
                void identity.signOut().then((signedOut) => {
                  if (signedOut) setHistoryOpen(false)
                })
              }}
            >
              <LogoutRoundedIcon fontSize="small" sx={{ mr: 1.25 }} /> Sign out
            </MenuItem>
          </Menu>
          <Tooltip
            title={
              hasDraft
                ? 'Apply changes (Ctrl / ⌘ + Enter)'
                : workspace.analysisState === 'running'
                  ? 'Cancel analysis (Ctrl / ⌘ + Enter)'
                  : 'Run analysis (Ctrl / ⌘ + Enter)'
            }
          >
            <span>
              <Button
                color={
                  workspace.analysisState === 'running' ? 'error' : 'primary'
                }
                variant="contained"
                size="large"
                sx={{ width: 158, minWidth: 158 }}
                disabled={
                  cancelling ||
                  cadTool === 'draw-outline' ||
                  ((meshing || Boolean(sectionValidationError)) &&
                    workspace.analysisState !== 'running')
                }
                startIcon={
                  workspace.analysisState === 'running' ? (
                    <StopCircleRoundedIcon />
                  ) : hasDraft ? (
                    <SaveRoundedIcon />
                  ) : (
                    <PlayArrowRoundedIcon />
                  )
                }
                onClick={
                  workspace.analysisState === 'running'
                    ? handleCancel
                    : hasDraft
                      ? applyDraft
                      : handleRun
                }
              >
                {workspace.analysisState === 'running'
                  ? cancelling
                    ? 'Stopping…'
                    : 'Cancel'
                  : hasDraft
                    ? 'Apply changes'
                    : 'Run analysis'}
              </Button>
            </span>
          </Tooltip>
        </Toolbar>
        <Stack
          direction="row"
          sx={{
            alignItems: 'center',
            bgcolor: 'background.paper',
            borderTop: '1px solid',
            borderColor: 'divider',
            minHeight: 38,
            px: 1,
          }}
        >
          <WorkspaceSwitcher
            activeFamily={state.activeFamily}
            draftFamilies={draftFamilies}
            resultFamilies={resultFamilies}
            onChange={openWorkspace}
          />
          <Divider orientation="vertical" flexItem sx={{ mx: 2, my: 1 }} />
          <Typography
            variant="body2"
            noWrap
            sx={{ flex: 1, minWidth: 0, color: 'text.secondary' }}
            title={model.name}
          >
            {model.name}
          </Typography>
          <Typography
            variant="caption"
            sx={{
              px: 1.5,
              color:
                currentStatus.color === 'default'
                  ? 'text.secondary'
                  : `${currentStatus.color}.main`,
            }}
          >
            {currentStatus.label}
          </Typography>
          {workspace.restart && (
            <Typography variant="caption" color="info.main">
              Restart{' '}
              {String(workspace.restart.committed_state.step_index ?? '—')}
            </Typography>
          )}
        </Stack>
        <Box sx={{ height: 2, bgcolor: 'background.paper' }}>
          {workspace.analysisState === 'running' && <LinearProgress />}
        </Box>
      </AppBar>

      {state.mode === 'model' ? (
        <>
          <Box sx={{ flex: 1, minHeight: 0, display: 'flex' }}>
            <Box
              component="aside"
              aria-label="Model navigator"
              sx={{
                width: 232,
                minWidth: 232,
                minHeight: 0,
                display: 'flex',
                flexDirection: 'column',
                bgcolor: 'background.paper',
                borderRight: '1px solid',
                borderColor: 'divider',
              }}
            >
              <ModelNavigator
                model={model}
                selection={workspace.selection}
                onInspectModel={() => selectEntity({ kind: 'model' })}
                onSelection={(selection) => {
                  resetEditTools()
                  if (selection.kind === 'model') {
                    setPropertiesCollapsed(true)
                    dispatch({ type: 'selectionChanged', selection })
                  } else selectEntity(selection)
                }}
                onModelChange={stageModelChange}
                onDelete={() => removeSelected()}
                onAddLoad={() => startPlacement({ kind: 'load' })}
                onDraw={(tool) => {
                  setCadTool(tool)
                  setPlacement(null)
                  setPendingMember(null)
                }}
              >
                <GeometryPanel
                  model={model}
                  selection={workspace.selection}
                  cadTool={cadTool}
                  holeDimensions={holeDimensions}
                  onHoleDimensionsChange={setHoleDimensions}
                  onCadToolChange={startDrawing}
                  onSelection={selectEntity}
                  onModelChange={stageModelChange}
                />
              </ModelNavigator>
            </Box>
            <Box
              component="main"
              aria-label="Model editing canvas"
              sx={{
                flex: 1,
                minWidth: 0,
                minHeight: 0,
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              <Stack
                direction="row"
                sx={{
                  px: 1.5,
                  height: 48,
                  flexShrink: 0,
                  alignItems: 'center',
                  borderBottom: '1px solid',
                  borderColor: 'divider',
                  bgcolor: 'background.paper',
                }}
              >
                <ModelTools
                  model={model}
                  tool={cadTool}
                  placement={placement}
                  onTool={startDrawing}
                  onSelection={selectEntity}
                  onPlace={startPlacement}
                />
                {propertiesCollapsed && (
                  <Tooltip title="Show properties">
                    <IconButton
                      aria-label="Expand Properties"
                      size="small"
                      onClick={() => setPropertiesCollapsed(false)}
                    >
                      <TuneRoundedIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                )}
              </Stack>
              <Box sx={{ flex: 1, minHeight: 0 }}>
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
                  onSelection={(selection) => {
                    if (selection.kind === 'model') {
                      setPropertiesCollapsed(true)
                      dispatch({ type: 'selectionChanged', selection })
                    } else selectEntity(selection)
                  }}
                  onModelChange={stageModelChange}
                  onPlace={handlePlace}
                  onPlacementChange={setPlacement}
                  holeDimensions={holeDimensions}
                  onStopDrawing={() => setCadTool('select')}
                  onPendingMember={setPendingMember}
                />
              </Box>
            </Box>
            <Box
              component="aside"
              hidden={propertiesCollapsed}
              aria-label="Model properties"
              sx={{
                width: 320,
                minWidth: 320,
                display: propertiesCollapsed ? 'none' : 'flex',
                flexDirection: 'column',
                minHeight: 0,
                bgcolor: 'background.paper',
                borderLeft: '1px solid',
                borderColor: 'divider',
              }}
            >
              <Stack
                direction="row"
                sx={{
                  alignItems: 'center',
                  minHeight: 48,
                  px: 2,
                  borderBottom: '1px solid',
                  borderColor: 'divider',
                }}
              >
                <Typography variant="subtitle2" sx={{ flex: 1 }}>
                  Properties
                </Typography>
                <Tooltip title="Close properties">
                  <IconButton
                    aria-label="Collapse Properties"
                    size="small"
                    onClick={() => setPropertiesCollapsed(true)}
                  >
                    <CloseRoundedIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Stack>
              <Box
                sx={{
                  p: 1.75,
                  overflow: 'auto',
                  flex: 1,
                  scrollbarGutter: 'stable',
                }}
              >
                <PropertyPanel
                  model={model}
                  selection={workspace.selection}
                  onChange={stageModelChange}
                  onDelete={removeSelected}
                  onGenerateMesh={handleGenerateMesh}
                  meshing={meshing}
                  meshDisabled={workspace.analysisState === 'running'}
                  placement={placement}
                  onStartPlacement={startPlacement}
                  onCancelPlacement={() => setPlacement(null)}
                />
              </Box>
              {sectionValidationError && (
                <Alert severity="error" sx={{ m: 1 }}>
                  {sectionValidationError} Correct the field before applying
                  changes.
                </Alert>
              )}
              {meshError && (
                <Alert
                  severity="error"
                  onClose={() => setMeshError(null)}
                  sx={{ m: 1 }}
                >
                  {meshError}
                </Alert>
              )}
              {workspace.resultInvalidated && (
                <Alert
                  severity="warning"
                  square
                  sx={{ borderTop: '1px solid', borderColor: 'warning.light' }}
                >
                  Applied model changes invalidated the previous results.
                </Alert>
              )}
            </Box>
          </Box>
          <DraftActionBar
            dirty={hasDraft}
            busy={meshing}
            onCancel={cancelDraft}
          />
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
          onResultTabChange={(tab) =>
            dispatch({ type: 'resultTabChanged', tab })
          }
          onResultViewChange={(view) =>
            dispatch({ type: 'resultViewChanged', view })
          }
          onStepChange={(step) => dispatch({ type: 'stepChanged', step })}
          onSelection={selectEntity}
        />
      )}

      <Snackbar
        key={toast?.message ?? 'empty-toast'}
        open={toast !== null}
        autoHideDuration={4200}
        onClose={() => setToast(null)}
      >
        {toast ? (
          <Alert
            severity={toast.severity}
            variant="filled"
            onClose={() => setToast(null)}
            sx={{ borderRadius: 3 }}
          >
            {toast.message}
          </Alert>
        ) : undefined}
      </Snackbar>
      <AnalysisSettingsDialog
        open={analysisSettingsOpen}
        onClose={() => setAnalysisSettingsOpen(false)}
        model={model}
        runOptions={runOptions}
        onModelChange={stageModelChange}
        onRunOptionsChange={(options) => {
          fileReadTokenRef.current += 1
          dispatch({ type: 'runOptionsDraftChanged', options })
        }}
      />
      <SaveProjectDialog
        open={saveOpen}
        onClose={() => setSaveOpen(false)}
        name={workspace.model.name}
        hasResults={Boolean(
          workspace.record &&
          !['queued', 'running'].includes(workspace.record.status),
        )}
        signedIn={Boolean(identity.currentUser)}
        saving={modelHistory.saving}
        error={modelHistory.error}
        onAccountSave={saveCurrentModel}
        onDownload={(includeResults) => {
          const project: ProjectDocument = {
            studio_project_version: '1.0.0',
            model: workspace.model,
            workspace: archiveFor(includeResults),
          }
          if (
            new Blob([`${JSON.stringify(project, null, 2)}\n`]).size >
            20 * 1024 * 1024
          ) {
            showMessage(
              'This project exceeds 20 MB. Save the model without results or reduce the analysis history.',
              'error',
            )
            return
          }
          downloadJson(
            project,
            `${workspace.model.model_id || 'nonlinear'}-project.json`,
          )
          setSaveOpen(false)
          showMessage(
            includeResults && project.workspace.record
              ? 'Project downloaded with model and results.'
              : 'Model project downloaded.',
            'success',
          )
        }}
      />
      <UnsavedChangesDialog
        open={unsavedDialogOpen}
        destination={pendingDestination}
        validationError={sectionValidationError}
        onKeepEditing={() => {
          pendingNavigationRef.current = null
          setUnsavedDialogOpen(false)
        }}
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
      <MathCoreDialog
        open={mathCoreOpen}
        onClose={() => setMathCoreOpen(false)}
      />
      <AuthDialog
        open={authOpen}
        initialMode={authMode}
        reason={authReason}
        onClose={() => {
          setAuthOpen(false)
          setAuthReason(null)
        }}
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
          error={modelHistory.error}
          saving={modelHistory.saving}
          deletingId={modelHistory.deletingId}
          onClose={() => setHistoryOpen(false)}
          onSave={() => {
            setHistoryOpen(false)
            setSaveOpen(true)
          }}
          onOpen={(entry) => {
            requestNavigation(`“${entry.name}” from model history`, () => {
              replaceDocument(
                structuredClone(entry.model),
                { kind: 'model' },
                null,
                defaultRunOptions(entry.model.model_family),
              )
              if (entry.workspace)
                dispatch({ type: 'archiveRestored', archive: entry.workspace })
              setHistoryOpen(false)
              showMessage(
                `Opened “${entry.name}” from model history.`,
                'success',
              )
            })
          }}
          onDelete={modelHistory.remove}
        />
      )}
    </Box>
  )
}
