import { Alert, Button, MenuItem, Stack, TextField } from '@mui/material'
import { useState } from 'react'
import type { ModelInput, Selection } from '../domain'
import {
  holeDimensionError,
  upsertHole,
  type HoleDimensions,
  type HoleShape,
} from '../cadGeometry'
import { deleteSketchLoop } from '../geometrySketch'

export function HoleFields({
  value,
  onChange,
}: {
  value: HoleDimensions
  onChange: (next: HoleDimensions) => void
}) {
  return (
    <Stack spacing={1.5}>
      <TextField
        select
        label="Hole shape"
        value={value.kind}
        onChange={(event) =>
          onChange({
            ...value,
            kind: event.target.value as HoleDimensions['kind'],
          })
        }
      >
        <MenuItem value="circle">Circle</MenuItem>
        <MenuItem value="rectangle">Rectangle</MenuItem>
        <MenuItem value="square">Square</MenuItem>
      </TextField>
      {(value.kind === 'circle'
        ? (['radius'] as const)
        : value.kind === 'square'
          ? (['width'] as const)
          : (['width', 'height'] as const)
      ).map((key) => (
        <TextField
          key={key}
          type="number"
          label={
            key === 'radius'
              ? 'Radius'
              : key === 'width'
                ? value.kind === 'square'
                  ? 'Side length'
                  : 'Width'
                : 'Height'
          }
          value={Number.isFinite(value[key]) ? value[key] : ''}
          error={!Number.isFinite(value[key]) || value[key] <= 0}
          helperText={
            !Number.isFinite(value[key]) || value[key] <= 0
              ? 'Enter a dimension greater than zero.'
              : undefined
          }
          slotProps={{ htmlInput: { step: 'any', min: 0 } }}
          onChange={(event) =>
            onChange({
              ...value,
              [key]:
                event.target.value === '' ? NaN : Number(event.target.value),
            })
          }
        />
      ))}
    </Stack>
  )
}

export function HoleProperties({
  model,
  id,
  shape,
  onChange,
}: {
  model: ModelInput
  id: string
  shape: HoleShape
  onChange: (model: ModelInput, selection?: Selection) => void
}) {
  const [draft, setDraft] = useState(shape)
  const [error, setError] = useState('')
  return (
    <Stack spacing={2}>
      <HoleFields
        value={draft}
        onChange={(value) => {
          setDraft({ ...draft, ...value })
          setError('')
        }}
      />
      <Stack direction="row" spacing={1}>
        {['X', 'Y'].map((axis, i) => (
          <TextField
            key={axis}
            label={`Center ${axis}`}
            type="number"
            value={Number.isFinite(draft.center[i]) ? draft.center[i] : ''}
            slotProps={{ htmlInput: { step: 'any' } }}
            onChange={(event) =>
              setDraft({
                ...draft,
                center: draft.center.map((n, j) =>
                  j === i
                    ? event.target.value === ''
                      ? NaN
                      : Number(event.target.value)
                    : n,
                ),
              })
            }
          />
        ))}
      </Stack>
      {error && <Alert severity="error">{error}</Alert>}
      <Button
        variant="contained"
        disabled={
          Boolean(holeDimensionError(draft)) ||
          draft.center.some((n) => !Number.isFinite(n))
        }
        onClick={() => {
          try {
            const next = upsertHole(model, draft, id)
            onChange(next.model, { kind: 'geometry', id })
            setError('')
          } catch (reason) {
            setError(
              reason instanceof Error
                ? reason.message
                : 'Check the hole dimensions.',
            )
          }
        }}
      >
        Update hole
      </Button>
      <Button
        onClick={() => {
          setDraft(shape)
          setError('')
        }}
      >
        Reset dimensions
      </Button>
      <Button
        color="error"
        onClick={() =>
          onChange(deleteSketchLoop(model, id), { kind: 'geometry' })
        }
      >
        Delete hole
      </Button>
    </Stack>
  )
}
