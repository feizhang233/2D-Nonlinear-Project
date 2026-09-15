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
import { ScientificField } from './ScientificField'
import { analysisSettingsError } from '../analysisValidation'

interface AnalysisPanelProps {
  model: ModelInput
  runOptions: RunOptions
  onModelChange: (model: ModelInput) => void
  onRunOptionsChange: (options: Partial<RunOptions>) => void
}

export function AnalysisPanel({ model, runOptions, onModelChange, onRunOptionsChange }: AnalysisPanelProps) {
  const options = model.analysis
  const settingsError = analysisSettingsError(model, runOptions)
  const family = MODEL_FAMILIES[model.model_family]
  const dofs = dofsForModel(model)
  const isFree = (nodeId: string, dof: Dof) => !model.constraints.some(constraint => constraint.node_id === nodeId && constraint.dof === dof)
  const controlNodes = model.nodes.filter(node => dofs.some(dof => isFree(node.id, dof)))
  const patchAnalysis = (patch: Partial<ModelInput['analysis']>) => onModelChange({ ...model, analysis: { ...options, ...patch } })
  const setControl = (control: ControlMethod) => {
    const analysis = structuredClone(options)
    analysis.control_method = control
    delete analysis.displacement_control
    delete analysis.arc_length
    if (control === 'displacement') {
      const loaded = model.loads.flatMap((load) => dofs
        .filter((dof) => load.node_id && isFree(load.node_id, dof) && Math.abs(load.components[dof] ?? 0) > 0)
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
        title="Loading strategy"
        subtitle={`${family.label} · ${dofs.join(' / ')}`}
      />
      <ToggleButtonGroup exclusive fullWidth size="small" value={options.control_method} onChange={(_, value: ControlMethod | null) => value && setControl(value)}>
        <ToggleButton value="load">Load</ToggleButton>
        <ToggleButton value="displacement" disabled={!controlNodes.length}>Displacement</ToggleButton>
        <ToggleButton value="arc_length">Arc length</ToggleButton>
      </ToggleButtonGroup>
      {settingsError && <Alert severity="error">{settingsError}</Alert>}

      {options.control_method === 'load' && (
        <ScientificField
          label="Target load factor"
          value={runOptions.targetLoadFactor}
          onValueChange={(value) => onRunOptionsChange({ targetLoadFactor: value })}
          helperText="The adaptive solver advances from the zero state or imported committed state to this load factor."
        />
      )}
      {options.control_method === 'displacement' && options.displacement_control && (
        <Stack spacing={1.5}>
          <Stack direction="row" spacing={1}>
            <TextField select fullWidth label="Control node" value={options.displacement_control.target.node_id} onChange={(event) => patchAnalysis({ displacement_control: { ...options.displacement_control!, target: { ...options.displacement_control!.target, node_id: event.target.value, dof: isFree(event.target.value, options.displacement_control!.target.dof) ? options.displacement_control!.target.dof : dofs.find(dof => isFree(event.target.value, dof))! } } })}>
              {controlNodes.map((node) => <MenuItem value={node.id} key={node.id}>{nodeDisplayLabel(model, node.id)}</MenuItem>)}
            </TextField>
            <TextField select fullWidth label="Degree of freedom" value={options.displacement_control.target.dof} onChange={(event) => patchAnalysis({ displacement_control: { ...options.displacement_control!, target: { ...options.displacement_control!.target, dof: event.target.value as Dof } } })}>
              {dofs.filter(dof => isFree(options.displacement_control!.target.node_id, dof)).map((dof) => <MenuItem value={dof} key={dof}>{dof}</MenuItem>)}
            </TextField>
          </Stack>
          <Stack direction="row" spacing={1}>
            <ScientificField nonZero label="Displacement increment" value={options.displacement_control.increment} onValueChange={(value) => patchAnalysis({ displacement_control: { ...options.displacement_control!, increment: value } })} />
            <ScientificField integer min={1} max={Math.min(10000, options.step_control.max_steps)} label="Steps" value={runOptions.numberOfSteps} onValueChange={(value) => onRunOptionsChange({ numberOfSteps: value })} />
          </Stack>
        </Stack>
      )}
      {options.control_method === 'arc_length' && options.arc_length && (
        <Stack spacing={1.5}>
          <Stack direction="row" spacing={1}>
            <ScientificField exclusiveMin={0} label="Arc-length radius" value={options.arc_length.radius} onValueChange={(value) => patchAnalysis({ arc_length: { ...options.arc_length!, radius: value } })} />
            <ScientificField integer min={1} max={Math.min(10000, options.step_control.max_steps)} label="Steps" value={runOptions.numberOfSteps} onValueChange={(value) => onRunOptionsChange({ numberOfSteps: value })} />
          </Stack>
          <Stack direction="row" spacing={1}>
            <ScientificField exclusiveMin={0} label="Minimum radius" value={options.arc_length.min_radius} onValueChange={(value) => patchAnalysis({ arc_length: { ...options.arc_length!, min_radius: value } })} />
            <ScientificField exclusiveMin={0} label="Maximum radius" value={options.arc_length.max_radius} onValueChange={(value) => patchAnalysis({ arc_length: { ...options.arc_length!, max_radius: value } })} />
          </Stack>
          <ScientificField exclusiveMin={0} label="Load scaling β" value={options.arc_length.beta} onValueChange={(value) => patchAnalysis({ arc_length: { ...options.arc_length!, beta: value } })} />
          <Alert severity="info">Arc-length convergence only shows that the augmented equilibrium equations satisfy the specified tolerances. It does not prove stability, branch uniqueness, or branch switching.</Alert>
        </Stack>
      )}

      <Accordion>
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
              <ScientificField integer min={1} label="Maximum iterations" value={options.max_iterations} onValueChange={(value) => patchAnalysis({ max_iterations: value })} />
            </Stack>
            {([
              ['residual', 'Residual tolerance'],
              ['displacement', 'Displacement correction tolerance'],
              ['energy', 'Energy tolerance'],
              ['linear_solver', 'Linear solver tolerance'],
              ['force_floor', 'Force normalization floor'],
              ['displacement_floor', 'Displacement normalization floor'],
              ['energy_floor', 'Energy normalization floor'],
            ] as const).map(([key, label]) => (
              <ScientificField
                key={key}
                exclusiveMin={0}
                label={label}
                value={options.tolerances[key]}
                onValueChange={(value) => patchAnalysis({ tolerances: { ...options.tolerances, [key]: value } })}
              />
            ))}
          </Stack>
        </AccordionDetails>
      </Accordion>

      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
          <Typography variant="subtitle2">Step size, cutback, and line search</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Stack spacing={1.5}>
            {options.control_method !== 'arc_length' && <>
            <Stack direction="row" spacing={1}>
              <ScientificField exclusiveMin={0} label={options.control_method === 'displacement' ? 'Initial step scale' : 'Initial load step'} value={options.step_control.initial_step} onValueChange={(value) => patchAnalysis({ step_control: { ...options.step_control, initial_step: value } })} />
              <ScientificField exclusiveMin={0} label={options.control_method === 'displacement' ? 'Minimum step scale' : 'Minimum load step'} value={options.step_control.min_step} onValueChange={(value) => patchAnalysis({ step_control: { ...options.step_control, min_step: value } })} />
            </Stack>
            <ScientificField exclusiveMin={0} label={options.control_method === 'displacement' ? 'Maximum step scale' : 'Maximum load step'} value={options.step_control.max_step} onValueChange={(value) => patchAnalysis({ step_control: { ...options.step_control, max_step: value } })} />
            {options.control_method === 'displacement' && <Typography variant="caption" color="text.secondary">The initial increment comes from Displacement increment. Minimum and maximum increments use the step scale divided by Initial step scale.</Typography>}
            </>}
            <ScientificField integer min={1} label="Maximum accepted steps" value={options.step_control.max_steps} onValueChange={(value) => patchAnalysis({ step_control: { ...options.step_control, max_steps: value } })} />
            <Stack direction="row" spacing={1}>
              <ScientificField exclusiveMin={0} exclusiveMax={1} label="Cutback factor" value={options.step_control.cutback_factor} onValueChange={(value) => patchAnalysis({ step_control: { ...options.step_control, cutback_factor: value } })} />
              <ScientificField integer min={0} label="Maximum retries" value={options.step_control.max_retries} onValueChange={(value) => patchAnalysis({ step_control: { ...options.step_control, max_retries: value } })} />
            </Stack>
            <Stack direction="row" spacing={1}>
              <ScientificField min={1} label="Growth factor" value={options.step_control.growth_factor} onValueChange={(value) => patchAnalysis({ step_control: { ...options.step_control, growth_factor: value } })} />
              <ScientificField integer min={1} label="Target iterations" value={options.step_control.target_iterations} onValueChange={(value) => patchAnalysis({ step_control: { ...options.step_control, target_iterations: value } })} />
            </Stack>
            <Typography variant="caption" color="text.secondary">Load, displacement, and arc-length control use bounded cutback based on the failure class. Committed state updates only after an accepted step.</Typography>
            <FormControlLabel control={<Switch checked={options.line_search.enabled} disabled={options.control_method === 'arc_length'} onChange={(event) => patchAnalysis({ line_search: { ...options.line_search, enabled: event.target.checked } })} />} label="Enable line search" />
            {options.line_search.enabled && options.control_method !== 'arc_length' && <>
              <TextField select fullWidth label="Line search method" value={options.line_search.method} onChange={(event) => patchAnalysis({ line_search: { ...options.line_search, method: event.target.value as 'backtracking' | 'orthogonality' } })}>
                <MenuItem value="backtracking">Backtracking</MenuItem>
                <MenuItem value="orthogonality" disabled>Orthogonality (unavailable for structural models)</MenuItem>
              </TextField>
              <ScientificField integer min={1} label="Line search iterations" value={options.line_search.max_iterations} onValueChange={(value) => patchAnalysis({ line_search: { ...options.line_search, max_iterations: value } })} />
              <ScientificField exclusiveMin={0} exclusiveMax={1} label="Minimum line search factor" value={options.line_search.min_alpha} onValueChange={(value) => patchAnalysis({ line_search: { ...options.line_search, min_alpha: value } })} />
              <ScientificField exclusiveMin={0} exclusiveMax={1} label="Line search reduction factor" value={options.line_search.reduction_factor} onValueChange={(value) => patchAnalysis({ line_search: { ...options.line_search, reduction_factor: value } })} />
            </>}
            {options.control_method === 'arc_length' && <Typography variant="caption" color="text.secondary">Line search is unavailable with arc-length control.</Typography>}
          </Stack>
        </AccordionDetails>
      </Accordion>
    </Stack>
  )
}
