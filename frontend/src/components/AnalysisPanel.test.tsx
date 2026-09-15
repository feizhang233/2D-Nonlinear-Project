// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { useState } from 'react'
import { AnalysisPanel } from './AnalysisPanel'
import { cloneSampleModel } from '../sampleModel'
import { defaultRunOptions } from '../modelFamilies'
import type { ModelInput } from '../domain'
import { analysisSettingsError } from '../analysisValidation'

afterEach(cleanup)
function Settings({ initial = cloneSampleModel() }: { initial?: ModelInput }) {
  const [model, setModel] = useState(initial)
  const [options, setOptions] = useState(defaultRunOptions('frame'))
  return <><AnalysisPanel model={model} runOptions={options} onModelChange={setModel} onRunOptionsChange={patch => setOptions(current => ({ ...current, ...patch }))} /><output>{String(Number.isNaN(options.numberOfSteps))}</output></>
}
describe('method-specific analysis inputs', () => {
  it('shows arc radii and common adaptation controls without unused load-step fields', () => {
    render(<Settings />)
    fireEvent.click(screen.getByRole('button', { name: 'Arc length' }))
    fireEvent.click(screen.getByRole('button', { name: 'Step size, cutback, and line search' }))
    expect(screen.getByRole('textbox', { name: 'Arc-length radius' })).toBeTruthy()
    expect(screen.queryByRole('textbox', { name: 'Initial load step' })).toBeNull()
    expect(screen.queryByRole('textbox', { name: 'Minimum load step' })).toBeNull()
    expect(screen.getByRole('textbox', { name: 'Growth factor' })).toBeTruthy()
    expect(screen.getByRole('textbox', { name: 'Maximum accepted steps' })).toBeTruthy()
    expect((screen.getByRole('switch', { name: 'Enable line search' }) as HTMLInputElement).disabled).toBe(true)
  })
  it('preserves fractional steps as an invalid draft instead of silently rounding', () => {
    render(<Settings />)
    fireEvent.click(screen.getByRole('button', { name: 'Displacement' }))
    const field = screen.getByRole('textbox', { name: 'Steps' })
    fireEvent.change(field, { target: { value: '1.5' } })
    expect((field as HTMLInputElement).value).toBe('1.5')
    expect(field.getAttribute('aria-invalid')).toBe('true')
    expect(screen.getByRole('status').textContent).toBe('true')
    fireEvent.change(field, { target: { value: '12' } })
    expect(screen.getByRole('status').textContent).toBe('false')
  })
  it('does not select a constrained loaded DOF as the control target', () => {
    const model = cloneSampleModel()
    const constrained = model.constraints[0]
    model.loads.unshift({ id: 'constrained-load', kind: 'nodal', node_id: constrained.node_id, components: { [constrained.dof]: 10 } })
    let changed = model
    render(<AnalysisPanel model={model} runOptions={defaultRunOptions('frame')} onModelChange={next => { changed = next }} onRunOptionsChange={() => undefined} />)
    fireEvent.click(screen.getByRole('button', { name: 'Displacement' }))
    expect(changed.analysis.displacement_control?.target).not.toEqual({ node_id: constrained.node_id, dof: constrained.dof })
    expect(analysisSettingsError(changed, defaultRunOptions('frame'))).toBeNull()
  })
  it('blocks contradictory step ranges and step limits before Apply', () => {
    const model = cloneSampleModel()
    model.analysis.step_control.initial_step = model.analysis.step_control.max_step * 2
    expect(analysisSettingsError(model, defaultRunOptions('frame'))).toContain('minimum ≤ initial ≤ maximum')
    model.analysis.step_control.initial_step = model.analysis.step_control.min_step
    model.analysis.control_method = 'arc_length'
    model.analysis.arc_length = { radius: 0.1, min_radius: 0.01, max_radius: 1, beta: 1, root_selection: 'direction_continuity' }
    expect(analysisSettingsError(model, { targetLoadFactor: 1, numberOfSteps: model.analysis.step_control.max_steps + 1 })).toContain('Maximum accepted steps')
  })
})

it('offers backtracking but marks unsupported orthogonality unavailable', async () => {
  render(<Settings />)
  fireEvent.click(screen.getByRole('button', { name: 'Step size, cutback, and line search' }))
  fireEvent.click(screen.getByRole('switch', { name: 'Enable line search' }))
  fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Line search method' }))
  const unsupported = await screen.findByRole('option', { name: 'Orthogonality (unavailable for structural models)' })
  expect(unsupported.getAttribute('aria-disabled')).toBe('true')
  const model = cloneSampleModel()
  model.analysis.line_search = { ...model.analysis.line_search, enabled: true, method: 'orthogonality' }
  expect(analysisSettingsError(model, defaultRunOptions('frame'))).toContain('backtracking')
})
