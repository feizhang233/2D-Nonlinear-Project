import type { SolidModel } from '../continuum3d/model'
import type { PlateModel } from '../plate3d/model'
import type { ShellModel } from '../shell3d/model'
import { toSpatialPayload, type Model3D } from '../spatial/model'
import { postJson } from './transport'

export const solveSpatialFrame = (model: Model3D, signal?: AbortSignal) =>
  postJson('/api/v1/3d/solve', toSpatialPayload(model), signal)

export const solveContinuum3D = (model: SolidModel, signal?: AbortSignal) =>
  postJson('/api/v1/continuum3d/solve', model, signal)
export const validateContinuum3D = (model: SolidModel, signal?: AbortSignal) =>
  postJson('/api/v1/continuum3d/validate', model, signal)

export const solvePlate3D = (model: PlateModel, signal?: AbortSignal) =>
  postJson('/api/v1/plate3d/solve', model, signal)
export const validatePlate3D = (model: PlateModel, signal?: AbortSignal) =>
  postJson('/api/v1/plate3d/validate', model, signal)

export const solveShell3D = (model: ShellModel, signal?: AbortSignal) =>
  postJson('/api/v1/shell3d/solve', model, signal)
export const validateShell3D = (model: ShellModel, signal?: AbortSignal) =>
  postJson('/api/v1/shell3d/validate', model, signal)
