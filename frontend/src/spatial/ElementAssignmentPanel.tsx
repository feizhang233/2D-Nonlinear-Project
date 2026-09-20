import { Box, Button, Typography } from '@mui/material'
import { useState, type ReactNode } from 'react'
export type AssignmentRow = { id: number; label: ReactNode; title?: string }
export function ElementAssignmentPanel({ kind, rows, selectedCount = 0 }: {
  kind: 'material' | 'section'; rows: AssignmentRow[]; selectedCount?: number
}) {
  const [limit, setLimit] = useState(60)
  return <Box component="section" aria-label={`${kind === 'material' ? 'Material' : 'Section'} apply to elements`} sx={{ display: 'grid', gap: 1, mt: 2 }}>
    <Typography variant="subtitle2">Apply to elements</Typography>
    <Box sx={{ display: 'flex', gap: 1 }}>
      <Button type="submit" value="all" variant="outlined" disabled={!rows.length} aria-label={`Apply ${kind} to all elements`}>Apply all</Button>
      <Button type="submit" value="selected" variant="outlined" disabled={!selectedCount}>Apply to selected ({selectedCount})</Button>
    </Box>
    <Box sx={{ display: 'grid', maxHeight: 240, overflow: 'auto' }}>
      {rows.slice(0, limit).map(row => <Button key={row.id} type="submit" value={`element:${row.id}`} aria-label={`Apply ${kind} to E${row.id}`} sx={{ justifyContent: 'space-between', borderBottom: '1px solid', borderColor: 'divider', gap: 1 }}><span>E{row.id}</span><Typography variant="caption">{row.label}</Typography></Button>)}
      {!rows.length && <Typography variant="caption">Create a member before assigning properties.</Typography>}
      {rows.length > limit && <Button onClick={() => setLimit(n => n + 60)}>Show more</Button>}
    </Box>
  </Box>
}
