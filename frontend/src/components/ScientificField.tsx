import { InputAdornment, TextField } from '@mui/material'
import { useEffect, useState } from 'react'

export function parseScientificNumber(text: string): number {
  if (!/^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i.test(text.trim())) return NaN
  const value = Number(text)
  return Number.isFinite(value) ? value : NaN
}

/** Keep intermediate exponent text intact; NaN marks an unappliable form draft. */
export function ScientificField({ label, value, unit, onValueChange, helperText, min, max, exclusiveMin, exclusiveMax, integer, nonZero }: {
  label: string; value: number; unit?: string; onValueChange: (value: number) => void
  helperText?: string; min?: number; max?: number; exclusiveMin?: number; exclusiveMax?: number; integer?: boolean; nonZero?: boolean
}) {
  const [text, setText] = useState(String(value))
  useEffect(() => {
    if (Number.isFinite(value)) setText(current => parseScientificNumber(current) === value ? current : String(value))
  }, [value])
  const errorFor = (number: number): string | null => {
    if (!Number.isFinite(number)) return 'Enter a finite number, for example -2.5e4.'
    if (integer && !Number.isInteger(number)) return 'Enter a whole number.'
    if (nonZero && number === 0) return 'Enter a nonzero increment.'
    if (min !== undefined && number < min) return `Enter a number at least ${min}.`
    if (max !== undefined && number > max) return `Enter a number no greater than ${max}.`
    if (exclusiveMin !== undefined && number <= exclusiveMin) return `Enter a number greater than ${exclusiveMin}.`
    if (exclusiveMax !== undefined && number >= exclusiveMax) return `Enter a number less than ${exclusiveMax}.`
    return null
  }
  const error = errorFor(parseScientificNumber(text))
  return <TextField fullWidth label={label} type="text" value={text} error={Boolean(error)}
    helperText={error ?? helperText ?? (integer ? 'Whole number' : 'Decimal or scientific notation, e.g. -2.5e4')}
    slotProps={{ htmlInput: { inputMode: 'text', spellCheck: false }, input: {
      endAdornment: unit ? <InputAdornment position="end">{unit}</InputAdornment> : undefined,
    } }}
    onChange={event => {
      setText(event.target.value)
      const number = parseScientificNumber(event.target.value)
      onValueChange(errorFor(number) ? NaN : number)
    }} />
}
