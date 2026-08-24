import type { AnalysisRecord, AnalysisRestart, ModelInput, ResultTab, ResultView, RunOptions, Selection } from './domain'
import { defaultRunOptions } from './modelFamilies'
import { cloneSampleModel } from './sampleModel'

export interface StudioState {
  model: ModelInput
  modelRevision: number
  selection: Selection
  inspectorTab: 'properties' | 'analysis'
  resultTab: ResultTab
  resultView: ResultView
  selectedStep: number
  runOptions: RunOptions
  analysisState: 'idle' | 'validating' | 'running' | 'succeeded' | 'failed'
  record: AnalysisRecord | null
  error: string | null
  resultInvalidated: boolean
  restart: AnalysisRestart | null
}

export const initialStudioState = (): StudioState => ({
  model: cloneSampleModel(),
  modelRevision: 0,
  selection: { kind: 'model' },
  inspectorTab: 'properties',
  resultTab: 'monitor',
  resultView: 'model',
  selectedStep: 0,
  runOptions: defaultRunOptions('frame'),
  analysisState: 'idle',
  record: null,
  error: null,
  resultInvalidated: false,
  restart: null,
})

export type StudioAction =
  | { type: 'modelChanged'; model: ModelInput; selection?: Selection; restart?: AnalysisRestart | null; runOptions?: RunOptions }
  | { type: 'selectionChanged'; selection: Selection }
  | { type: 'inspectorTabChanged'; tab: StudioState['inspectorTab'] }
  | { type: 'resultTabChanged'; tab: ResultTab }
  | { type: 'resultViewChanged'; view: ResultView }
  | { type: 'stepChanged'; step: number }
  | { type: 'runOptionsChanged'; options: Partial<RunOptions> }
  | { type: 'analysisStarted' }
  | { type: 'analysisProgressed'; record: AnalysisRecord; revision: number }
  | { type: 'analysisSucceeded'; record: AnalysisRecord; revision: number }
  | { type: 'analysisFailed'; message: string; record?: AnalysisRecord | null; revision: number }
  | { type: 'analysisCancelled' }

export function studioReducer(state: StudioState, action: StudioAction): StudioState {
  switch (action.type) {
    case 'modelChanged':
      return {
        ...state,
        model: action.model,
        modelRevision: state.modelRevision + 1,
        selection: action.selection ?? state.selection,
        analysisState: 'idle',
        record: null,
        error: null,
        selectedStep: 0,
        resultView: 'model',
        resultInvalidated: state.record !== null || state.analysisState === 'running',
        restart: action.restart ?? null,
        runOptions: action.runOptions ?? state.runOptions,
        inspectorTab: action.selection?.id ? 'properties' : state.inspectorTab,
      }
    case 'selectionChanged': return { ...state, selection: action.selection, inspectorTab: 'properties' }
    case 'inspectorTabChanged': return { ...state, inspectorTab: action.tab }
    case 'resultTabChanged': return { ...state, resultTab: action.tab }
    case 'resultViewChanged': return { ...state, resultView: action.view }
    case 'stepChanged': return { ...state, selectedStep: action.step }
    case 'runOptionsChanged': return { ...state, runOptions: { ...state.runOptions, ...action.options } }
    case 'analysisStarted':
      return { ...state, analysisState: 'running', record: null, error: null, resultInvalidated: false, resultTab: 'monitor' }
    case 'analysisProgressed':
      if (action.revision !== state.modelRevision) return state
      return { ...state, analysisState: 'running', record: action.record, error: null }
    case 'analysisSucceeded':
      if (action.revision !== state.modelRevision) return state
      return {
        ...state,
        analysisState: 'succeeded', record: action.record, error: null,
        selectedStep: Math.max(0, (action.record.result?.steps.length ?? 1) - 1),
        resultView: 'deformation', resultInvalidated: false,
      }
    case 'analysisFailed':
      if (action.revision !== state.modelRevision) return state
      return {
        ...state, analysisState: 'failed', record: action.record ?? null, error: action.message,
        resultTab: 'failure', resultView: 'model', resultInvalidated: false,
      }
    case 'analysisCancelled':
      return { ...state, analysisState: 'idle', record: null, error: null }
  }
}
