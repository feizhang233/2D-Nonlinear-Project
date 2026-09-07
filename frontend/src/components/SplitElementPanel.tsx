import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded'
import {
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Alert,
  Button,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { useState } from 'react'
import type { ModelInput, Selection } from '../domain'
import { parseSplitPositions, splitFrameElement } from '../modelOperations'

export function SplitElementPanel({
  model,
  elementId,
  onChange,
}: {
  model: ModelInput
  elementId: string
  onChange: (model: ModelInput, selection?: Selection) => void
}) {
  const [text, setText] = useState('1/2')
  const [error, setError] = useState<string | null>(null)
  return (
    <Accordion id="split-member-panel">
      <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
        <Typography component="span" variant="subtitle2">Split member</Typography>
      </AccordionSummary>
      <AccordionDetails>
        <Stack spacing={1.25}>
          <Typography variant="caption" color="text.secondary">
            Positions measured from the i node. Each cut adds a node and connects the resulting
            members.
          </Typography>
          <Stack direction="row" spacing={0.5}>
            {[
              ['Half', '1/2'],
              ['Quarters', '1/4, 1/2, 3/4'],
              ['Thirds', '1/3, 2/3'],
            ].map(([label, value]) => (
              <Button
                key={label}
                size="small"
                variant="outlined"
                onClick={() => {
                  setText(value)
                  setError(null)
                }}
              >
                {label}
              </Button>
            ))}
          </Stack>
          <TextField
            label="Split positions"
            value={text}
            error={Boolean(error)}
            helperText={error ?? 'Fractions or decimals, separated by commas: 1/4, 0.6'}
            onChange={(event) => {
              setText(event.target.value)
              setError(null)
            }}
          />
          <Button
            variant="contained"
            onClick={() => {
              try {
                const next = splitFrameElement(model, elementId, parseSplitPositions(text))
                onChange(next, { kind: 'elements', id: elementId })
                setError(null)
              } catch (e) {
                setError(e instanceof Error ? e.message : 'Could not split this member.')
              }
            }}
          >
            Split element
          </Button>
          <Alert severity="info">
            Materials and sections are retained. Distributed loads are interpolated onto the new
            members. Apply changes to commit.
          </Alert>
        </Stack>
      </AccordionDetails>
    </Accordion>
  )
}
