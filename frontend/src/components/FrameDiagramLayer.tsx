import { alpha, useTheme } from '@mui/material/styles'
import type { Point } from '../canvasViewport'
import type { ModelInput, Selection } from '../domain'
import { elementDisplayLabel } from '../entityLabels'
import { frameQuantityLabels, type FrameDiagram, type FrameQuantity } from '../frameDiagrams'
import { formatNumber } from '../resultUtils'

export function FrameDiagramLayer({ model, diagrams, quantity, positions, selection, onSelection }: {
  model: ModelInput; diagrams: FrameDiagram[]; quantity: FrameQuantity; positions: Map<string, Point>
  selection: Selection; onSelection: (selection: Selection) => void
}) {
  const theme = useTheme()
  const maximum = Math.max(1e-20, ...diagrams.flatMap(diagram => diagram.stations.map(p => Math.abs(p[quantity]))))
  return <g aria-label={`${frameQuantityLabels[quantity]} diagrams`}>
    {diagrams.map(diagram => {
      const element = model.elements.find(element => element.id === diagram.elementId)!
      const [a, b] = element.node_ids.map(id => positions.get(id))
      if (!a || !b) return null
      const length = Math.hypot(b.x - a.x, b.y - a.y)
      if (!length) return null
      const normal = { x: (b.y - a.y) / length, y: -(b.x - a.x) / length }
      const base = (ratio: number) => ({ x: a.x + (b.x - a.x) * ratio, y: a.y + (b.y - a.y) * ratio })
      const points = diagram.stations.map(station => {
        const point = base(station.ratio), offset = 52 * station[quantity] / maximum
        return { x: point.x + normal.x * offset, y: point.y + normal.y * offset }
      })
      const selected = selection.kind === 'elements' && selection.id === element.id
      const choose = () => onSelection({ kind: 'elements', id: element.id })
      const peakIndex = diagram.stations.reduce((best, point, index, all) => Math.abs(point[quantity]) > Math.abs(all[best][quantity]) ? index : best, 0)
      return <g key={element.id} role="button" tabIndex={0} aria-label={`${frameQuantityLabels[quantity]} diagram for ${elementDisplayLabel(model, element.id)}`}
        style={{ cursor: 'pointer' }} onClick={event => { event.stopPropagation(); choose() }}
        onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); event.stopPropagation(); choose() } }}>
        <title>{elementDisplayLabel(model, element.id)} · {frameQuantityLabels[quantity]} · peak {formatNumber(diagram.stations[peakIndex][quantity])}</title>
        <polygon points={[a, ...points, b].map(p => `${p.x},${p.y}`).join(' ')} fill={alpha(theme.palette.primary.main, selected ? 0.24 : 0.12)} />
        <polyline points={points.map(p => `${p.x},${p.y}`).join(' ')} fill="none" stroke="transparent" strokeWidth={14} />
        <polyline points={points.map(p => `${p.x},${p.y}`).join(' ')} fill="none" stroke={theme.palette.primary.main} strokeWidth={selected ? 3 : 1.8} />
        {[0, points.length - 1].map(i => <line key={i} x1={base(diagram.stations[i].ratio).x} y1={base(diagram.stations[i].ratio).y} x2={points[i].x} y2={points[i].y} stroke={theme.palette.primary.main} strokeWidth={1} />)}
        {selected && [...new Set([0, peakIndex, points.length - 1])].map(i => <text key={i} pointerEvents="none" x={points[i].x} y={points[i].y - 8} textAnchor="middle" fontSize={11} fill={theme.palette.primary.dark} stroke={theme.palette.background.canvas} strokeWidth={4} paintOrder="stroke">{formatNumber(diagram.stations[i][quantity])}</text>)}
      </g>
    })}
  </g>
}
