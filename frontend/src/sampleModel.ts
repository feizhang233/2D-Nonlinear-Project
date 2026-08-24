import type { AnalysisOptions, ModelFamily, ModelInput } from './domain'

type AnalysisOverrides = Omit<Partial<AnalysisOptions>, 'tolerances' | 'step_control' | 'line_search'> & {
  tolerances?: Partial<AnalysisOptions['tolerances']>
  step_control?: Partial<AnalysisOptions['step_control']>
  line_search?: Partial<AnalysisOptions['line_search']>
}

const analysisOptions = (overrides: AnalysisOverrides = {}): AnalysisOptions => {
  const base: AnalysisOptions = {
    control_method: 'load',
    newton_method: 'full',
    max_iterations: 30,
    tolerances: {
      residual: 1e-8, displacement: 1e-8, energy: 1e-10, linear_solver: 1e-10,
      force_floor: 1e-12, displacement_floor: 1e-12, energy_floor: 1e-16,
    },
    step_control: {
      initial_step: 0.05, min_step: 1e-4, max_step: 0.1, max_steps: 100,
      max_retries: 8, target_iterations: 6, cutback_factor: 0.5, growth_factor: 1.5,
    },
    line_search: {
      enabled: false, method: 'backtracking', max_iterations: 8,
      min_alpha: 1e-3, reduction_factor: 0.5,
    },
    extensions: {},
  }
  return {
    ...base,
    ...overrides,
    tolerances: { ...base.tolerances, ...overrides.tolerances },
    step_control: { ...base.step_control, ...overrides.step_control },
    line_search: { ...base.line_search, ...overrides.line_search },
  }
}

export const shallowArchModel: ModelInput = {
  schema_version: '1.0.0', model_id: 'p11-shallow-arch', name: 'Shallow arch limit-point demo', model_family: 'frame',
  units: { length: 'm', force: 'N', stress: 'Pa', angle: 'rad', system_label: 'SI' },
  nodes: [
    { id: 'N1', coordinates: [-1, 0] }, { id: 'N2', coordinates: [0, 0.2] }, { id: 'N3', coordinates: [1, 0] },
  ],
  materials: [{ id: 'M1', model: 'linear-elastic', parameters: { young: 10_000_000 } }],
  elements: [
    { id: 'E1', formulation: 'frame2d-corotational', node_ids: ['N1', 'N2'], material_id: 'M1', properties: { area: 0.01, second_moment: 1e-8 } },
    { id: 'E2', formulation: 'frame2d-corotational', node_ids: ['N2', 'N3'], material_id: 'M1', properties: { area: 0.01, second_moment: 1e-8 } },
  ],
  loads: [{ id: 'P', kind: 'nodal', node_id: 'N2', components: { UY: -1000 }, coordinate_system: 'global', pattern: 'default', scale: 1 }],
  constraints: [
    { id: 'C1', node_id: 'N1', dof: 'UX', value: 0 }, { id: 'C2', node_id: 'N1', dof: 'UY', value: 0 },
    { id: 'C3', node_id: 'N1', dof: 'RZ', value: 0 }, { id: 'C4', node_id: 'N2', dof: 'UX', value: 0 },
    { id: 'C5', node_id: 'N2', dof: 'RZ', value: 0 }, { id: 'C6', node_id: 'N3', dof: 'UX', value: 0 },
    { id: 'C7', node_id: 'N3', dof: 'UY', value: 0 }, { id: 'C8', node_id: 'N3', dof: 'RZ', value: 0 },
  ],
  analysis: analysisOptions(),
  extensions: { purpose: 'Frame nonlinear workbench acceptance', expected_first_limit_load_factor: 0.296 },
}

export const continuumModel: ModelInput = {
  schema_version: '1.0.0', model_id: 'p12-q4-plane-strain-tension', name: 'Q4 plane-strain tension', model_family: 'continuum',
  units: { length: 'm', force: 'N', stress: 'Pa', angle: 'rad', system_label: 'SI' },
  nodes: [
    { id: 'N1', coordinates: [0, 0] }, { id: 'N2', coordinates: [2, 0] },
    { id: 'N3', coordinates: [2, 1] }, { id: 'N4', coordinates: [0, 1] },
  ],
  materials: [{ id: 'M1', model: 'saint-venant-kirchhoff', parameters: { young: 10_000_000, poisson: 0.3, plane_mode: 'plane_strain' } }],
  elements: [{ id: 'E1', formulation: 'Q4-total-lagrangian', node_ids: ['N1', 'N2', 'N3', 'N4'], material_id: 'M1', properties: { thickness: 0.1 } }],
  loads: [
    { id: 'P1', kind: 'nodal', node_id: 'N2', components: { UX: 50_000 } },
    { id: 'P2', kind: 'nodal', node_id: 'N3', components: { UX: 50_000 } },
  ],
  constraints: [
    { id: 'C1', node_id: 'N1', dof: 'UX', value: 0 },
    { id: 'C2', node_id: 'N1', dof: 'UY', value: 0 },
    { id: 'C3', node_id: 'N4', dof: 'UX', value: 0 },
  ],
  analysis: analysisOptions({
    tolerances: { residual: 1e-9, displacement: 1e-9, linear_solver: 1e-12 },
    step_control: { initial_step: 0.25, min_step: 0.25, max_step: 0.25, max_steps: 4, growth_factor: 1 },
  }),
  extensions: {
    purpose: 'Total Lagrangian continuum and raw Gauss-point recovery',
    scope: 'plane strain, 2x2 full integration',
    gmsh: { mesh_size: 0.5 },
  },
}

export const plateModel: ModelInput = {
  schema_version: '1.0.0', model_id: 'p13-von-karman-mitc4-cantilever', name: 'von Kármán MITC4 plate cantilever', model_family: 'plate',
  units: { length: 'm', force: 'N', stress: 'Pa', angle: 'rad', system_label: 'SI' },
  nodes: [
    { id: 'N1', coordinates: [0, 0] }, { id: 'N2', coordinates: [1, 0] },
    { id: 'N3', coordinates: [1, 1] }, { id: 'N4', coordinates: [0, 1] },
  ],
  materials: [{ id: 'M1', model: 'linear-elastic', parameters: { young: 21_000_000, poisson: 0.3 } }],
  elements: [{
    id: 'E1', formulation: 'Q4-von-karman-MITC4', node_ids: ['N1', 'N2', 'N3', 'N4'], material_id: 'M1',
    properties: { thickness: 0.05, plate_method: 'M', shear_scheme: 'mitc4', shear_correction: 5 / 6 },
  }],
  loads: [
    { id: 'P1', kind: 'nodal', node_id: 'N2', components: { UZ: -100 } },
    { id: 'P2', kind: 'nodal', node_id: 'N3', components: { UZ: -100 } },
  ],
  constraints: [
    { id: 'C1', node_id: 'N1', dof: 'UX', value: 0 }, { id: 'C2', node_id: 'N1', dof: 'UY', value: 0 },
    { id: 'C3', node_id: 'N1', dof: 'UZ', value: 0 }, { id: 'C4', node_id: 'N1', dof: 'RX', value: 0 },
    { id: 'C5', node_id: 'N1', dof: 'RY', value: 0 }, { id: 'C6', node_id: 'N2', dof: 'UX', value: 0 },
    { id: 'C7', node_id: 'N2', dof: 'UY', value: 0 }, { id: 'C8', node_id: 'N3', dof: 'UX', value: 0 },
    { id: 'C9', node_id: 'N3', dof: 'UY', value: 0 }, { id: 'C10', node_id: 'N4', dof: 'UX', value: 0 },
    { id: 'C11', node_id: 'N4', dof: 'UY', value: 0 }, { id: 'C12', node_id: 'N4', dof: 'UZ', value: 0 },
    { id: 'C13', node_id: 'N4', dof: 'RX', value: 0 }, { id: 'C14', node_id: 'N4', dof: 'RY', value: 0 },
  ],
  analysis: analysisOptions({
    max_iterations: 40,
    tolerances: { linear_solver: 1e-12 },
    step_control: { initial_step: 0.25, min_step: 0.015625, max_step: 0.25, growth_factor: 1 },
    line_search: { enabled: true, max_iterations: 10 },
  }),
  extensions: { scope: 'von Karman moderate rotations; not arbitrary finite rotations', gmsh: { mesh_size: 0.25 } },
}

export const shellModel: ModelInput = {
  schema_version: '1.0.0', model_id: 'p14-corotational-flat-shell-cantilever', name: 'Corotational Q4 flat-shell cantilever', model_family: 'shell',
  units: { length: 'm', force: 'N', stress: 'Pa', angle: 'rad', system_label: 'SI' },
  nodes: [
    { id: 'N1', coordinates: [0, 0, 0] }, { id: 'N2', coordinates: [1, 0, 0] },
    { id: 'N3', coordinates: [1, 1, 0] }, { id: 'N4', coordinates: [0, 1, 0] },
  ],
  materials: [{ id: 'M1', model: 'linear-elastic-isotropic', parameters: { young: 21_000_000, poisson: 0.3 } }],
  elements: [{
    id: 'E1', formulation: 'Q4-corotational-flat-shell-RM', node_ids: ['N1', 'N2', 'N3', 'N4'], material_id: 'M1',
    properties: { thickness: 0.05, shear_correction_factor: 5 / 6, alpha_d: 1e-4, differentiation_step: 2e-5 },
  }],
  loads: [
    { id: 'P1', kind: 'nodal', node_id: 'N2', components: { UZ: -1 } },
    { id: 'P2', kind: 'nodal', node_id: 'N3', components: { UZ: -1 } },
  ],
  constraints: [
    { id: 'C1', node_id: 'N1', dof: 'UX', value: 0 }, { id: 'C2', node_id: 'N1', dof: 'UY', value: 0 },
    { id: 'C3', node_id: 'N1', dof: 'UZ', value: 0 }, { id: 'C4', node_id: 'N1', dof: 'RX', value: 0 },
    { id: 'C5', node_id: 'N1', dof: 'RY', value: 0 }, { id: 'C6', node_id: 'N1', dof: 'RZ', value: 0 },
    { id: 'C7', node_id: 'N4', dof: 'UX', value: 0 }, { id: 'C8', node_id: 'N4', dof: 'UY', value: 0 },
    { id: 'C9', node_id: 'N4', dof: 'UZ', value: 0 }, { id: 'C10', node_id: 'N4', dof: 'RX', value: 0 },
    { id: 'C11', node_id: 'N4', dof: 'RY', value: 0 }, { id: 'C12', node_id: 'N4', dof: 'RZ', value: 0 },
  ],
  analysis: analysisOptions({
    tolerances: { linear_solver: 1e-11 },
    step_control: { initial_step: 0.5, min_step: 0.03125, max_step: 0.5, max_steps: 50, growth_factor: 1 },
    line_search: { enabled: true, max_iterations: 10 },
  }),
  extensions: { scope: 'large rigid-body rotation with small local flat-shell strain', gmsh: { mesh_size: 0.25 } },
}

export const sampleModels: Record<ModelFamily, ModelInput> = {
  frame: shallowArchModel,
  continuum: continuumModel,
  plate: plateModel,
  shell: shellModel,
}

export const cloneSampleModel = (family: ModelFamily = 'frame') => structuredClone(sampleModels[family])
