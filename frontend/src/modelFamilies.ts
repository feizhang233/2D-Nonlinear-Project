import type { Dof, JsonValue, ModelFamily, ModelInput, RunOptions } from './domain'

export interface ModelFamilyInfo {
  family: ModelFamily
  label: string
  shortLabel: string
  formulation: string
  capability: string
  projectionNote: string
  elementNodeCount: 2 | 4
  defaultDofs: Dof[]
  primaryLoadDof: Dof
  defaultRunOptions: RunOptions
  defaultMaterial: { model: string; parameters: Record<string, JsonValue> }
  defaultElementProperties: Record<string, JsonValue>
}

export const MODEL_FAMILIES: Record<ModelFamily, ModelFamilyInfo> = {
  frame: {
    family: 'frame', label: 'Frame', shortLabel: 'Frame',
    formulation: 'frame2d-corotational',
    capability: '2-node corotational Euler–Bernoulli; large rigid rotation and small strain.',
    projectionNote: '2D line elements; deformation uses UX / UY.',
    elementNodeCount: 2,
    defaultDofs: ['UX', 'UY', 'RZ'],
    primaryLoadDof: 'UY',
    defaultRunOptions: { targetLoadFactor: 0.25, numberOfSteps: 8 },
    defaultMaterial: { model: 'linear-elastic', parameters: { young: 10_000_000 } },
    defaultElementProperties: { area: 0.01, second_moment: 1e-8 },
  },
  continuum: {
    family: 'continuum', label: 'Continuum', shortLabel: 'Continuum',
    formulation: 'Q4-total-lagrangian',
    capability: 'Total Lagrangian Q4; Saint-Venant–Kirchhoff plane strain.',
    projectionNote: 'Q4 surface elements; UX / UY and Gauss-point Cauchy stress.',
    elementNodeCount: 4,
    defaultDofs: ['UX', 'UY'],
    primaryLoadDof: 'UX',
    defaultRunOptions: { targetLoadFactor: 1, numberOfSteps: 4 },
    defaultMaterial: { model: 'saint-venant-kirchhoff', parameters: { young: 10_000_000, poisson: 0.3, plane_mode: 'plane_strain' } },
    defaultElementProperties: { thickness: 0.1 },
  },
  plate: {
    family: 'plate', label: 'Plate', shortLabel: 'Plate',
    formulation: 'Q4-von-karman-MITC4',
    capability: 'von Kármán Q4 + MITC4; moderate rotation and small strain.',
    projectionNote: 'Q4 engineering projection; UZ is shown as an oblique lift, not 3D perspective.',
    elementNodeCount: 4,
    defaultDofs: ['UX', 'UY', 'UZ', 'RX', 'RY'],
    primaryLoadDof: 'UZ',
    defaultRunOptions: { targetLoadFactor: 1, numberOfSteps: 4 },
    defaultMaterial: { model: 'linear-elastic', parameters: { young: 21_000_000, poisson: 0.3 } },
    defaultElementProperties: { thickness: 0.05, plate_method: 'M', shear_scheme: 'mitc4', shear_correction: 5 / 6 },
  },
  shell: {
    family: 'shell', label: 'Shell', shortLabel: 'Shell',
    formulation: 'Q4-corotational-flat-shell-RM',
    capability: '6-DOF corotational flat shell; large rigid rotation and small local strain.',
    projectionNote: 'Q4 engineering projection; UZ is shown as an oblique lift, not a general curved-shell 3D view.',
    elementNodeCount: 4,
    defaultDofs: ['UX', 'UY', 'UZ', 'RX', 'RY', 'RZ'],
    primaryLoadDof: 'UZ',
    defaultRunOptions: { targetLoadFactor: 1, numberOfSteps: 2 },
    defaultMaterial: { model: 'linear-elastic-isotropic', parameters: { young: 21_000_000, poisson: 0.3 } },
    defaultElementProperties: { thickness: 0.05, shear_correction_factor: 5 / 6, alpha_d: 1e-4, differentiation_step: 2e-5 },
  },
}

export const MODEL_FAMILY_ORDER: ModelFamily[] = ['frame', 'continuum', 'plate', 'shell']

export function dofsForModel(model: ModelInput): Dof[] {
  if (model.model_family === 'plate') {
    const isVonKarman = model.elements.some((element) => element.formulation.toLowerCase().replaceAll('_', '-').includes('von-karman'))
    return isVonKarman ? MODEL_FAMILIES.plate.defaultDofs : ['UZ', 'RX', 'RY']
  }
  return MODEL_FAMILIES[model.model_family].defaultDofs
}

export const defaultRunOptions = (family: ModelFamily): RunOptions => ({ ...MODEL_FAMILIES[family].defaultRunOptions })
