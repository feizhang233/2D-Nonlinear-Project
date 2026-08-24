import Box from '@mui/material/Box'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import { useTheme } from '@mui/material/styles'
import { useMemo } from 'react'
import { formatNumber } from '../resultUtils'

interface Series {
  name: string
  color: string
  points: Array<{ x: number; y: number }>
}

interface MiniChartProps {
  title: string
  xLabel: string
  yLabel: string
  series: Series[]
  logY?: boolean
  emptyText?: string
}

export function MiniChart({ title, xLabel, yLabel, series, logY = false, emptyText = 'No data available to plot' }: MiniChartProps) {
  const theme = useTheme()
  const prepared = useMemo(() => {
    const all = series.flatMap((item) => item.points).filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y))
    if (!all.length) return null
    const yValue = (value: number) => logY ? Math.log10(Math.max(value, 1e-30)) : value
    const xs = all.map((point) => point.x)
    const ys = all.map((point) => yValue(point.y))
    const xMin = Math.min(...xs)
    const xMax = Math.max(...xs)
    const yMin = Math.min(...ys)
    const yMax = Math.max(...ys)
    const xSpan = xMax - xMin || 1
    const ySpan = yMax - yMin || 1
    const path = (points: Array<{ x: number; y: number }>) => points.map((point, index) => {
      const x = 46 + ((point.x - xMin) / xSpan) * 302
      const y = 14 + (1 - (yValue(point.y) - yMin) / ySpan) * 112
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`
    }).join(' ')
    return { xMin, xMax, yMin, yMax, path }
  }, [logY, series])

  const plotFill = theme.palette.background.containerLow
  const grid = theme.palette.divider
  const axis = theme.palette.text.secondary

  return (
    <Box sx={{ minWidth: 0 }}>
      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
        <Typography variant="subtitle2">{title}</Typography>
        <Stack direction="row" spacing={1}>
          {series.map((item) => (
            <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center' }} key={item.name}>
              <Box sx={{ width: 12, height: 3, borderRadius: 2, bgcolor: item.color }} />
              <Typography variant="caption" color="text.secondary">{item.name}</Typography>
            </Stack>
          ))}
        </Stack>
      </Stack>
      {prepared ? (
        <svg viewBox="0 0 370 158" role="img" aria-label={title} style={{ width: '100%', height: 150, display: 'block' }}>
          <rect x="46" y="14" width="302" height="112" rx="8" fill={plotFill} stroke={grid} />
          {[0, 0.5, 1].map((fraction) => <line key={fraction} x1="46" x2="348" y1={14 + fraction * 112} y2={14 + fraction * 112} stroke={grid} />)}
          {series.map((item) => <path key={item.name} d={prepared.path(item.points)} fill="none" stroke={item.color} strokeWidth="2.3" strokeLinejoin="round" />)}
          <text x="46" y="143" fontSize="9" fill={axis}>{formatNumber(prepared.xMin)}</text>
          <text x="348" y="143" textAnchor="end" fontSize="9" fill={axis}>{formatNumber(prepared.xMax)}</text>
          <text x="40" y="20" textAnchor="end" fontSize="9" fill={axis}>{formatNumber(logY ? 10 ** prepared.yMax : prepared.yMax)}</text>
          <text x="40" y="126" textAnchor="end" fontSize="9" fill={axis}>{formatNumber(logY ? 10 ** prepared.yMin : prepared.yMin)}</text>
          <text x="197" y="156" textAnchor="middle" fontSize="9" fill={axis}>{xLabel}</text>
          <text transform="translate(10 70) rotate(-90)" textAnchor="middle" fontSize="9" fill={axis}>{yLabel}</text>
        </svg>
      ) : (
        <Box sx={{ height: 150, display: 'grid', placeItems: 'center', bgcolor: 'background.containerLow', borderRadius: 2 }}>
          <Typography variant="caption" color="text.secondary">{emptyText}</Typography>
        </Box>
      )}
    </Box>
  )
}
