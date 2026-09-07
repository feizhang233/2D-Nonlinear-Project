import { Alert, MenuItem, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography } from '@mui/material'
import type { ModelInput, Selection, SolveResult } from '../domain'
import { elementDisplayLabel } from '../entityLabels'
import { frameDiagrams } from '../frameDiagrams'
import { formatNumber } from '../resultUtils'

export function FrameSectionTable({ model, result, selection, onSelection }: { model: ModelInput; result: SolveResult; selection: Selection; onSelection: (selection: Selection) => void }) {
  const diagrams = frameDiagrams(model, result)
  const diagram = diagrams.find(d => selection.kind === 'elements' && d.elementId === selection.id) ?? diagrams[0]
  if (!diagram) return <Alert severity="info">No recovered Frame end actions are available in this result.</Alert>
  return <Stack spacing={1.5}>
    <Typography variant="subtitle2">Member section forces · last accepted state</Typography>
    <TextField select label="Diagram member" value={diagram.elementId} onChange={event => onSelection({ kind: 'elements', id: event.target.value })}>
      {diagrams.map(d => <MenuItem key={d.elementId} value={d.elementId}>{elementDisplayLabel(model, d.elementId)}</MenuItem>)}
    </TextField>
    {diagram.memberLoads && <Alert severity="info">Member-load corrections use reference local axes. Large-rotation distributed-load stress recovery is approximate.</Alert>}
    <TableContainer sx={{ maxHeight: 280 }}><Table size="small" stickyHeader aria-label="Member section forces">
      <TableHead><TableRow>{['x (m)', 'N (N)', 'V (N)', 'M (N·m)'].map(label => <TableCell key={label}>{label}</TableCell>)}</TableRow></TableHead>
      <TableBody>{diagram.stations.map(point => <TableRow key={point.ratio}>{[point.x, point.axial, point.shear, point.moment].map((value, index) => <TableCell key={index}>{formatNumber(value)}</TableCell>)}</TableRow>)}</TableBody>
    </Table></TableContainer>
    <Typography variant="caption">x follows i → j. N is positive in tension; V = dM/dx. M(0) = −Mᵢ and M(L) = Mⱼ after member-load correction.</Typography>
  </Stack>
}
