import { InputAdornment, TextField } from '@mui/material'
import { useEffect, useState } from 'react'

export function parseScientificNumber(text: string): number {
  if (!/^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i.test(text.trim())) return NaN
  const value = Number(text)
  return Number.isFinite(value) ? value : NaN
}

/** Keep intermediate exponent text intact; NaN marks an unappliable form draft. */
export function ScientificField({ label, value, unit, onValueChange }: {
  label: string; value: number; unit?: string; onValueChange: (value: number) => void
}) {
  const [text, setText] = useState(String(value))
  useEffect(() => {
    if (Number.isFinite(value)) setText(current => parseScientificNumber(current) === value ? current : String(value))
  }, [value])
  const invalid = !Number.isFinite(parseScientificNumber(text))
  return <TextField fullWidth label={label} type="text" value={text} error={invalid}
    helperText={invalid ? 'Enter a finite number, for example -2.5e4.' : 'Decimal or scientific notation, e.g. -2.5e4'}
    slotProps={{ htmlInput: { inputMode: 'text', spellCheck: false }, input: {
      endAdornment: unit ? <InputAdornment position="end">{unit}</InputAdornment> : undefined,
    } }}
    onChange={event => { setText(event.target.value); onValueChange(parseScientificNumber(event.target.value)) }} />
}
