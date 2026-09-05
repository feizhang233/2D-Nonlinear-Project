import type {
  AnalysisRecord,
  AnalysisRestart,
  ModelFamily,
  ModelInput,
  ResultTab,
  ResultView,
  RunOptions,
  Selection,
} from './domain'
import { defaultRunOptions, MODEL_FAMILY_ORDER } from './modelFamilies'
import { cloneSampleModel } from './sampleModel'

export type StudioMode = 'model' | 'results'

export interface WorkspaceState {
  model: ModelInput
  draftModel: ModelInput | null
  modelRevision: number
  selection: Selection
  inspectorTab: 'properties' | 'analysis'
  resultTab: ResultTab
  resultView: ResultView
  selectedStep: number
  runOptions: RunOptions
  draftRunOptions: RunOptions | null
  analysisState: 'idle' | 'validating' | 'running' | 'succeeded' | 'failed'
  record: AnalysisRecord | null
  error: string | null
  resultInvalidated: boolean
  restart: AnalysisRestart | null
}

export interface StudioState {
  activeFamily: ModelFamily
  mode: StudioMode
  workspaces: Record<ModelFamily, WorkspaceState>
}

const createWorkspace = (family: ModelFamily): WorkspaceState => ({
  model: cloneSampleModel(family),
  draftModel: null,
  modelRevision: 0,
  selection: { kind: 'model' },
  inspectorTab: 'properties',
  resultTab: 'monitor',
  resultView: 'model',
  selectedStep: 0,
  runOptions: defaultRunOptions(family),
  draftRunOptions: null,
  analysisState: 'idle',
  record: null,
  error: null,
  resultInvalidated: false,
  restart: null,
})

export const initialStudioState = (): StudioState => ({
  activeFamily: 'frame',
  mode: 'model',
  workspaces: Object.fromEntries(MODEL_FAMILY_ORDER.map((family) => [family, createWorkspace(family)])) as Record<ModelFamily, WorkspaceState>,
})

export const activeWorkspace = (state: StudioState): WorkspaceState => state.workspaces[state.activeFamily]
export const editingModel = (workspace: WorkspaceState): ModelInput => workspace.draftModel ?? workspace.model
export const editingRunOptions = (workspace: WorkspaceState): RunOptions => workspace.draftRunOptions ?? workspace.runOptions
export const workspaceHasDraft = (workspace: WorkspaceState): boolean => workspace.draftModel !== null || workspace.draftRunOptions !== null

export type StudioAction =
  | { type: 'workspaceChanged'; family: ModelFamily }
  | { type: 'modeChanged'; mode: StudioMode }
  | { type: 'modelDraftChanged'; model: ModelInput; selection?: Selection }
  | { type: 'runOptionsDraftChanged'; options: Partial<RunOptions> }
  | { type: 'draftApplied' }
  | { type: 'draftCancelled' }
  | { type: 'documentReplaced'; model: ModelInput; selection?: Selection; restart?: AnalysisRestart | null; runOptions?: RunOptions }
  | { type: 'selectionChanged'; selection: Selection }
  | { type: 'inspectorTabChanged'; tab: WorkspaceState['inspectorTab'] }
  | { type: 'resultTabChanged'; tab: ResultTab }
  | { type: 'resultViewChanged'; view: ResultView }
  | { type: 'stepChanged'; step: number }
  | { type: 'analysisStarted'; family: ModelFamily }
  | { type: 'analysisProgressed'; family: ModelFamily; record: AnalysisRecord; revision: number }
  | { type: 'analysisSucceeded'; family: ModelFamily; record: AnalysisRecord; revision: number }
  | { type: 'analysisFailed'; family: ModelFamily; message: string; record?: AnalysisRecord | null; revision: number }
  | { type: 'analysisCancelled'; family: ModelFamily; record?: AnalysisRecord }

const updateWorkspace = (
  state: StudioState,
  family: ModelFamily,
  update: (workspace: WorkspaceState) => WorkspaceState,
  mode = state.mode,
): StudioState => ({
  ...state,
  mode,
  workspaces: { ...state.workspaces, [family]: update(state.workspaces[family]) },
})

export function studioReducer(state: StudioState, action: StudioAction): StudioState {
  const family = 'family' in action ? action.family : state.activeFamily
  const workspace = state.workspaces[family]

  switch (action.type) {
    case 'workspaceChanged':
      return { ...state, activeFamily: action.family, mode: 'model' }
    case 'modeChanged':
      return { ...state, mode: action.mode }
    case 'modelDraftChanged':
      return updateWorkspace(state, family, (current) => ({
        ...current,
        draftModel: action.model,
        selection: action.selection ?? current.selection,
        inspectorTab: action.selection?.id ? 'properties' : current.inspectorTab,
      }))
    case 'runOptionsDraftChanged':
      return updateWorkspace(state, family, (current) => ({
        ...current,
        draftRunOptions: { ...(current.draftRunOptions ?? current.runOptions), ...action.options },
      }))
    case 'draftApplied': {
      if (!workspace.draftModel && !workspace.draftRunOptions) return state
      const invalidated = workspace.record !== null || workspace.analysisState === 'running'
      return updateWorkspace(state, family, (current) => ({
        ...current,
        model: current.draftModel ?? current.model,
        draftModel: null,
        modelRevision: current.modelRevision + 1,
        runOptions: current.draftRunOptions ?? current.runOptions,
        draftRunOptions: null,
        analysisState: 'idle',
        record: null,
        error: null,
        selectedStep: 0,
        resultView: 'model',
        resultInvalidated: invalidated,
        restart: null,
      }), 'model')
    }
    case 'draftCancelled':
      return updateWorkspace(state, family, (current) => ({
        ...current,
        draftModel: null,
        draftRunOptions: null,
        selection: { kind: 'model' },
        inspectorTab: 'properties',
      }))
    case 'documentReplaced': {
      const targetFamily = action.model.model_family
      const currentTarget = state.workspaces[targetFamily]
      const nextTarget: WorkspaceState = {
        ...currentTarget,
        model: action.model,
        draftModel: null,
        modelRevision: currentTarget.modelRevision + 1,
        selection: action.selection ?? { kind: 'model' },
        inspectorTab: 'properties',
        resultTab: 'monitor',
        resultView: 'model',
        selectedStep: 0,
        runOptions: action.runOptions ?? currentTarget.runOptions,
        draftRunOptions: null,
        analysisState: 'idle',
        record: null,
        error: null,
        resultInvalidated: currentTarget.record !== null || currentTarget.analysisState === 'running',
        restart: action.restart ?? null,
      }
      return {
        ...state,
        activeFamily: targetFamily,
        mode: 'model',
        workspaces: { ...state.workspaces, [targetFamily]: nextTarget },
      }
    }
    case 'selectionChanged':
      return updateWorkspace(state, family, (current) => ({ ...current, selection: action.selection, inspectorTab: 'properties' }))
    case 'inspectorTabChanged':
      return updateWorkspace(state, family, (current) => ({ ...current, inspectorTab: action.tab }))
    case 'resultTabChanged':
      return updateWorkspace(state, family, (current) => ({ ...current, resultTab: action.tab }))
    case 'resultViewChanged':
      return updateWorkspace(state, family, (current) => ({ ...current, resultView: action.view }))
    case 'stepChanged':
      return updateWorkspace(state, family, (current) => ({ ...current, selectedStep: action.step }))
    case 'analysisStarted':
      return updateWorkspace(state, family, (current) => ({
        ...current,
        analysisState: 'running',
        record: null,
        error: null,
        resultInvalidated: false,
        resultTab: 'monitor',
      }), 'results')
    case 'analysisProgressed':
      if (action.revision !== workspace.modelRevision || workspace.analysisState !== 'running') return state
      return updateWorkspace(state, family, (current) => ({ ...current, analysisState: 'running', record: action.record, error: null }))
    case 'analysisSucceeded':
      if (action.revision !== workspace.modelRevision || workspace.analysisState !== 'running') return state
      return updateWorkspace(state, family, (current) => ({
        ...current,
        analysisState: 'succeeded',
        record: action.record,
        error: null,
        selectedStep: Math.max(0, (action.record.result?.steps.length ?? 1) - 1),
        resultView: 'deformation',
        resultInvalidated: false,
      }), state.activeFamily === family ? 'results' : state.mode)
    case 'analysisFailed':
      if (action.revision !== workspace.modelRevision || workspace.analysisState !== 'running') return state
      return updateWorkspace(state, family, (current) => ({
        ...current,
        analysisState: 'failed',
        record: action.record ?? null,
        error: action.message,
        resultTab: 'failure',
        resultView: 'model',
        resultInvalidated: false,
      }), state.activeFamily === family ? 'results' : state.mode)
    case 'analysisCancelled':
      return updateWorkspace(state, family, (current) => ({ ...current, analysisState: 'idle', record: action.record ?? null, resultView: 'model', error: null }), state.activeFamily === family && !action.record ? 'model' : state.mode)
  }
}
