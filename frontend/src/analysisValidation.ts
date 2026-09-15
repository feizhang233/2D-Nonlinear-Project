import type { ModelInput, RunOptions } from './domain'
import { hasNonFiniteNumber } from './inputValidation'
import { dofsForModel } from './modelFamilies'

/** Cross-field checks shared by the settings dialog and every Apply path. */
export function analysisSettingsError(model: ModelInput, runOptions: RunOptions): string | null {
  const analysis = model.analysis
  if (hasNonFiniteNumber(analysis) || hasNonFiniteNumber(runOptions)) return 'Complete the numeric analysis fields.'
  const step = analysis.step_control
  if (analysis.line_search.enabled && analysis.line_search.method === 'orthogonality') {
    return 'Structural analysis supports backtracking line search. Select Backtracking or turn off line search.'
  }
  if (!(step.min_step > 0 && step.min_step <= step.initial_step && step.initial_step <= step.max_step)) {
    return 'Step sizes must satisfy 0 < minimum ≤ initial ≤ maximum.'
  }
  if (analysis.control_method !== 'load' && runOptions.numberOfSteps > step.max_steps) {
    return 'Steps must not exceed Maximum accepted steps.'
  }
  if (!Number.isInteger(runOptions.numberOfSteps) || runOptions.numberOfSteps < 1 || runOptions.numberOfSteps > 10000) {
    return 'Steps must be a whole number from 1 to 10000.'
  }
  if (analysis.control_method === 'arc_length') {
    const arc = analysis.arc_length
    if (!arc || !(arc.min_radius > 0 && arc.min_radius <= arc.radius && arc.radius <= arc.max_radius)) {
      return 'Arc-length radii must satisfy 0 < minimum ≤ radius ≤ maximum.'
    }
    if (analysis.line_search.enabled) return 'Turn off line search for arc-length control.'
  }
  if (analysis.control_method === 'displacement') {
    const target = analysis.displacement_control?.target
    if (!target || !model.nodes.some(node => node.id === target.node_id)
      || !dofsForModel(model).includes(target.dof)
      || model.constraints.some(constraint => constraint.node_id === target.node_id && constraint.dof === target.dof)) {
      return 'Choose an unconstrained node and degree of freedom for displacement control.'
    }
  }
  return null
}
