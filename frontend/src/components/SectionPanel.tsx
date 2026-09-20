import {
  Alert,
  Box,
  Button,
  Checkbox,
  Divider,
  FormControlLabel,
  InputAdornment,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { useState } from 'react'
import type { ModelInput, Selection } from '../domain'
import { elementDisplayLabel } from '../entityLabels'
import {
  addSection,
  assignSection,
  defaultDimensions,
  sectionIdForElement,
  sectionLibrary,
  sectionProperties,
  setDefaultSection,
  updateSection,
  type SectionDefinition,
  type SectionShape,
} from '../sections'

const SECTION_SHAPES: Record<SectionShape, string> = {
  custom: 'Custom',
  rectangle: 'Rectangle',
  circle: 'Circle',
  i_section: 'I section',
  tube: 'Tube',
  thickness: 'Uniform thickness',
}
const LABELS: Record<string, string> = {
  area: 'Cross-sectional area A',
  second_moment: 'Second moment I',
  width: 'Width b',
  height: 'Height h',
  diameter: 'Diameter d',
  outer_diameter: 'Outer diameter D',
  wall_thickness: 'Wall thickness t',
  web_thickness: 'Web thickness tw',
  flange_thickness: 'Flange thickness tf',
  thickness: 'Thickness t',
}

function Definition({
  model,
  section,
  onChange,
}: {
  model: ModelInput
  section: SectionDefinition
  onChange: (model: ModelInput, selection?: Selection) => void
}) {
  const [visible, setVisible] = useState(30)
  const library = sectionLibrary(model)
  const assigned = model.elements.filter(
    (element) => sectionIdForElement(model, element) === section.id,
  )
  let error = ''
  let values: Record<string, number> = {}
  try {
    values = sectionProperties(section)
  } catch (e) {
    error = e instanceof Error ? e.message : 'Check dimensions.'
  }
  const update = (patch: Partial<SectionDefinition>) =>
    onChange(updateSection(model, { ...section, ...patch }), {
      kind: 'sections',
      id: section.id,
    })
  return (
    <Stack spacing={2}>
      <Box>
        <Typography variant="overline">
          Section definition · {section.id}
        </Typography>
        <Typography variant="h6">
          {section.name || 'Unnamed section'}
        </Typography>
      </Box>
      <TextField
        label="Section name"
        value={section.name}
        error={!section.name.trim()}
        helperText={!section.name.trim() ? 'Enter a section name.' : undefined}
        slotProps={{ htmlInput: { maxLength: 80 } }}
        onChange={(event) => update({ name: event.target.value })}
      />
      <TextField
        select
        label="Section shape"
        value={section.shape}
        onChange={(event) => {
          const shape = event.target.value as SectionShape
          update({ shape, dimensions: defaultDimensions(shape) })
        }}
      >
        {(model.model_family === 'frame'
          ? (['custom', 'rectangle', 'circle', 'i_section', 'tube'] as const)
          : (['thickness'] as const)
        ).map((shape) => (
          <MenuItem key={shape} value={shape}>
            {SECTION_SHAPES[shape]}
          </MenuItem>
        ))}
      </TextField>
      <Box
        sx={{
          py: 1.5,
          bgcolor: 'background.containerLow',
          borderRadius: 1,
          textAlign: 'center',
        }}
      >
        <svg
          viewBox="0 0 180 90"
          width="100%"
          height="90"
          aria-label={`${SECTION_SHAPES[section.shape]} cross-section`}
          role="img"
          style={{ color: 'var(--mui-palette-primary-main)' }}
        >
          <g
            fill="currentColor"
            fillOpacity="0.18"
            stroke="currentColor"
            strokeWidth="2"
          >
            {section.shape === 'circle' || section.shape === 'tube' ? (
              <>
                <circle cx="90" cy="45" r="32" />
                {section.shape === 'tube' && (
                  <circle
                    cx="90"
                    cy="45"
                    r="23"
                    fill="var(--mui-palette-background-containerLow)"
                  />
                )}
              </>
            ) : section.shape === 'i_section' ? (
              <path d="M55 12H125V23H96V67H125V78H55V67H84V23H55Z" />
            ) : (
              <rect
                x="45"
                y={section.shape === 'thickness' ? 35 : 15}
                width="90"
                height={section.shape === 'thickness' ? 20 : 60}
              />
            )}
          </g>
          <path
            d="M18 45H162M90 3V87"
            stroke="currentColor"
            strokeOpacity="0.4"
            strokeDasharray="4 4"
          />
        </svg>
        <Typography variant="caption" color="text.secondary">
          {section.shape === 'thickness'
            ? 'Uniform through-thickness property'
            : 'Centroidal bending about the horizontal axis'}
        </Typography>
      </Box>
      {Object.entries(section.dimensions).map(([key, value]) => (
        <TextField
          key={key}
          type="number"
          label={LABELS[key] ?? key}
          value={value || ''}
          error={!Number.isFinite(value) || value <= 0}
          helperText={
            !Number.isFinite(value) || value <= 0
              ? 'Enter a positive value.'
              : undefined
          }
          slotProps={{
            htmlInput: { step: 'any' },
            input: {
              endAdornment: (
                <InputAdornment position="end">
                  {model.units.length}
                  {key === 'area' ? '²' : key === 'second_moment' ? '⁴' : ''}
                </InputAdornment>
              ),
            },
          }}
          onChange={(event) =>
            update({
              dimensions: {
                ...section.dimensions,
                [key]: Number(event.target.value),
              },
            })
          }
        />
      ))}
      {error ? (
        <Alert severity="error">{error}</Alert>
      ) : (
        section.shape !== 'custom' && (
          <Box sx={{ p: 1.5, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
            {Object.entries(values).map(([key, value]) => (
              <Stack
                key={key}
                direction="row"
                sx={{ justifyContent: 'space-between' }}
              >
                <Typography variant="caption">
                  {key === 'area'
                    ? 'Area A'
                    : key === 'second_moment'
                      ? 'Second moment I'
                      : 'Thickness'}
                </Typography>
                <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                  {value.toExponential(4)}
                </Typography>
              </Stack>
            ))}
          </Box>
        )
      )}
      <FormControlLabel
        control={
          <Checkbox
            checked={library.default_id === section.id}
            disabled={Boolean(error) || library.default_id === section.id}
            onChange={() => onChange(setDefaultSection(model, section.id))}
          />
        }
        label="Use for new elements"
      />
      <Divider />
      <Stack
        direction="row"
        sx={{ justifyContent: 'space-between', alignItems: 'center' }}
      >
        <Box>
          <Typography variant="subtitle2">Element assignment</Typography>
          <Typography variant="caption" color="text.secondary">
            {assigned.length} of {model.elements.length} assigned
          </Typography>
        </Box>
        <Button
          variant="outlined"
          disabled={Boolean(error) || !model.elements.length}
          onClick={() =>
            onChange(
              assignSection(
                model,
                section.id,
                model.elements.map((e) => e.id),
              ),
            )
          }
        >
          Assign all
        </Button>
      </Stack>
      <Typography variant="caption" color="text.secondary">
        Choose an element to assign this section. To remove an assignment,
        choose another section.
      </Typography>
      <Stack spacing={0.5}>
        {model.elements.slice(0, visible).map((element) => {
          const selected = sectionIdForElement(model, element) === section.id
          return (
            <Button
              key={element.id}
              variant={selected ? 'contained' : 'outlined'}
              aria-pressed={selected}
              disabled={Boolean(error)}
              onClick={() =>
                onChange(assignSection(model, section.id, [element.id]))
              }
              sx={{ justifyContent: 'space-between' }}
            >
              <span>{elementDisplayLabel(model, element.id)}</span>
              <Typography component="span" variant="caption">
                {selected ? 'Assigned' : 'Assign'}
              </Typography>
            </Button>
          )
        })}
      </Stack>
      {model.elements.length > visible && (
        <Button onClick={() => setVisible((n) => n + 30)}>
          Show 30 more elements
        </Button>
      )}
    </Stack>
  )
}

export function SectionPanel({
  model,
  selection,
  onChange,
}: {
  model: ModelInput
  selection: Selection
  onChange: (model: ModelInput, selection?: Selection) => void
}) {
  const section = sectionLibrary(model).definitions.find(
    (item) => item.id === selection.id,
  )
  if (section)
    return (
      <Definition
        key={`${model.model_id}-${section.id}`}
        model={model}
        section={section}
        onChange={onChange}
      />
    )
  return (
    <Stack spacing={2}>
      <Typography variant="h6">Section library</Typography>
      <Typography variant="body2" color="text.secondary">
        Define reusable{' '}
        {model.model_family === 'frame'
          ? 'cross-sections and assign area and bending stiffness'
          : 'thicknesses'}{' '}
        to your elements. Changes to a definition update all assigned elements.
      </Typography>
      <Button
        variant="contained"
        onClick={() => {
          const added = addSection(model)
          onChange(added.model, { kind: 'sections', id: added.id })
        }}
      >
        New section
      </Button>
    </Stack>
  )
}
