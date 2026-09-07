import type {
  AnalysisRecord,
  ModelInput,
  ResultTab,
  ResultView,
  RunOptions,
} from './domain'

export interface WorkspaceArchive {
  run_options: RunOptions
  record: AnalysisRecord | null
  selected_step: number
  result_view: ResultView
  result_tab: ResultTab
}
export interface ProjectDocument {
  studio_project_version: '1.0.0'
  model: ModelInput
  workspace: WorkspaceArchive
}
export function isProjectDocument(value: unknown): value is ProjectDocument {
  return Boolean(
    value &&
    typeof value === 'object' &&
    (value as Record<string, unknown>).studio_project_version === '1.0.0',
  )
}
export function downloadJson(value: unknown, filename: string): void {
  const blob = new Blob([`${JSON.stringify(value, null, 2)}\n`], {
    type: 'application/json',
  })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename.replace(/[^\p{L}\p{N}._ -]/gu, '_')
  anchor.hidden = true
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
