import { useState } from 'react'
import { Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Checkbox, FormControlLabel, MenuItem, TextField, Typography } from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import { ElementAssignmentPanel } from './ElementAssignmentPanel'
import { NumericForm, type Field } from './NumericForm'
import { applyMaterial, applySection, autoReference, norm, xyz, type Member, type Model3D, type Selection, type Vec3 } from './model'

export type DrawingProperties = Omit<Member, 'id' | 'node_i' | 'node_j'>
type Props = {
  model: Model3D; selection: Selection; defaults: DrawingProperties; templates: DrawingProperties
  onDefaults: (value: DrawingProperties) => void; onTemplates: (value: DrawingProperties) => void
  onChange: (model: Model3D, message?: string) => void; onMessage: (message: string) => void
}

export function PropertyEditor({ kind, ...props }: Props & { kind: 'material' | 'section' }) {
  const { model, selection, defaults, templates, onDefaults, onTemplates, onChange, onMessage } = props
  const member = model.elements.find(e => selection.elements.includes(e.id))
  const source = member ?? templates
  const fields: Field[] = kind === 'material' ? [
    { key: 'E', label: 'E (GPa)', value: source.E / 1e9, positive: true },
    { key: 'G', label: 'G (GPa)', value: source.G / 1e9, positive: true },
  ] : [
    { key: 'A', label: 'A (cm²)', value: source.A * 1e4, positive: true },
    ...(['Iy', 'Iz', 'J'] as const).map(key => ({ key, label: `${key} (cm⁴)`, value: source[key] * 1e8, positive: true })),
    ...(['Asy', 'Asz'] as const).map(key => ({ key, label: `${key} (cm²)`, value: (source[key] ?? source.A * .83) * 1e4, positive: true })),
  ]
  const label = kind === 'material' ? 'Material' : 'Section'
  return <>
    <div className="inspector-note">{member ? `Values from E${member.id}. Edit the definition, then choose the elements below.` : 'Edit the definition, then apply it to existing elements or use it for new elements.'}</div>
    <NumericForm variant="library" fields={fields} action="Use for new elements"
      heading={<div className="library-card-heading"><span>{label.toUpperCase()} DEFINITION</span><strong>{kind === 'material' ? 'Elastic material' : 'Section properties'}</strong></div>}
      assignment={<ElementAssignmentPanel kind={kind} selectedCount={selection.elements.length} rows={model.elements.map(e => ({ id: e.id,
        label: kind === 'material' ? `E ${Number((e.E / 1e9).toPrecision(5))} · G ${Number((e.G / 1e9).toPrecision(5))} GPa` : `A ${Number((e.A * 1e4).toPrecision(5))} cm²`,
        title: `Apply this ${kind} definition to E${e.id}`,
      }))} />}
      onSubmit={(v, target) => {
        const patch = kind === 'material' ? { E: v.E * 1e9, G: v.G * 1e9 } : { A: v.A / 1e4, Iy: v.Iy / 1e8, Iz: v.Iz / 1e8, J: v.J / 1e8, Asy: v.Asy / 1e4, Asz: v.Asz / 1e4 }
        if (Object.values(patch).some(value => !Number.isFinite(value) || value <= 0)) throw new Error('Property values must remain finite and greater than zero after unit conversion.')
        if (target === 'defaults') { onDefaults({ ...defaults, ...patch }); onMessage(`${label} set for new elements`) }
        else {
          const ids = target === 'all' ? model.elements.map(e => e.id) : target === 'selected' ? selection.elements : [Number(target.split(':')[1])]
          const next = kind === 'material' ? applyMaterial(model, ids, { E: v.E * 1e9, G: v.G * 1e9 }) : applySection(model, ids, { A: v.A / 1e4, Iy: v.Iy / 1e8, Iz: v.Iz / 1e8, J: v.J / 1e8, Asy: v.Asy / 1e4, Asz: v.Asz / 1e4 })
          onChange(next, `${label} applied to ${ids.length} element${ids.length === 1 ? '' : 's'}`)
        }
        onTemplates({ ...templates, ...patch })
      }} />
    {kind === 'section' && <MemberOptions key={`${selection.elements.join(',')}-${JSON.stringify([source.theory, source.reference_vector, source.roll_angle, source.releases])}`} {...props} />}
  </>
}

function MemberOptions({ model, selection, defaults, onDefaults, onChange, onMessage }: Props) {
  const member = model.elements.find(e => selection.elements.includes(e.id)); const source = member ?? defaults
  const [theory, setTheory] = useState(source.theory); const [releases, setReleases] = useState(source.releases)
  return <Accordion disableGutters elevation={0}><AccordionSummary expandIcon={<ExpandMoreIcon />}><Typography variant="subtitle2">Element formulation & orientation</Typography></AccordionSummary><AccordionDetails>
    <NumericForm fields={[...source.reference_vector.map((value, i) => ({ key: `ref${i}`, label: `Ref ${'XYZ'[i]}`, value })), { key: 'roll', label: 'Roll (degrees)', value: source.roll_angle }]}
      action={member ? `Apply options to selected (${selection.elements.length})` : 'Use options for new elements'} onSubmit={v => {
        const patch = { theory, reference_vector: [v.ref0, v.ref1, v.ref2] as Vec3, roll_angle: v.roll, releases }
        if (norm(patch.reference_vector) < 1e-12) throw new Error('Reference vector cannot be zero.')
        if (theory === 'timoshenko' && model.distributed_loads.some(l => selection.elements.includes(l.element_id))) throw new Error('Remove line loads from the selected members before using Timoshenko.')
        if (theory === 'timoshenko' && (member ? model.elements.filter(e => selection.elements.includes(e.id)) : [defaults]).some(e => !e.Asy || !e.Asz)) throw new Error('Apply positive Asy and Asz section properties before using Timoshenko.')
        if (member) { const next = structuredClone(model); next.elements = next.elements.map(e => selection.elements.includes(e.id) ? { ...e, ...patch } : e); onChange(next, 'Element options applied') }
        else { onDefaults({ ...defaults, ...patch }); onMessage('Drawing options updated') }
      }}>
      <TextField select label="Beam theory" value={theory} onChange={e => setTheory(e.target.value as Member['theory'])}><MenuItem value="euler_bernoulli">Euler–Bernoulli</MenuItem><MenuItem value="timoshenko">Timoshenko</MenuItem></TextField>
      {theory === 'timoshenko' && <Alert severity="info">Nodal loads only for this formulation.</Alert>}
      <Typography variant="caption" color="text.secondary">Reference vector sets local y before roll. Local x runs from start to end.</Typography>
      <Typography variant="subtitle2">Local end releases</Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>{[3, 4, 5, 9, 10, 11].map(r => <FormControlLabel key={r} control={<Checkbox size="small" checked={releases.includes(r)} onChange={(_, checked) => setReleases(checked ? [...releases, r] : releases.filter(v => v !== r))} />} label={`${r < 6 ? 'Start' : 'End'} R${'xyz'[r % 6 - 3]}`} />)}</Box>
    </NumericForm>
    {member && <Button fullWidth sx={{ mt: 1.5 }} variant="outlined" onClick={() => { const next = structuredClone(model); next.elements = next.elements.map(e => selection.elements.includes(e.id) ? { ...e, reference_vector: autoReference(xyz(next.nodes[e.node_i - 1]), xyz(next.nodes[e.node_j - 1])) } : e); onChange(next, 'Reference vectors aligned automatically') }}>Auto-align reference vectors</Button>}
  </AccordionDetails></Accordion>
}
