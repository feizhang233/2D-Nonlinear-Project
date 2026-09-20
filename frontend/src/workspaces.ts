import type { ModelFamily } from './domain'

/** Dimension navigation selects an independent document in the same family. */
const SPATIAL_WORKSPACES = {
  frame3d: 'frame', continuum3d: 'continuum', plate3d: 'plate', shell3d: 'shell',
} as const satisfies Record<string, ModelFamily>
export type SpatialFamily = keyof typeof SPATIAL_WORKSPACES
export type WorkspaceId = ModelFamily | SpatialFamily

export const isSpatialWorkspace = (id: WorkspaceId): id is SpatialFamily =>
  Object.hasOwn(SPATIAL_WORKSPACES, id)
export const workspaceFamily = (id: WorkspaceId): ModelFamily =>
  isSpatialWorkspace(id) ? SPATIAL_WORKSPACES[id] : id
export const spatialWorkspace = (family: ModelFamily): SpatialFamily => `${family}3d`
