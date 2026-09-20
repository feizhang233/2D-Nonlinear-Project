import { useState, type ReactNode } from 'react'
import { Alert, Box, Button } from '@mui/material'
import { ScientificField } from '../components/ScientificField'
export type Field = { key: string; label: string; value: number; min?: number; positive?: boolean; max?: number; integer?: boolean }
/** Spatial forms commit a complete assignment and preserve partial numeric input. */
export function NumericForm({ fields, action, onSubmit, children, heading, assignment }: {
  fields: Field[]; action: string; onSubmit: (values: Record<string, number>, target: string) => void
  children?: ReactNode; heading?: ReactNode; assignment?: ReactNode; variant?: 'default' | 'library'
}) {
  const [values, setValues] = useState<Record<string, number>>(() => Object.fromEntries(fields.map(f => [f.key, Number(f.value.toPrecision(12))])))
  const [failure, setFailure] = useState('')
  return <Box component="form" noValidate onKeyDown={event => { if (event.key === 'Enter' && event.nativeEvent.isComposing) event.preventDefault() }} onSubmit={event => {
    event.preventDefault(); setFailure('')
    if (fields.some(f => !Number.isFinite(values[f.key]) || (f.positive && values[f.key] <= 0) || (f.min !== undefined && values[f.key] < f.min) || (f.max !== undefined && values[f.key] > f.max) || (f.integer && !Number.isInteger(values[f.key])))) {
      setFailure('Correct the highlighted values before applying.'); event.currentTarget.querySelector<HTMLInputElement>('input[aria-invalid="true"]')?.focus(); return
    }
    const target = ((event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null)?.value || 'defaults'
    try { onSubmit(values, target) } catch (error) { setFailure(error instanceof Error ? error.message : 'Unable to apply values.') }
  }} sx={{ display: 'grid', gap: 1.5 }}>
    {heading}
    <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2,minmax(0,1fr))', gap: 1 }}>
      {fields.map(f => <ScientificField key={f.key} label={f.label} value={values[f.key]} min={f.min} max={f.max} integer={f.integer} exclusiveMin={f.positive ? 0 : undefined} helperText=" " onValueChange={value => setValues(v => ({ ...v, [f.key]: value }))} />)}
    </Box>
    {children}
    {failure && <Alert severity="error">{failure}</Alert>}
    <Button type="submit" value="defaults" variant="contained" fullWidth>{action}</Button>
    {assignment}
  </Box>
}
