import { HoleProperties } from './HoleFields'
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded'
import { Accordion, AccordionSummary, AccordionDetails } from '@mui/material'
import { ScientificField } from './ScientificField'
import { SectionPanel } from './SectionPanel'
import { SplitElementPanel } from './SplitElementPanel'
import { assignSection, sectionIdForElement, sectionLibrary } from '../sections'
import { deleteSelection } from '../modelOperations'
import CategoryRoundedIcon from '@mui/icons-material/CategoryRounded'
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded'
import GridOnRoundedIcon from '@mui/icons-material/GridOnRounded'
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined'
import Alert from '@mui/material/Alert'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import FormControlLabel from '@mui/material/FormControlLabel'
import InputAdornment from '@mui/material/InputAdornment'
import MenuItem from '@mui/material/MenuItem'
import Stack from '@mui/material/Stack'
import Switch from '@mui/material/Switch'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import type {
  Dof,
  EntityKind,
  JsonValue,
  LoadInput,
  ModelInput,
  Selection,
} from '../domain'
import {
  elementDisplayLabel,
  loadDisplayLabel,
  materialDisplayLabel,
  modelDisplayLabel,
  nodeDisplayLabel,
  supportDisplayLabel,
  withEntityDisplayName,
} from '../entityLabels'
import {
  deleteSketchVertex,
  editablePlacementNodes,
  firstFreePlacementNodeId,
  geometryNeedsMesh,
  getSketch,
  isSurfaceFamily,
  moveSketchVertex,
  PlacementState,
} from '../geometrySketch'
import {
  meshBoundaries,
  meshSizeForModel,
  meshStatusForModel,
  withMeshSize,
} from '../meshing'
import { dofsForModel, MODEL_FAMILIES } from '../modelFamilies'
import {
  addSupportAtNode,
  classifySupport,
  constraintsForClass,
  groupedSupports,
  moveSupportToNode,
  SUPPORT_CLASS_LABEL,
  SUPPORT_CLASS_ORDER,
  supportNodeId,
  toggleConstraintDof,
  type SupportClass,
} from '../supports'
import { SectionHeader } from './chrome'

interface PropertyPanelProps {
  model: ModelInput
  selection: Selection
  onChange: (model: ModelInput, selection?: Selection) => void
  onDelete?: (selection: Selection) => void
  onGenerateMesh?: () => void
  meshing?: boolean
  meshDisabled?: boolean
  placement?: PlacementState
  onStartPlacement?: (placement: NonNullable<PlacementState>) => void
  onCancelPlacement?: () => void
}

const numberValue = (value: string) =>
  Number.isFinite(Number(value)) ? Number(value) : 0
const propertyLabels: Record<string, string> = {
  young: 'Young’s modulus E',
  poisson: 'Poisson’s ratio ν',
  plane_mode: 'Plane mode',
  area: 'Area A',
  second_moment: 'Second moment I',
  thickness: 'Thickness t',
  plate_method: 'Plate method',
  shear_scheme: 'Shear scheme',
  shear_correction: 'Shear correction factor',
  shear_correction_factor: 'Shear correction factor',
  alpha_d: 'Drilling stabilization αd',
  differentiation_step: 'Numerical differentiation step',
}

const unitForKey = (key: string, model: ModelInput): string | undefined => {
  if (key === 'young') return model.units.stress
  if (key === 'thickness') return model.units.length
  if (key === 'area') return `${model.units.length}²`
  if (key === 'second_moment') return `${model.units.length}⁴`
  return undefined
}

export function PropertyPanel({
  model,
  selection,
  onChange,
  onDelete,
  onGenerateMesh,
  meshing = false,
  meshDisabled = false,
  placement = null,
  onStartPlacement,
  onCancelPlacement,
}: PropertyPanelProps) {
  const family = MODEL_FAMILIES[model.model_family]
  const meshStatus = meshStatusForModel(model)
  const meshSize = meshSizeForModel(model)
  const meshSizeInvalid = !Number.isFinite(meshSize) || meshSize <= 0
  const topologyReadOnly = isSurfaceFamily(model)
  const dofs = dofsForModel(model)
  const placementNodes = editablePlacementNodes(model)
  const locationOptions = (currentId?: string) => {
    if (currentId && !placementNodes.some((node) => node.id === currentId)) {
      return [
        {
          id: currentId,
          label: nodeDisplayLabel(model, currentId),
          coordinates: [],
        },
        ...placementNodes,
      ]
    }
    return placementNodes
  }
  const changeModel = (patch: Partial<ModelInput>) =>
    onChange({ ...model, ...patch })
  const updateEntity = (
    kind: Exclude<EntityKind, 'model'>,
    id: string,
    mutate: (entity: Record<string, unknown>) => void,
  ) => {
    const next = structuredClone(model)
    const entity = (
      next[kind] as unknown as Array<Record<string, unknown>>
    ).find((item) => item.id === id)
    if (!entity) return
    mutate(entity)
    onChange(next)
  }
  const removeEntity = (kind: Exclude<EntityKind, 'model'>, id: string) => {
    if (onDelete) onDelete({ kind, id })
    else onChange(deleteSelection(model, { kind, id }), { kind })
  }

  if (selection.kind === 'sections')
    return (
      <SectionPanel model={model} selection={selection} onChange={onChange} />
    )

  if (selection.kind === 'mesh') {
    return (
      <Stack spacing={2}>
        <SectionHeader
          icon={<GridOnRoundedIcon fontSize="small" />}
          title="Mesh"
          subtitle={
            model.model_family === 'frame'
              ? `${family.label} · explicit line-element topology`
              : `${family.label} · all-Q4 Gmsh surface mesh`
          }
        />
        {model.model_family === 'frame' ? (
          <Alert severity="info">
            The current Frame model contains {meshStatus.nodeCount} nodes and{' '}
            {meshStatus.elementCount} explicit line elements. Gmsh surface
            meshing is available for Continuum, Plate, and Shell.
          </Alert>
        ) : (
          <>
            <Alert severity={meshStatus.generatedByGmsh ? 'success' : 'info'}>
              {meshStatus.generatedByGmsh
                ? `The canvas mesh was generated by ${meshStatus.sourceLabel}: ${meshStatus.nodeCount} nodes / ${meshStatus.elementCount} Q4 elements.`
                : `The canvas shows the model topology: ${meshStatus.nodeCount} nodes / ${meshStatus.elementCount} Q4 elements. Gmsh remeshing has not been run.`}
            </Alert>
            <TextField
              type="number"
              label="Target element size"
              value={meshSize}
              error={meshSizeInvalid}
              slotProps={{
                htmlInput: { step: 'any' },
                input: {
                  endAdornment: (
                    <InputAdornment position="end">
                      {model.units.length}
                    </InputAdornment>
                  ),
                },
              }}
              onChange={(event) =>
                onChange(withMeshSize(model, numberValue(event.target.value)))
              }
              helperText={
                meshSizeInvalid
                  ? 'Target element size must be greater than 0.'
                  : 'The API only requires a value greater than 0. This model value is not a fixed lower limit.'
              }
            />
            {geometryNeedsMesh(model) && (
              <Alert severity="warning">
                Geometry changed. Generate a new mesh before solving.
              </Alert>
            )}
            <Alert severity="info">
              Outer contours and holes come from the Geometry panel. Shell
              geometry must be planar and parallel to XY. The interactive
              service limit is 10,000 nodes; the backend rejects excessively
              small sizes.
            </Alert>
            <Button
              variant="contained"
              startIcon={
                meshing ? (
                  <CircularProgress size={18} color="inherit" />
                ) : (
                  <GridOnRoundedIcon />
                )
              }
              disabled={
                meshing || meshDisabled || !onGenerateMesh || meshSizeInvalid
              }
              onClick={onGenerateMesh}
            >
              {meshing ? 'Generating mesh…' : 'Generate mesh with Gmsh'}
            </Button>
            <Typography variant="caption" color="text.secondary">
              Workflow: extract the exterior boundary → generate an all-Q4 Gmsh
              mesh → replace nodes and elements → rebind supports, concentrated
              loads, and boundary distributed loads.
            </Typography>
          </>
        )}
      </Stack>
    )
  }

  if (selection.kind === 'model') {
    return (
      <Stack spacing={2}>
        <SectionHeader
          title={modelDisplayLabel()}
          subtitle={`${family.label} · name and unit metadata`}
        />
        <TextField
          label="Display name"
          value={model.name}
          onChange={(event) => changeModel({ name: event.target.value })}
        />
        <Stack direction="row" spacing={1}>
          <TextField
            label="Length"
            value={model.units.length}
            onChange={(event) =>
              changeModel({
                units: { ...model.units, length: event.target.value },
              })
            }
          />
          <TextField
            label="Force"
            value={model.units.force}
            onChange={(event) =>
              changeModel({
                units: { ...model.units, force: event.target.value },
              })
            }
          />
        </Stack>
        <Stack direction="row" spacing={1}>
          <TextField
            label="Stress"
            value={model.units.stress}
            onChange={(event) =>
              changeModel({
                units: { ...model.units, stress: event.target.value },
              })
            }
          />
          <TextField
            label="Angle"
            value={model.units.angle}
            onChange={(event) =>
              changeModel({
                units: { ...model.units, angle: event.target.value },
              })
            }
          />
        </Stack>
        <Alert severity="info" icon={<InfoOutlinedIcon fontSize="small" />}>
          {family.capability} The current adapters require m / N / Pa / rad; the
          interface does not convert units automatically.
        </Alert>
      </Stack>
    )
  }

  if (selection.kind === 'geometry') {
    const sketch = getSketch(model)
    const hole = sketch.loops.find(
      (loop) => loop.id === selection.id && loop.shape,
    )
    if (hole?.shape)
      return (
        <HoleProperties
          key={`${model.model_id}-${hole.id}-${JSON.stringify(hole.shape)}`}
          model={model}
          id={hole.id}
          shape={hole.shape}
          onChange={onChange}
        />
      )
    const vertex = selection.id
      ? sketch.vertices.find((item) => item.id === selection.id)
      : undefined
    if (!vertex) {
      return (
        <Stack spacing={2}>
          <SectionHeader
            title="Geometry"
            subtitle="Select a contour vertex to edit coordinates"
          />
        </Stack>
      )
    }
    const outer = sketch.loops.find((loop) => loop.kind === 'outer')
    const index = sketch.vertices.findIndex((item) => item.id === vertex.id) + 1
    return (
      <Stack spacing={2}>
        <SectionHeader
          title={`Vertex ${index}`}
          subtitle="Geometry vertex used for the CAD contour, not a mesh node"
        />
        <Stack direction="row" spacing={1}>
          {['X', 'Y'].map((label, axis) => (
            <TextField
              key={label}
              type="number"
              label={label}
              value={vertex.coordinates[axis] ?? 0}
              slotProps={{
                htmlInput: { step: 'any' },
                input: {
                  endAdornment: (
                    <InputAdornment position="end">
                      {model.units.length}
                    </InputAdornment>
                  ),
                },
              }}
              onChange={(event) => {
                const next = [...vertex.coordinates]
                next[axis] = numberValue(event.target.value)
                onChange(moveSketchVertex(model, vertex.id, next), {
                  kind: 'geometry',
                  id: vertex.id,
                })
              }}
            />
          ))}
        </Stack>
        <Button
          color="error"
          variant="outlined"
          startIcon={<DeleteOutlineRoundedIcon />}
          disabled={(outer?.vertexIds.length ?? 0) <= 3}
          onClick={() =>
            onChange(deleteSketchVertex(model, vertex.id), { kind: 'model' })
          }
        >
          Delete vertex
        </Button>
      </Stack>
    )
  }

  if (!selection.id) {
    if (selection.kind === 'constraints') {
      const grouped = groupedSupports(model, dofs)
      const defaultNode =
        firstFreePlacementNodeId(model) ?? placementNodes[0]?.id
      return (
        <Stack spacing={2}>
          <SectionHeader
            title="Supports"
            subtitle="Add a support, then click the CAD contour or choose a vertex"
          />
          <Alert severity={placement?.kind === 'support' ? 'warning' : 'info'}>
            {placement?.kind === 'support'
              ? 'Click a geometry vertex or frame node on the canvas to place the new support.'
              : `${grouped.nodeCount} supports currently define ${grouped.recordCount} DOF constraints. ${grouped.groups.map((group) => `${group.label} ${group.items.length}`).join(' · ') || 'No supports yet'}.`}
          </Alert>
          <Button
            variant="contained"
            disabled={!defaultNode || Boolean(placement)}
            onClick={() => onStartPlacement?.({ kind: 'support' })}
          >
            {placement?.kind === 'support'
              ? 'Waiting for canvas click…'
              : 'Add support'}
          </Button>
          {placement?.kind === 'support' && (
            <Button onClick={onCancelPlacement}>Cancel placement</Button>
          )}
          {defaultNode && (
            <Button
              variant="outlined"
              onClick={() =>
                onChange(addSupportAtNode(model, defaultNode, dofs), {
                  kind: 'constraints',
                  id: defaultNode,
                })
              }
            >
              Add at{' '}
              {placementNodes.find((node) => node.id === defaultNode)?.label ??
                defaultNode}
            </Button>
          )}
        </Stack>
      )
    }
    if (selection.kind === 'loads') {
      const defaultNode = placementNodes[0]?.id ?? model.nodes[0]?.id
      return (
        <Stack spacing={2}>
          <SectionHeader
            title="Loads"
            subtitle="Click a node for a point load or an element for a line load"
          />
          <Alert severity={placement?.kind === 'load' ? 'warning' : 'info'}>
            {placement?.kind === 'load'
              ? 'Click the intended node or element. No load is created until you choose its location.'
              : `This group contains ${model.loads.length} loads. New loads keep their own numbers and are not renamed when earlier loads are deleted.`}
          </Alert>
          <Button
            variant="contained"
            disabled={!defaultNode || Boolean(placement)}
            onClick={() => onStartPlacement?.({ kind: 'load' })}
          >
            {placement?.kind === 'load'
              ? 'Waiting for canvas click…'
              : 'Add load'}
          </Button>
          {placement?.kind === 'load' && (
            <Button onClick={onCancelPlacement}>Cancel placement</Button>
          )}
        </Stack>
      )
    }
    const count = model[selection.kind].length
    return (
      <Stack spacing={2}>
        <SectionHeader
          title="Entity properties"
          subtitle="Select an item in the model list to edit it"
        />
        <Alert severity="info">
          This group contains {count} items. Use the group + action to add one,
          or open a numbered item from the list.
        </Alert>
      </Stack>
    )
  }

  const { kind, id } = selection
  if (kind === 'nodes') {
    const node = model.nodes.find((item) => item.id === id)
    if (!node) return null
    const referenced =
      model.elements.some((item) => item.node_ids.includes(id)) ||
      model.loads.some((item) => item.node_id === id) ||
      model.constraints.some((item) => item.node_id === id)
    return (
      <Stack spacing={2}>
        <SectionHeader
          title={nodeDisplayLabel(model, id)}
          subtitle={
            topologyReadOnly
              ? 'Read-only finite-element mesh node'
              : `${model.model_family === 'shell' ? '3D reference coordinates' : '2D reference coordinates'}; units come from model metadata`
          }
        />
        {topologyReadOnly && (
          <Alert severity="info">
            Mesh nodes are visible for inspection but cannot be edited directly.
            Edit the Geometry contour and generate a new mesh.
          </Alert>
        )}
        <TextField
          label="Display name"
          value={nodeDisplayLabel(model, id)}
          disabled={topologyReadOnly}
          slotProps={{ htmlInput: { maxLength: 80 } }}
          onChange={(event) =>
            onChange(
              withEntityDisplayName(model, kind, id, event.target.value),
              { kind, id },
            )
          }
        />
        <Stack direction="row" spacing={1}>
          {(model.model_family === 'shell' ? ['X', 'Y', 'Z'] : ['X', 'Y']).map(
            (label, index) => (
              <TextField
                fullWidth
                key={label}
                type="number"
                label={label}
                value={node.coordinates[index] ?? 0}
                disabled={topologyReadOnly}
                slotProps={{
                  htmlInput: { step: 'any' },
                  input: {
                    endAdornment: (
                      <InputAdornment position="end">
                        {model.units.length}
                      </InputAdornment>
                    ),
                  },
                }}
                onChange={(event) =>
                  updateEntity(kind, id, (entity) => {
                    ;(entity.coordinates as number[])[index] = numberValue(
                      event.target.value,
                    )
                  })
                }
              />
            ),
          )}
        </Stack>
        {!topologyReadOnly && <Divider />}
        {!topologyReadOnly && (
          <Button
            color="error"
            variant="outlined"
            startIcon={<DeleteOutlineRoundedIcon />}
            disabled={referenced}
            onClick={() => removeEntity(kind, id)}
          >
            Delete node
          </Button>
        )}
        {!topologyReadOnly && referenced && (
          <Typography variant="caption" color="text.secondary">
            This node is referenced by an element, support, or load. Remove
            those references first.
          </Typography>
        )}
      </Stack>
    )
  }

  if (kind === 'elements') {
    const element = model.elements.find((item) => item.id === id)
    if (!element) return null
    return (
      <Stack spacing={2}>
        <SectionHeader
          title={elementDisplayLabel(model, id)}
          subtitle={
            topologyReadOnly
              ? `Read-only ${family.formulation} mesh element`
              : family.capability
          }
        />
        {topologyReadOnly && (
          <Alert severity="info">
            Mesh elements are visible for connectivity and formulation
            inspection. Their topology is controlled by Geometry and Gmsh.
          </Alert>
        )}
        <TextField
          label="Display name"
          value={elementDisplayLabel(model, id)}
          disabled={topologyReadOnly}
          slotProps={{ htmlInput: { maxLength: 80 } }}
          onChange={(event) =>
            onChange(
              withEntityDisplayName(model, kind, id, event.target.value),
              { kind, id },
            )
          }
        />
        <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }} useFlexGap>
          {Array.from({ length: family.elementNodeCount }, (_, index) => (
            <TextField
              select
              key={index}
              label={
                family.elementNodeCount === 2
                  ? index === 0
                    ? 'i node'
                    : 'j node'
                  : `Node ${index + 1}`
              }
              value={element.node_ids[index] ?? ''}
              disabled={topologyReadOnly}
              sx={{ minWidth: 110, flex: '1 1 42%' }}
              onChange={(event) =>
                updateEntity(kind, id, (entity) => {
                  ;(entity.node_ids as string[])[index] = event.target.value
                })
              }
            >
              {model.nodes.map((node) => (
                <MenuItem key={node.id} value={node.id}>
                  {nodeDisplayLabel(model, node.id)}
                </MenuItem>
              ))}
            </TextField>
          ))}
        </Stack>
        <TextField
          select
          disabled={topologyReadOnly}
          label="Material"
          value={element.material_id}
          onChange={(event) =>
            updateEntity(kind, id, (entity) => {
              entity.material_id = event.target.value
            })
          }
        >
          {model.materials.map((material) => (
            <MenuItem key={material.id} value={material.id}>
              {materialDisplayLabel(model, material.id)}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          label="Section"
          value={sectionIdForElement(model, element) ?? ''}
          onChange={(event) =>
            onChange(assignSection(model, event.target.value, [id]))
          }
        >
          <MenuItem value="" disabled>
            Choose a section
          </MenuItem>
          {sectionLibrary(model).definitions.map((section) => (
            <MenuItem key={section.id} value={section.id}>
              {section.name}
            </MenuItem>
          ))}
        </TextField>
        <Button
          size="small"
          sx={{ alignSelf: 'flex-start', px: 0 }}
          onClick={() =>
            onChange(model, {
              kind: 'sections',
              id: sectionIdForElement(model, element),
            })
          }
        >
          Edit section definition →
        </Button>
        <Accordion>
          <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
            <Typography component="span" variant="subtitle2">
              Element details
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Stack spacing={2}>
              {Object.entries(element.properties).map(([key, value]) => (
                <TextField
                  key={key}
                  type={typeof value === 'number' ? 'number' : 'text'}
                  label={propertyLabels[key] ?? key}
                  value={
                    typeof value === 'object'
                      ? JSON.stringify(value)
                      : String(value)
                  }
                  disabled={
                    topologyReadOnly ||
                    typeof value === 'object' ||
                    ['area', 'second_moment', 'thickness'].includes(key)
                  }
                  slotProps={{
                    htmlInput:
                      typeof value === 'number' ? { step: 'any' } : undefined,
                    input: unitForKey(key, model)
                      ? {
                          endAdornment: (
                            <InputAdornment position="end">
                              {unitForKey(key, model)}
                            </InputAdornment>
                          ),
                        }
                      : undefined,
                  }}
                  onChange={(event) =>
                    updateEntity(kind, id, (entity) => {
                      ;(entity.properties as Record<string, JsonValue>)[key] =
                        typeof value === 'number'
                          ? numberValue(event.target.value)
                          : event.target.value
                    })
                  }
                />
              ))}
              <TextField
                label="Formulation"
                value={element.formulation}
                disabled
              />
            </Stack>
          </AccordionDetails>
        </Accordion>
        {!topologyReadOnly && (
          <>
            <Divider />
            <SplitElementPanel
              key={id}
              model={model}
              elementId={id}
              onChange={onChange}
            />
            <Button
              color="error"
              variant="outlined"
              startIcon={<DeleteOutlineRoundedIcon />}
              onClick={() => removeEntity(kind, id)}
            >
              Delete element
            </Button>
          </>
        )}
      </Stack>
    )
  }

  if (kind === 'materials') {
    const material = model.materials.find((item) => item.id === id)
    if (!material) return null
    const used = model.elements.some((item) => item.material_id === id)
    return (
      <Stack spacing={2}>
        <SectionHeader
          icon={<CategoryRoundedIcon fontSize="small" />}
          title={materialDisplayLabel(model, id)}
          subtitle={`${family.shortLabel} verified constitutive parameters`}
        />
        <TextField
          label="Display name"
          value={materialDisplayLabel(model, id)}
          slotProps={{ htmlInput: { maxLength: 80 } }}
          onChange={(event) =>
            onChange(
              withEntityDisplayName(model, kind, id, event.target.value),
              { kind, id },
            )
          }
        />
        <TextField label="Constitutive model" value={material.model} disabled />
        {Object.entries(material.parameters).map(([key, value]) => (
          <TextField
            key={key}
            type={typeof value === 'number' ? 'number' : 'text'}
            label={propertyLabels[key] ?? key}
            value={
              typeof value === 'object' ? JSON.stringify(value) : String(value)
            }
            disabled={typeof value === 'object'}
            slotProps={{
              htmlInput:
                typeof value === 'number' ? { step: 'any' } : undefined,
              input: unitForKey(key, model)
                ? {
                    endAdornment: (
                      <InputAdornment position="end">
                        {unitForKey(key, model)}
                      </InputAdornment>
                    ),
                  }
                : undefined,
            }}
            onChange={(event) =>
              updateEntity(kind, id, (entity) => {
                ;(entity.parameters as Record<string, JsonValue>)[key] =
                  typeof value === 'number'
                    ? numberValue(event.target.value)
                    : event.target.value
              })
            }
          />
        ))}
        <Button
          color="error"
          variant="outlined"
          startIcon={<DeleteOutlineRoundedIcon />}
          disabled={used}
          onClick={() => removeEntity(kind, id)}
        >
          Delete material
        </Button>
        {used && (
          <Typography variant="caption" color="text.secondary">
            This material is used by an element.
          </Typography>
        )}
      </Stack>
    )
  }

  if (kind === 'constraints') {
    const nodeId = supportNodeId(model, id)
    if (!nodeId) return null
    const records = model.constraints.filter((item) => item.node_id === nodeId)
    const supportClass = classifySupport(dofs, records)
    const transDofs = dofs.filter((dof) => dof.startsWith('U'))
    const rollerDof =
      records.find((item) => item.dof.startsWith('U'))?.dof ??
      transDofs[0] ??
      dofs[0]
    const applyClass = (nextClass: SupportClass, nextRoller = rollerDof) => {
      onChange(
        {
          ...model,
          constraints: constraintsForClass(
            nodeId,
            nextClass,
            dofs,
            model.constraints,
            nextRoller,
          ),
        },
        { kind: 'constraints', id: nodeId },
      )
    }
    const moveToNode = (nextNodeId: string) => {
      if (nextNodeId === nodeId) return
      onChange(moveSupportToNode(model, nodeId, nextNodeId), {
        kind: 'constraints',
        id: nextNodeId,
      })
    }
    return (
      <Stack spacing={2}>
        <SectionHeader
          title={`${supportDisplayLabel(model, nodeId)} · ${SUPPORT_CLASS_LABEL[supportClass]}`}
          subtitle="DOF constraints at the same node are edited as one support"
          action={
            <Button
              color="error"
              variant="outlined"
              size="small"
              startIcon={<DeleteOutlineRoundedIcon />}
              onClick={() => removeEntity('constraints', nodeId)}
            >
              Delete
            </Button>
          }
        />
        <TextField
          label="Display name"
          value={supportDisplayLabel(model, nodeId)}
          slotProps={{ htmlInput: { maxLength: 80 } }}
          onChange={(event) =>
            onChange(
              withEntityDisplayName(
                model,
                'constraints',
                nodeId,
                event.target.value,
              ),
              { kind: 'constraints', id: nodeId },
            )
          }
        />
        <TextField
          select
          label="Location"
          value={nodeId}
          onChange={(event) => moveToNode(event.target.value)}
        >
          {locationOptions(nodeId).map((node) => (
            <MenuItem key={node.id} value={node.id}>
              {node.label}
            </MenuItem>
          ))}
        </TextField>
        <Button
          variant={
            placement?.kind === 'support' && placement.targetId === nodeId
              ? 'contained'
              : 'outlined'
          }
          onClick={() =>
            placement?.kind === 'support' && placement.targetId === nodeId
              ? onCancelPlacement?.()
              : onStartPlacement?.({ kind: 'support', targetId: nodeId })
          }
        >
          {placement?.kind === 'support' && placement.targetId === nodeId
            ? 'Click a vertex on the canvas…'
            : 'Pick location on canvas'}
        </Button>
        <TextField
          select
          label="Support type"
          value={supportClass}
          onChange={(event) => applyClass(event.target.value as SupportClass)}
        >
          {SUPPORT_CLASS_ORDER.map((item) => (
            <MenuItem key={item} value={item}>
              {SUPPORT_CLASS_LABEL[item]}
            </MenuItem>
          ))}
        </TextField>
        {supportClass === 'roller' && transDofs.length > 0 && (
          <TextField
            select
            label="Roller constraint direction"
            value={rollerDof}
            onChange={(event) =>
              applyClass('roller', event.target.value as Dof)
            }
          >
            {transDofs.map((dof) => (
              <MenuItem key={dof} value={dof}>
                {dof}
              </MenuItem>
            ))}
          </TextField>
        )}
        {dofs.map((dof) => {
          const record = records.find((item) => item.dof === dof)
          return (
            <Stack
              key={dof}
              direction="row"
              spacing={1}
              sx={{ alignItems: 'center' }}
            >
              <FormControlLabel
                sx={{ minWidth: 88 }}
                control={
                  <Switch
                    checked={Boolean(record)}
                    onChange={(event) =>
                      onChange(
                        {
                          ...model,
                          constraints: toggleConstraintDof(
                            nodeId,
                            dof,
                            event.target.checked,
                            model.constraints,
                          ),
                        },
                        { kind: 'constraints', id: nodeId },
                      )
                    }
                  />
                }
                label={dof}
              />
              {record && (
                <TextField
                  fullWidth
                  type="number"
                  label="Prescribed value"
                  value={record.value ?? 0}
                  slotProps={{ htmlInput: { step: 'any' } }}
                  onChange={(event) =>
                    updateEntity('constraints', record.id, (entity) => {
                      entity.value = numberValue(event.target.value)
                    })
                  }
                />
              )}
            </Stack>
          )
        })}
        <Button
          color="error"
          variant="outlined"
          startIcon={<DeleteOutlineRoundedIcon />}
          onClick={() => removeEntity('constraints', nodeId)}
        >
          Delete support
        </Button>
      </Stack>
    )
  }

  const load = model.loads.find((item) => item.id === id)
  if (kind !== 'loads' || !load) return null
  const boundaries = meshBoundaries(model)
  const loadKindOptions: Array<{ kind: LoadInput['kind']; label: string }> =
    model.model_family === 'frame'
      ? [
          { kind: 'nodal', label: 'Nodal concentrated load' },
          { kind: 'element', label: 'Member distributed load' },
        ]
      : model.model_family === 'continuum'
        ? [
            { kind: 'nodal', label: 'Nodal concentrated load' },
            { kind: 'edge', label: 'Boundary distributed load' },
          ]
        : [
            { kind: 'nodal', label: 'Nodal concentrated load' },
            { kind: 'surface', label: 'Surface distributed load' },
            { kind: 'edge', label: 'Boundary distributed load' },
          ]
  const loadLabel =
    loadKindOptions.find((option) => option.kind === load.kind)?.label ??
    load.kind
  const distributedDofs: Dof[] =
    model.model_family === 'continuum'
      ? ['UX', 'UY']
      : model.model_family === 'plate'
        ? ['UZ']
        : ['UX', 'UY', 'UZ']
  const changeLoadKind = (nextKind: LoadInput['kind']) =>
    onStartPlacement?.({
      kind: 'load',
      targetId: id,
      loadKind:
        nextKind === 'nodal'
          ? 'nodal'
          : nextKind === 'surface'
            ? 'surface'
            : 'line',
    })

  const selectBoundary = (boundaryId: string) => {
    const boundary = boundaries.find((candidate) => candidate.id === boundaryId)
    if (!boundary?.segments.length) return
    updateEntity('loads', id, (entity) => {
      entity.element_id = boundary.segments[0].element_id
      entity.extensions = {
        boundary_id: boundary.id,
        edge_node_ids: boundary.node_ids,
        edge_segments: boundary.segments,
        local_edge: boundary.segments[0].local_edge,
      }
    })
  }
  return (
    <Stack spacing={2}>
      <SectionHeader
        title={loadDisplayLabel(model, id)}
        subtitle={`${family.shortLabel} · ${loadLabel} · ${load.coordinate_system === 'local' ? 'reference local coordinates' : 'fixed global direction'}`}
        action={
          <Button
            color="error"
            variant="outlined"
            size="small"
            startIcon={<DeleteOutlineRoundedIcon />}
            onClick={() => removeEntity('loads', id)}
          >
            Delete
          </Button>
        }
      />
      <TextField
        label="Display name"
        value={loadDisplayLabel(model, id)}
        slotProps={{ htmlInput: { maxLength: 80 } }}
        onChange={(event) =>
          onChange(
            withEntityDisplayName(model, 'loads', id, event.target.value),
            { kind: 'loads', id },
          )
        }
      />
      <TextField
        select
        label="Load type"
        value={load.kind}
        onChange={(event) =>
          changeLoadKind(event.target.value as LoadInput['kind'])
        }
      >
        {loadKindOptions.map((option) => (
          <MenuItem key={option.kind} value={option.kind}>
            {option.label}
          </MenuItem>
        ))}
      </TextField>
      {load.kind === 'nodal' && (
        <>
          <TextField
            select
            label="Location"
            value={load.node_id ?? ''}
            onChange={(event) =>
              updateEntity('loads', id, (entity) => {
                entity.node_id = event.target.value
              })
            }
          >
            {locationOptions(load.node_id ?? undefined).map((node) => (
              <MenuItem key={node.id} value={node.id}>
                {node.label}
              </MenuItem>
            ))}
          </TextField>
          <Button
            variant={
              placement?.kind === 'load' && placement.targetId === id
                ? 'contained'
                : 'outlined'
            }
            onClick={() =>
              placement?.kind === 'load' && placement.targetId === id
                ? onCancelPlacement?.()
                : onStartPlacement?.({
                    kind: 'load',
                    targetId: id,
                    loadKind: 'nodal',
                  })
            }
          >
            {placement?.kind === 'load' && placement.targetId === id
              ? 'Click a vertex on the canvas…'
              : 'Pick location on canvas'}
          </Button>
          {dofs.map((dof) => (
            <ScientificField
              key={dof}
              label={`${dof} component`}
              value={load.components[dof] ?? 0}
              unit={
                dof.startsWith('R')
                  ? `${model.units.force}·${model.units.length}`
                  : model.units.force
              }
              onValueChange={(value) =>
                updateEntity('loads', id, (entity) => {
                  ;(entity.components as Record<string, number>)[dof] = value
                })
              }
            />
          ))}
        </>
      )}
      {load.kind !== 'nodal' && (
        <Button
          variant="outlined"
          onClick={() =>
            onStartPlacement?.({
              kind: 'load',
              targetId: id,
              loadKind: load.kind === 'surface' ? 'surface' : 'line',
            })
          }
        >
          Pick location on canvas
        </Button>
      )}
      {load.kind === 'element' && (
        <>
          <TextField
            select
            label="Member"
            value={load.element_id ?? ''}
            onChange={(event) =>
              updateEntity('loads', id, (entity) => {
                entity.element_id = event.target.value
              })
            }
          >
            {model.elements.map((element) => (
              <MenuItem key={element.id} value={element.id}>
                {elementDisplayLabel(model, element.id)}
              </MenuItem>
            ))}
          </TextField>
          {(['qx', 'qy'] as const).map((component) => (
            <ScientificField
              key={component}
              label={`${component} distributed intensity`}
              value={load.components[`${component}_i`] ?? 0}
              unit={`${model.units.force}/${model.units.length}`}
              onValueChange={(value) =>
                updateEntity('loads', id, (entity) => {
                  ;(entity.components as Record<string, number>)[
                    `${component}_i`
                  ] = value
                  ;(entity.components as Record<string, number>)[
                    `${component}_j`
                  ] = value
                })
              }
            />
          ))}
          <Alert severity="info">
            The distributed load is converted to consistent nodal forces in
            reference local coordinates. It is not a follower load.
          </Alert>
        </>
      )}
      {load.kind === 'surface' && (
        <>
          <TextField
            label="Scope"
            value={`${Array.isArray(load.extensions?.element_ids) ? load.extensions.element_ids.length : 1} Q4 elements`}
            disabled
          />
          {distributedDofs.map((dof) => (
            <ScientificField
              key={dof}
              label={`${dof} surface load`}
              value={load.components[dof] ?? 0}
              unit={`${model.units.force}/${model.units.length}²`}
              onValueChange={(value) =>
                updateEntity('loads', id, (entity) => {
                  ;(entity.components as Record<string, number>)[dof] = value
                })
              }
            />
          ))}
        </>
      )}
      {load.kind === 'edge' && (
        <>
          {boundaries.length ? (
            <TextField
              select
              label="Gmsh boundary"
              value={String(load.extensions?.boundary_id ?? boundaries[0].id)}
              onChange={(event) => selectBoundary(event.target.value)}
            >
              {boundaries.map((boundary) => (
                <MenuItem key={boundary.id} value={boundary.id}>
                  {boundary.label} · {boundary.length.toLocaleString('en-US')}{' '}
                  {model.units.length}
                </MenuItem>
              ))}
            </TextField>
          ) : (
            <Stack direction="row" spacing={1}>
              <TextField
                fullWidth
                select
                label="Element"
                value={load.element_id ?? ''}
                onChange={(event) =>
                  updateEntity('loads', id, (entity) => {
                    entity.element_id = event.target.value
                  })
                }
              >
                {model.elements.map((element) => (
                  <MenuItem key={element.id} value={element.id}>
                    {elementDisplayLabel(model, element.id)}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                fullWidth
                select
                label="Local edge"
                value={Number(load.extensions?.local_edge ?? 0)}
                onChange={(event) =>
                  updateEntity('loads', id, (entity) => {
                    entity.extensions = {
                      local_edge: Number(event.target.value),
                    }
                  })
                }
              >
                {[0, 1, 2, 3].map((edge) => (
                  <MenuItem key={edge} value={edge}>
                    Edge {edge + 1}
                  </MenuItem>
                ))}
              </TextField>
            </Stack>
          )}
          {distributedDofs.map((dof) => (
            <ScientificField
              key={dof}
              label={`${dof} line load`}
              value={load.components[dof] ?? 0}
              unit={`${model.units.force}/${model.units.length}`}
              onValueChange={(value) =>
                updateEntity('loads', id, (entity) => {
                  ;(entity.components as Record<string, number>)[dof] = value
                })
              }
            />
          ))}
          <Alert severity="info">
            Boundary intensity is integrated over each Gmsh segment into
            consistent nodal forces and keeps a fixed global direction.
          </Alert>
        </>
      )}
      <Button
        color="error"
        variant="outlined"
        startIcon={<DeleteOutlineRoundedIcon />}
        onClick={() => removeEntity('loads', id)}
      >
        Delete load
      </Button>
    </Stack>
  )
}
