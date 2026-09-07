---
version: alpha
name: "Nonlinear Studio"
description: "A compact CAE workbench that keeps nonlinear model state, solver progress, and numerical evidence visibly connected."
colors:
  primary: "#35635d"
  primary-dark: "#234a45"
  primary-light: "#789d96"
  secondary: "#256b8b"
  success: "#138a63"
  warning: "#b76a00"
  danger: "#bd4552"
  canvas: "#fcfdfc"
  background: "#f4f6f5"
  surface: "#ffffff"
  surface-container-low: "#f7f9f8"
  surface-container: "#f0f4f2"
  surface-container-high: "#e6eeea"
  text: "#253037"
  text-muted: "#68747b"
  divider: "#e2e7e4"
typography:
  sans:
    fontFamily: "Avenir Next, Segoe UI, system-ui, -apple-system, sans-serif"
  mono:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"
rounded:
  DEFAULT: "0.5rem"
  control: "0.375rem"
  compact: "0.3125rem"
spacing:
  control-gap: "0.5rem"
  content-gap: "0.75rem"
  panel-padding: "1rem"
  toolbar-height: "3.5rem"
  context-bar-height: "2.375rem"
components:
  app-bar: {}
  engineering-canvas: {}
  inspector: {}
  results-dock: {}
  button: {}
  field: {}
  table: {}
  status-chip: {}
---

# Nonlinear Studio Design System

## Overview

### Creative North Star

The user's latest direction replaces the crowded instrument-panel treatment with a quiet
structural drawing workspace. The canvas is the main surface. A single compact action bar and a
thin family/document row orient the user; the model list expands in place and Properties opens
when needed. Neutral white surfaces, muted green actions, flat fields and fine dividers reduce
competing emphasis. The distinctive element is the structural model itself, with restrained
engineering annotations. No decorative cards or always-visible explanatory banners surround it.

### Product context and register

- **Audience and primary job:** structural/FEM engineers preparing a bounded nonlinear model,
  running it, and checking convergence and recovery evidence without losing model provenance.
- **Target market and evidence:** engineering users; the repository's P1-P16 contracts and CAE
  entity tree determine the workflow. No market-specific visual motif is inferred from language.
- **Locales and language policy:** the owned UI is English-only. User-facing entities start with stable ordinal
  names such as `Model 1`, `Node 1`, `Material 1`, `Support 1`, and `Load 1`, and can be renamed from Properties;
  raw solver IDs remain unchanged inside API, import/export, and diagnostic contracts.
- **Usage scene:** desktop-first, keyboard-and-pointer, focused local engineering work.
- **Register:** product. Familiar model tree, inspector, viewport, and results-dock patterns win over
  brand expression.
- **Memorable signature:** four persistent model-family workspaces paired with an explicit Model/Results
  mode boundary. The fixed primary action makes Apply/Run ownership visible without a second action band.
- **Restraint:** forms, tables, toolbars, warnings, and failure evidence remain flat, compact, and
  literal.
- **Anti-references:** not a marketing dashboard, consumer 3D viewer, glassmorphic control panel,
  or decorative scientific poster; those styles would obscure exact state and numerical limits.
- **Token ownership/runtime mapping:** the established MUI theme in `frontend/src/theme.ts` remains
  the runtime source of truth. This file mirrors its accepted tokens and explains their use; token
  changes must update the theme and this document together.

## Colors

`primary` owns safe primary actions, focus, selection, and selection overlays. `secondary`
and `success` identify reaction and accepted-state evidence. `warning` marks recoverable limits or
invalidated results; `danger` is reserved for failures and destructive entity removal. The
`canvas` is a cool near-white plotting surface. Application chrome uses Material 3 surface roles
(`background`, `surface`, `surface-container-low`, `surface-container`, `surface-container-high`)
and `divider` so hierarchy is mostly tonal.

The near-white canvas is the largest quiet surface; structural geometry uses navy/teal, loads use red,
and reactions use teal. Result plots may use primary blue, danger red, success green, teal, and amber, but every color has
a label, number, icon, line style, or table alternative. The current release has one light workspace theme with a light identity header; high-contrast operation must retain platform focus and semantic text rather than relying on
canvas color alone.

## Typography

The canonical sans stack is defined by `typography.sans`: Avenir Next with Segoe UI and native system fallbacks for
compact English product copy. Headings use weight 600 and actions use weight 500 for hierarchy; body guidance
stays regular and compact. Solver
IDs, model IDs, DOF names, formulas, and exact JSON-oriented identifiers may use
`typography.mono`. Numeric tables use tabular alignment where the component supports it. English
technical identifiers are not title-cased or translated when translation would change the
contract.

## Layout

The desktop shell retains four independent families and Model/Results modes. A 56 px header
contains Project, the mode switch, Save project, Analysis, account, and the fixed 158 px Apply/Run
button. A 38 px family row names all four families, the current document, and its plain-text status.
A 2 px progress slot remains allocated. Project owns Open, Export, History, restart export,
Math Core, Guide, and example reset; its accessible MUI menu preserves the existing guards.

Model mode uses a 232 px single-column model list and a flexible canvas. Categories expand
in place, New precedes their records, and search appears above lists longer than eight records.
Lists keep 60-record pagination and selected-record reachability. Category counts and the bottom
model total replace duplicate count banners. Only applicable selected-entity deletion is shown.

A 48 px toolbar belongs to the canvas and contains Select, Node/Outline, Member/Hole, Support,
and Load. Sections live in the model list; member splitting lives in Properties. Properties is
320 px wide when open and occupies no space when closed. Model metadata opens from the list's
settings action; entity selection opens its form. The form remains mounted while hidden so raw
unfinished numeric text survives close/reopen. Drawing does not automatically open the inspector
and resize the canvas between endpoint clicks. The 34 px footer shows edit status and Cancel
only when there is a draft. Primary action placement is stable in every state.

Results uses the full canvas after a successful solve. Results & tables opens a 460 px evidence
panel with independent scrolling; running and failed solves reveal that panel automatically.
Hiding it never deletes results, selection or result-tab state. Result quantity remains directly
accessible on the canvas. The camera toolbar is one flat horizontal group at bottom-right;
units and grid scale sit unboxed at bottom-left. The grid uses faint major lines without dots.

The desktop support floor remains 1120 px, with document horizontal scrolling below that width.
Navigator, Properties and result evidence own separate vertical scrollers. Bounded dialogs stay
within smaller viewports. SVG pointer and diagram coordinates use the measured viewport transform.
Guest access and authenticated private history retain the established data and permission rules.

## Elevation & Depth

White surfaces, whitespace and one-pixel dividers establish hierarchy. App chrome and canvas
controls stay flat. Elevation is reserved for open menus, dialogs and transient notifications. Properties sections, tables, alerts, and static content
stay flat. The near-white canvas layers compact opaque controls over the plot, but does not use blur or
translucent glass effects.

## Shapes

Controls use the `control` radius (6 px), major work panes use `DEFAULT` (8 px),
and outlined fields use `compact` (5 px). Dense table frames use `DEFAULT`. Status chips stay 4 px rounded because they
encode transient state, not navigation.
Entity geometry uses precise strokes and nodes rather than rounded card metaphors. Dividers remain
one-pixel neutral lines.

## Components

### Foundational visual states

All interactive controls retain MUI's default, hover, focus-visible, active, disabled, and busy
semantics. Selected entities combine color with stroke/weight or selected-row treatment. Analysis
uses a stable determinate indicator only when measurable; otherwise the existing indeterminate
bar and textual Step/Iteration state are canonical. Warning, failure, empty, invalidated, and
success states stay in the panel they affect.

### Buttons and actions

One fixed-width primary action in the app bar changes with the transaction state: Apply changes
for a draft, Run analysis for a committed model, and Cancel while a server job is active.
Invalid numeric drafts disable Apply; the footer retains only draft status and Cancel. Import, export, example reset, and view controls are secondary.
Delete is outlined danger and separated inside the selected entity inspector. Busy labels and
icons retain the button's dimensions.

### Navigation and data display

The workspace bar changes the active working document and must show all four supported families by
name while preserving each family's independent model, draft, selection, analysis, and result state.
The Model/Results toggle owns the top-level mode boundary. The canvas toolbar groups drawing and placement; Analysis settings opens from the header. The left explorer
uses Geometry, Materials, Sections, Supports, Loads, Mesh, Nodes and Elements categories. Each
category owns an explicit New action and an inline list. Larger lists offer search; selected entities expose Delete selected.
Lists show 60 records at a time with Show more; the selected entity remains reachable. Entity navigation,
canvas result modes and result tabs each own one level of state. Properties belongs only to the
selected entity. Analysis settings is a separate bounded dialog opened from the header;
loading strategy is visible first, with Newton and step controls in collapsed disclosures. Tables retain headers
and scroll within their result frame. Surface families
render as closed Q4 faces; Frame renders as line elements. Every result overlay has a table
alternative.

Mesh is a first-class item in the left entity navigator alongside nodes, elements, materials,
constraints, and loads. Selecting it opens the dedicated mesh inspector; the model-family context
bar and canvas toolbar do not duplicate that canonical action. The canvas caption reports mesh provenance; the model list reports live node/element totals. Target size accepts every finite value
greater than zero; an example value is never presented or enforced as a lower bound. Limitations,
explicit generation, busy state, and generated node/element summary stay together in the inspector.
Dense surface meshes show every node and element in the tree and canvas by default and keep them
selectable for inspection. They are read-only: topology changes originate from Geometry and Mesh, not
from direct node movement, renaming, connectivity edits, additions, or deletion. Unselected entity
labels remain suppressed; selected, loaded, and constrained node labels remain visible so topology is
readable after refinement.
`Show background grid` controls only the plotting aid; Q4 element edges are always the finite-element mesh.
Distributed loads render as repeated directional arrows over their member, surface, or boundary,
while exact components, units, coordinate system, and fixed-reference limitation remain in the
selected load inspector.

### Canvas navigation and domain rendering

Zoom controls and the wheel zoom about the chosen anchor; Fit model/F restores framing. Pan view,
Alt + drag, and middle-button drag move the camera. Focused canvas arrow keys provide a non-drag
pan alternative. Ctrl + wheel remains browser-owned. Escape cancels an active drag or pan mode.
Frame and sketch drags preserve the original camera and commit one draft change on release after
a 4 px movement threshold; pointer cancellation restores the original model. Grid spacing follows
physical coordinates and is shown with model length units. Dense mesh labels show selected,
loaded, and constrained nodes; all mesh nodes remain selectable. Result mode omits editable sketch
overlays, displays reactions at all constrained mesh nodes, and retains explicit final-state
recovery warnings. Nodal load rendering includes every load and nonzero component; rotational
components use moment arcs. Navy geometry, coral loads, slate supports, and dashed reference
geometry retain engineering roles distinct from the muted green UI actions.

### CAD outline and load placement

Geometry owns a compact Draw outline / Insert vertex / Add hole flow. Outline creation is a
transient preview: click corners (Shift constrains the next edge), enter exact X/Y coordinates,
Undo vertex, then Close outline. Closing a valid outline stages one reversible domain replacement;
the previous holes, supports and loads are cleared because they belong to the previous domain.
Cancel restores the committed model. Self-crossing, collapsed and touching contours are rejected.
Run/Apply stays unavailable while an outline is being drawn. Mesh-pending geometry hides stale FE
faces and reports its state rather than presenting the previous mesh as current.

HoleFields is the shared shape/dimension form: Circle asks for radius, Rectangle for width and
height, and Square for side length. The next canvas click sets the center. Invalid or overlapping
holes stay in placement with an inline error. A selected hole opens the same shape fields plus
Center X/Y and Update hole; this local dimension proposal is applied to the model draft only by
Update hole. Reset dimensions discards the local proposal. Existing polygon holes retain vertex
editing. Circle definitions persist as four arc endpoints and center/radius metadata; Gmsh uses
real circular arcs while the first-order Q4 boundary consists of straight chords.

Every Load entry starts placement without creating a record or selecting a default location.
Auto placement maps the first node click to a point load and the first member/element click to a
line load. The placement selector also offers explicit Point / Line (and Plate/Shell Surface).
Surface line loads select the nearest exposed edge of the clicked Q4 cell; interior cells are
rejected, and a Gmsh CAD boundary applies to all its mesh edge segments. Intensity is force/length,
Frame uses fixed reference local directions, and surface boundaries use fixed global directions.
Pick location on canvas preserves the load number and intensity when the kind stays the same.
Changing kind also waits for a target click, leaving the previous load intact until then. Successful
placement opens the new load's inspector. Escape cancels placement without creating a load.

### Frame creation and section-force diagrams

Every New node/member entry point enters canvas placement. Node clicks create or snap within
10 screen pixels. Member creation accepts two empty points, existing nodes, or a combination;
a dashed preview follows the pointer. Zero-length and duplicate members are rejected. The camera
remains stable throughout placement. Escape exits the tool; Cancel restores the full committed model.

Frame Results offers Moment M, Shear V, and Axial N filled diagrams using one common scale across
members. Only the selected member shows end and peak values, avoiding overlapping all-member
text. Diagram clicks and the Member section forces selector share selection; a scrollable station
table supplies x, N, V, and M. Scientific numeric cells never wrap mid-exponent.

Diagrams use recovered end actions from the last accepted state. Earlier steps show a recovery
notice and an explicit action to return to that state. Missing end actions produce an empty state.
N is positive in tension, x follows i to j, V = dM/dx, and M(0) = -Mi / M(L) = Mj after member-load
correction. Nodal-only recovery uses current member length. Distributed-load corrections use the
reference local axes and length; the canvas and table disclose the large-rotation approximation.
Legacy internal-force archive views map to Moment for Frame. Project schemas persist the new views.

ScientificField is the canonical load-component input. It accepts decimal and e/E notation and
preserves incomplete exponent text. Non-finite inputs stay visible as invalid drafts and cannot
be applied or sent to the solver. Cancel restores the committed finite value.

### Sections, direct editing, and project files

SectionPanel owns Custom A/I, Rectangle, Circle, I section, Tube, and surface thickness definitions.
It stages valid materialized properties on assigned elements. Invalid dimensions stay visible and
block Apply, but Cancel and discard remain available. A definition can be the default for new
Frame members or regenerated Q4 elements. The server validates the reserved section library and
its consistency with the actual element properties. Legacy models remain usable without metadata.

SplitElementPanel accepts fractions/decimals measured from i to j, previews positions as text,
and stages connected members with inherited material/section and interpolated distributed loads.
Delete and Backspace invoke the same operation as Delete selected, outside fields, IME, dialogs,
and Results. Model removal is reversible through Cancel. Referenced materials/sections and
connected nodes require resolving their references first; generated mesh topology stays protected.

Save project opens a bounded dialog with Download project and private account-save destinations.
Model, run options, optional terminal analysis record, and the selected result view travel together.
Opening a project validates its version, schema, and model/result fingerprints before restoring it.
A 20 MB archive limit is separate from the existing solver-submission limit. Legacy model/restart
files and model-only account snapshots remain supported. Save errors remain in the dialog.

### Progressive disclosure and retained state

Long SectionHeader descriptions use native Details disclosures. Element details and Split member
use accessible MUI accordions. Entity connectivity, material and section remain immediately editable;
derived properties and formulation are available in Element details. This removes read-only fields
from the main editing path without removing evidence. Analysis loading strategy stays visible while
Newton and step settings remain folded by default. Errors and invalidated-result notices remain
persistent in their owning form or evidence panel. Opening Analysis from Results returns to Model
before editing so the draft is never mistaken for the read-only result model.

### Runtime token mapping

| Token group | Runtime owner | Consumers |
| --- | --- | --- |
| Colors, typography, radii | `frontend/src/theme.ts` | MUI controls, chrome, inspectors, dialogs, charts |
| Canvas surface, grid, selection, reactions | `studioTheme.palette` | `ModelCanvas.tsx` via `useTheme` |
| Geometry, load and support glyphs | Domain drawing colors in `ModelCanvas.tsx` | SVG only; unchanged engineering role |
| Scrollbars and reduced motion | `MuiCssBaseline` in `theme.ts` | All owned scrolling surfaces |

### Forms and overlays

MUI outlined TextField/Select remains the canonical field and authored select owner. Fields keep
persistent labels, numeric step metadata, unit adornments where the unit is already in the model,
and inline helper/error text. Model and analysis-option edits are staged; the persistent transaction
strip owns Cancel and the header owns Apply changes, while an app-owned three-outcome dialog guards navigation away
from staged work. Snackbars acknowledge completed low-risk actions; validation, solve failure, and
invalidated results remain persistent inline.
Tooltips supplement icon actions and never contain the only instruction. The application stylesheet
owns one visible, tokenized scrollbar baseline; component styles only add geometry exceptions such
as stable gutters.

The first-use beginner guide is an app-owned, keyboard-accessible six-step dialog. It opens on first
use, can be dismissed permanently with guarded local storage, and always remains available from the
`Project → Guide` action. Each guide step can open its corresponding workflow destination.

Authentication uses one shared sign-in/register dialog with app-owned validation, masked password
fields, accessible reveal controls, and a persistent explanation of Guest mode. Accounts are optional:
Guest can model, mesh, solve, open, and download projects with results, while account saving and private history require
an authenticated HttpOnly session. History is private per account, bounded to 24 snapshots, and uses a
single pessimistic delete confirmation that names the snapshot and states that deletion is permanent.

The Step 2 Math Core is a Project-menu utility, not a fifth model workspace or a Results tab. Its bounded
dialog uses the established MUI fields and dialog geometry, pairs each core/operation selector with a
server-owned executable JSON example, and keeps the residual convention and trial/commit boundary
visible beside the request. Response envelopes remain literal, scrollable, and monospaced. The tool is
disabled while a nonlinear analysis is running and never mutates the active model, revision, draft, or
result evidence.

Entity display names are stored as UI metadata in the model `extensions` object. The navigator,
Properties header, canvas, selectors, exports, and saved snapshots consume the same label resolver.
Renaming never mutates solver IDs or connectivity references; clearing a custom name restores the
generated ordinal label.

### Iconography

Material Rounded icons are canonical at small/medium sizes. Icon-only controls require an English
accessible name through their tooltip/label. Family, entity, run, import/export, and status icons
support text; they do not replace it.

### Motion

Motion communicates state only: 160-200 ms for disclosure, selection, and disclosure changes. Analysis progress is continuous only while work is active. Reduced-motion mode removes
geometry transitions and retains immediate state changes and readable progress text.

### Content and data visualization

Copy is direct English and technical: name the family, formulation, DOF, Step, Iteration, load factor,
units, and limitation. Do not describe convergence as proof of stability or generalize a bounded
element formulation. Numerical values use English locale grouping with scientific notation for
very large or small magnitudes. Plot colors always have legends, axis labels, and tabular evidence.

## Do's and Don'ts

- **Do:** keep model family, formulation, DOF set, active result, and solver status visibly aligned.
- **Do:** reuse the established MUI theme and navigator/canvas/inspector workbench across every family.
- **Don't:** expose a model-family option that only changes copy while submitting a Frame payload.
- **Don't:** imply full 3D shell rendering, stability proof, or unsupported constitutive behavior
  from the current projected visualization.
