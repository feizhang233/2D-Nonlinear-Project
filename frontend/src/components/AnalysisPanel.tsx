import AutoFixHighRoundedIcon from '@mui/icons-material/AutoFixHighRounded'
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded'
import HelpOutlineRoundedIcon from '@mui/icons-material/HelpOutlineRounded'
import Accordion from '@mui/material/Accordion'
import AccordionDetails from '@mui/material/AccordionDetails'
import AccordionSummary from '@mui/material/AccordionSummary'
import Alert from '@mui/material/Alert'
import FormControlLabel from '@mui/material/FormControlLabel'
import MenuItem from '@mui/material/MenuItem'
import Stack from '@mui/material/Stack'
import Switch from '@mui/material/Switch'
import TextField from '@mui/material/TextField'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import type { ControlMethod, Dof, ModelInput, RunOptions } from '../domain'
import { nodeDisplayLabel } from '../entityLabels'
import { dofsForModel, MODEL_FAMILIES } from '../modelFamilies'
import { SectionHeader } from './chrome'

interface AnalysisPanelProps {
  model: ModelInput
  runOptions: RunOptions
  onModelChange: (model: ModelInput) => void
  onRunOptionsChange: (options: Partial<RunOptions>) => void
}

const numeric = (value: string, fallback: number) => Number.isFinite(Number(value)) ? Number(value) : fallback

export function AnalysisPanel({ model, runOptions, onModelChange, onRunOptionsChange }: AnalysisPanelProps) {
  const options = model.analysis
  const family = MODEL_FAMILIES[model.model_family]
  const dofs = dofsForModel(model)
  const patchAnalysis = (patch: Partial<ModelInput['analysis']>) => onModelChange({ ...model, analysis: { ...options, ...patch } })
  const setControl = (control: ControlMethod) => {
    const analysis = structuredClone(options)
    analysis.control_method = control
    delete analysis.displacement_control
    delete analysis.arc_length
    if (control === 'displacement') {
      const loaded = model.loads.flatMap((load) => dofs
        .filter((dof) => load.node_id && Math.abs(load.components[dof] ?? 0) > 0)
        .map((dof) => ({ node_id: load.node_id as string, dof, value: load.components[dof] ?? 0 })))[0]
      const free = model.nodes.flatMap((node) => dofs.map((dof) => ({ node_id: node.id, dof })))
        .find((candidate) => !model.constraints.some((constraint) => constraint.node_id === candidate.node_id && constraint.dof === candidate.dof))
      const target = loaded ?? { ...(free ?? { node_id: model.nodes[0]?.id ?? '', dof: family.primaryLoadDof }), value: -1 }
      analysis.displacement_control = {
        target: { node_id: target.node_id, dof: target.dof },
        increment: Math.sign(target.value || -1) * 0.01,
      }
    }
    if (control === 'arc_length') {
      analysis.arc_length = { radius: 0.05, min_radius: 1e-4, max_radius: 0.15, beta: 1, root_selection: 'direction_continuity' }
      analysis.line_search.enabled = false
    }
    onModelChange({ ...model, analysis })
  }

  return (
    <Stack spacing={2}>
      <SectionHeader
        icon={<AutoFixHighRoundedIcon fontSize="small" />}
        title="Nonlinear analysis"
        subtitle={`${family.label} · ${dofs.join(' / ')}`}
      />
      <ToggleButtonGroup exclusive fullWidth size="small" value={options.control_method} onChange={(_, value: ControlMethod | null) => value && setControl(value)}>
        <ToggleButton value="load">Load</ToggleButton>
        <ToggleButton value="displacement">Displacement</ToggleButton>
        <ToggleButton value="arc_length">Arc length</ToggleButton>
      </ToggleButtonGroup>

      {options.control_method === 'load' && (
        <TextField
          type="number"
          label="Target load factor"
          value={runOptions.targetLoadFactor}
          slotProps={{ htmlInput: { step: 'any' } }}
          onChange={(event) => onRunOptionsChange({ targetLoadFactor: numeric(event.target.value, runOptions.targetLoadFactor) })}
          helperText="The adaptive solver advances from the zero state or imported committed state to this load factor."
        />
      )}
      {options.control_method === 'displacement' && options.displacement_control && (
        <Stack spacing={1.5}>
          <Stack direction="row" spacing={1}>
            <TextField select fullWidth label="Control node" value={options.displacement_control.target.node_id} onChange={(event) => patchAnalysis({ displacement_control: { ...options.displacement_control!, target: { ...options.displacement_control!.target, node_id: event.target.value } } })}>
              {model.nodes.map((node) => <MenuItem value={node.id} key={node.id}>{nodeDisplayLabel(model, node.id)}</MenuItem>)}
            </TextField>
            <TextField select fullWidth label="Degree of freedom" value={options.displacement_control.target.dof} onChange={(event) => patchAnalysis({ displacement_control: { ...options.displacement_control!, target: { ...options.displacement_control!.target, dof: event.target.value as Dof } } })}>
              {dofs.map((dof) => <MenuItem value={dof} key={dof}>{dof}</MenuItem>)}
            </TextField>
          </Stack>
          <Stack direction="row" spacing={1}>
            <TextField type="number" label="Displacement increment" value={options.displacement_control.increment} slotProps={{ htmlInput: { step: 'any' } }} onChange={(event) => patchAnalysis({ displacement_control: { ...options.displacement_control!, increment: numeric(event.target.value, options.displacement_control!.increment) } })} />
            <TextField type="number" label="Steps" value={runOptions.numberOfSteps} slotProps={{ htmlInput: { min: 1, step: 1 } }} onChange={(event) => onRunOptionsChange({ numberOfSteps: Math.max(1, Math.round(numeric(event.target.value, runOptions.numberOfSteps))) })} />
          </Stack>
        </Stack>
      )}
      {options.control_method === 'arc_length' && options.arc_length && (
        <Stack spacing={1.5}>
          <Stack direction="row" spacing={1}>
            <TextField type="number" label="Arc-length radius" value={options.arc_length.radius} slotProps={{ htmlInput: { step: 'any' } }} onChange={(event) => patchAnalysis({ arc_length: { ...options.arc_length!, radius: numeric(event.target.value, options.arc_length!.radius) } })} />
            <TextField type="number" label="Steps" value={runOptions.numberOfSteps} slotProps={{ htmlInput: { min: 1, step: 1 } }} onChange={(event) => onRunOptionsChange({ numberOfSteps: Math.max(1, Math.round(numeric(event.target.value, runOptions.numberOfSteps))) })} />
          </Stack>
          <Stack direction="row" spacing={1}>
            <TextField type="number" label="Minimum radius" value={options.arc_length.min_radius} slotProps={{ htmlInput: { step: 'any' } }} onChange={(event) => patchAnalysis({ arc_length: { ...options.arc_length!, min_radius: numeric(event.target.value, options.arc_length!.min_radius) } })} />
            <TextField type="number" label="Maximum radius" value={options.arc_length.max_radius} slotProps={{ htmlInput: { step: 'any' } }} onChange={(event) => patchAnalysis({ arc_length: { ...options.arc_length!, max_radius: numeric(event.target.value, options.arc_length!.max_radius) } })} />
          </Stack>
          <TextField type="number" label="Load scaling β" value={options.arc_length.beta} slotProps={{ htmlInput: { step: 'any' } }} onChange={(event) => patchAnalysis({ arc_length: { ...options.arc_length!, beta: numeric(event.target.value, options.arc_length!.beta) } })} />
          <Alert severity="info">Arc-length convergence only shows that the augmented equilibrium equations satisfy the specified tolerances. It does not prove stability, branch uniqueness, or branch switching.</Alert>
        </Stack>
      )}

      <Accordion defaultExpanded>
        <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
          <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center' }}>
            <Typography variant="subtitle2">Newton method and tolerances</Typography>
            <Tooltip title="Residual, displacement correction, and energy metrics all contribute to convergence checks">
              <HelpOutlineRoundedIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
            </Tooltip>
          </Stack>
        </AccordionSummary>
        <AccordionDetails>
          <Stack spacing={1.5}>
            <Stack direction="row" spacing={1}>
              <TextField select fullWidth label="Newton method" value={options.newton_method} onChange={(event) => patchAnalysis({ newton_method: event.target.value as 'full' | 'modified' })}>
                <MenuItem value="full">Full Newton</MenuItem>
                <MenuItem value="modified">Modified Newton</MenuItem>
              </TextField>
              <TextField type="number" fullWidth label="Maximum iterations" value={options.max_iterations} slotProps={{ htmlInput: { min: 1, step: 1 } }} onChange={(event) => patchAnalysis({ max_iterations: Math.max(1, Math.round(numeric(event.target.value, options.max_iterations))) })} />
            </Stack>
            {(['residual', 'displacement', 'energy'] as const).map((key) => (
              <TextField
                key={key}
                type="number"
                label={`${key === 'residual' ? 'Residual' : key === 'displacement' ? 'Displacement correction' : 'Energy'} tolerance`}
                value={options.tolerances[key]}
                slotProps={{ htmlInput: { step: 'any', min: 0 } }}
                onChange={(event) => patchAnalysis({ tolerances: { ...options.tolerances, [key]: numeric(event.target.value, options.tolerances[key]) } })}
              />
            ))}
          </Stack>
        </AccordionDetails>
      </Accordion>

      <Accordion defaultExpanded>
        <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
          <Typography variant="subtitle2">Step size, cutback, and line search</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Stack spacing={1.5}>
            <Stack direction="row" spacing={1}>
              <TextField type="number" label="Initial step size" value={options.step_control.initial_step} slotProps={{ htmlInput: { step: 'any' } }} onChange={(event) => patchAnalysis({ step_control: { ...options.step_control, initial_step: numeric(event.target.value, options.step_control.initial_step) } })} />
              <TextField type="number" label="Minimum step size" value={options.step_control.min_step} slotProps={{ htmlInput: { step: 'any' } }} onChange={(event) => patchAnalysis({ step_control: { ...options.step_control, min_step: numeric(event.target.value, options.step_control.min_step) } })} />
            </Stack>
            <Stack direction="row" spacing={1}>
              <TextField type="number" label="Cutback factor" value={options.step_control.cutback_factor} slotProps={{ htmlInput: { step: 'any' } }} onChange={(event) => patchAnalysis({ step_control: { ...options.step_control, cutback_factor: numeric(event.target.value, options.step_control.cutback_factor) } })} />
              <TextField type="number" label="Maximum retries" value={options.step_control.max_retries} slotProps={{ htmlInput: { step: 1 } }} onChange={(event) => patchAnalysis({ step_control: { ...options.step_control, max_retries: Math.max(0, Math.round(numeric(event.target.value, options.step_control.max_retries))) } })} />
            </Stack>
            <Typography variant="caption" color="text.secondary">Load, displacement, and arc-length control use bounded cutback based on the failure class. Committed state updates only after an accepted step.</Typography>
            <FormControlLabel control={<Switch checked={options.line_search.enabled} disabled={options.control_method === 'arc_length'} onChange={(event) => patchAnalysis({ line_search: { ...options.line_search, enabled: event.target.checked } })} />} label="Enable line search" />
            {options.control_method === 'arc_length' && <Typography variant="caption" color="text.secondary">The P8 arc-length algorithm does not run together with the P7 line search, so this option is disabled.</Typography>}
          </Stack>
        </AccordionDetails>
      </Accordion>
    </Stack>
  )
}
