import { useState } from 'react'
import type { SpatialFamily } from '../workspaces'

/** Visit once, keep mounted: document, camera and unfinished fields stay local. */
export function useSpatialNavigation() {
  const [active, setActive] = useState<SpatialFamily | false>(false)
  const [visited, setVisited] = useState<Set<SpatialFamily>>(() => new Set())
  const open = (family: SpatialFamily) => {
    setVisited(previous => previous.has(family) ? previous : new Set([...previous, family]))
    setActive(family)
  }
  return { active, visited, open, close: () => setActive(false) }
}
