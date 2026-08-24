---
version: alpha
name: "Nonlinear Studio"
description: "A compact CAE workbench that keeps nonlinear model state, solver progress, and numerical evidence visibly connected."
colors:
  primary: "#4563b5"
  primary-dark: "#30498f"
  primary-light: "#7890d4"
  secondary: "#008b8b"
  success: "#138a63"
  warning: "#b76a00"
  danger: "#c43d4b"
  canvas: "#fbfcff"
  background: "#f4f5f8"
  surface: "#ffffff"
  surface-container-low: "#f1f2f6"
  surface-container: "#ebeef5"
  surface-container-high: "#e5e9f2"
  text: "#202431"
  text-muted: "#626977"
  divider: "#d9dde6"
typography:
  sans:
    fontFamily: "Roboto, system-ui, -apple-system, Segoe UI, sans-serif"
  mono:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"
rounded:
  DEFAULT: "1rem"
  control: "1.25rem"
  compact: "0.5rem"
spacing:
  control-gap: "0.5rem"
  content-gap: "0.75rem"
  panel-padding: "1rem"
  toolbar-height: "4rem"
  context-bar-height: "3.5rem"
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

The interface follows the Frame Studio workbench language: quiet white and cool-gray surfaces,
cobalt workflow/action accents, precise dividers, and a light gridded model space where geometry,
constraints, loads, deformation, and recovered responses stay visibly connected. Nonlinear-specific
controls and evidence remain explicit rather than being hidden behind the simpler visual language.

### Product context and register

- **Audience and primary job:** structural/FEM engineers preparing a bounded nonlinear model,
  running it, and checking convergence and recovery evidence without losing model provenance.
- **Target market and evidence:** engineering users; the repository's P1-P16 contracts and CAE
  entity tree determine the workflow. No market-specific visual motif is inferred from language.
- **Locales and language policy:** the owned UI is English-only. User-facing entities start with stable ordinal
  names such as `Model 1`, `Node 1`, `Material 1`, `Support 1`, and `Load 1`, and can be renamed from Properties;
  raw solver IDs remain unchanged inside API, import/export, and diagnostic contracts.
- **Usage scene:** desktop-first, keyboard-and-pointer, information-dense local engineering work.
- **Register:** product. Familiar model tree, inspector, viewport, and results-dock patterns win over
  brand expression.
- **Memorable signature:** a load-path workflow rail whose connected nodes move from model definition
  to the committed solve, paired with a compact model builder and a persistent left Properties workspace.
- **Restraint:** forms, tables, toolbars, warnings, and failure evidence remain flat, compact, and
  literal.
- **Anti-references:** not a marketing dashboard, consumer 3D viewer, glassmorphic control panel,
  or decorative scientific poster; those styles would obscure exact state and numerical limits.
- **Token ownership/runtime mapping:** the established MUI theme in `frontend/src/theme.ts` remains
  the runtime source of truth. This file mirrors its accepted tokens and explains their use; token
  changes must update the theme and this document together.

## Colors

`primary` owns safe primary actions, focus, selection, and the normal model overlay. `secondary`
and `success` identify reaction and accepted-state evidence. `warning` marks recoverable limits or
invalidated results; `danger` is reserved for failures and destructive entity removal. The
`canvas` is a cool near-white plotting surface. Application chrome uses Material 3 surface roles
(`background`, `surface`, `surface-container-low`, `surface-container`, `surface-container-high`)
and `divider` so hierarchy is mostly tonal.

The light canvas is the largest quiet surface; structural geometry uses navy/cobalt, loads use red,
and reactions use teal. Result plots may use primary blue, danger red, success green, teal, and amber, but every color has
a label, number, icon, line style, or table alternative. The current release has one light chrome
theme; high-contrast operation must retain platform focus and semantic text rather than relying on
canvas color alone.

## Typography

The canonical sans stack is defined by `typography.sans`: Roboto with native system fallbacks for
compact English product copy. Headings and actions use weight 500 for hierarchy; body guidance
stays regular and compact. Solver
IDs, model IDs, DOF names, formulas, and exact JSON-oriented identifiers may use
`typography.mono`. Numeric tables use tabular alignment where the component supports it. English
technical identifiers are not title-cased or translated when translation would change the
contract.

## Layout

The desktop shell follows Frame Studio's working order: a workflow-led model builder at the far left,
a persistent Properties/Analysis workspace immediately beside it, the canvas as the main right-hand
region, and a bottom result dock. The two left regions share one bounded work surface so selecting a
tree or canvas entity always reveals its editable properties without crossing the screen. The shell
sits under a two-row top app bar (identity/actions, then model-family context) and a collapsible
six-step workflow rail.
The model builder starts directly with Setup and Topology entities; it does not repeat workflow
readiness or search controls above the list. Double-clicking an entity collapses Properties to a
named 48 px restore rail, while the visible collapse/expand buttons provide keyboard and touch access.
`toolbar-height`, `context-bar-height`, `panel-padding`, `content-gap`, and `control-gap` mirror
the MUI 8 dp grid. The canvas and results dock may own bounded scrolling; the Properties workspace and
navigator keep visible scrollbars. Geometry is reserved during analysis so progress, success, and
error states do not move the primary action.

The current engineering workspace has a 1120 px desktop support floor. Narrow-width verification
must preserve horizontal access to all four regions; a future mobile workflow requires a separate
navigation contract rather than silently hiding model or result controls.

Identity is progressive rather than a route gate. Guest mode opens the complete modeling and analysis
workspace immediately. The top app bar groups Save, History, account identity, and Sign out without
moving the primary Run analysis action. Authentication and model history use bounded MUI dialogs so
the current model stays visible and is not discarded when a session changes.

## Elevation & Depth

Tonal surface containers establish most hierarchy. The app bar, canvas overlay, and result-dock
chrome may use modest Material elevation (levels 1–2) because they contain persistent
actions/status or overlap the plotting bed. Properties sections, tables, alerts, and static content
stay flat. The light canvas layers compact opaque controls over the plot, but does not use blur or
translucent glass effects.

## Shapes

Controls use the `control` radius (M3 buttons ~20 dp), major work panes use `DEFAULT` (16 dp),
and filled fields / dense table frames use `compact`. Status chips stay 8 dp rounded because they
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

There is one primary action in the app bar: run analysis, which becomes an explicit cancel action
while a server job is active. Import, export, example reset, and view controls are secondary.
Delete is outlined danger and separated inside the selected entity inspector. Busy labels and
icons retain the button's dimensions.

### Navigation and data display

The model-family selector changes the entire working document and must show all four supported
families by name. The workflow rail opens the canonical edit target for Model, Materials, Supports,
Loads, Mesh, and Solve; completion markers come from live model/analysis state. The left builder
starts directly with Setup and Topology and keeps every entity reachable. Entity navigation,
inspector tabs, canvas result modes, and result tabs each own one level of state. Tables retain headers
and scroll within their result frame. Surface families
render as closed Q4 faces; Frame renders as line elements. Every result overlay has a table
alternative.

Mesh is a first-class item in the left entity navigator alongside nodes, elements, materials,
constraints, and loads. Selecting it opens the dedicated mesh inspector; the model-family context
bar and canvas toolbar do not duplicate that canonical action. The canvas status chip always
reports mesh provenance plus live node/element counts. Target size accepts every finite value
greater than zero; an example value is never presented or enforced as a lower bound. Limitations,
explicit generation, busy state, and generated node/element summary stay together in the inspector.
Dense surface meshes keep every node and element selectable but suppress unselected entity labels;
selected, loaded, and constrained node labels remain visible so topology is readable after refinement.
`Show background grid` controls only the plotting aid; Q4 element edges are always the finite-element mesh.
Distributed loads render as repeated directional arrows over their member, surface, or boundary,
while exact components, units, coordinate system, and fixed-reference limitation remain in the
selected load inspector.

### Forms and overlays

MUI filled TextField/Select remains the canonical field and authored select owner. Fields keep
persistent labels, numeric step metadata, unit adornments where the unit is already in the model,
and inline helper/error text. Snackbars acknowledge completed
low-risk actions; validation, solve failure, and invalidated results remain persistent inline.
Tooltips supplement icon actions and never contain the only instruction. The application stylesheet
owns one visible, tokenized scrollbar baseline; component styles only add geometry exceptions such
as stable gutters.

The first-use beginner guide is an app-owned, keyboard-accessible six-step dialog. It opens on first
use, can be dismissed permanently with guarded local storage, and always remains available from the
top-level `Guide` action. Each guide step can open its corresponding workflow destination.

Authentication uses one shared sign-in/register dialog with app-owned validation, masked password
fields, accessible reveal controls, and a persistent explanation of Guest mode. Accounts are optional:
Guest can model, mesh, solve, import, and export, while server-enforced saving and model history require
an authenticated HttpOnly session. History is private per account, bounded to 24 snapshots, and uses a
single pessimistic delete confirmation that names the snapshot and states that deletion is permanent.

Entity display names are stored as UI metadata in the model `extensions` object. The navigator,
Properties header, canvas, selectors, exports, and saved snapshots consume the same label resolver.
Renaming never mutates solver IDs or connectivity references; clearing a custom name restores the
generated ordinal label.

### Iconography

Material Rounded icons are canonical at small/medium sizes. Icon-only controls require an English
accessible name through their tooltip/label. Family, entity, run, import/export, and status icons
support text; they do not replace it.

### Motion

Motion communicates state only: 160-200 ms for disclosure, selection, and result-dock height
changes. Analysis progress is continuous only while work is active. Reduced-motion mode removes
geometry transitions and retains immediate state changes and readable progress text.

### Content and data visualization

Copy is direct English and technical: name the family, formulation, DOF, Step, Iteration, load factor,
units, and limitation. Do not describe convergence as proof of stability or generalize a bounded
element formulation. Numerical values use English locale grouping with scientific notation for
very large or small magnitudes. Plot colors always have legends, axis labels, and tabular evidence.

## Do's and Don'ts

- **Do:** keep model family, formulation, DOF set, active result, and solver status visibly aligned.
- **Do:** reuse the established MUI theme and four-region CAE workbench across every family.
- **Don't:** expose a model-family option that only changes copy while submitting a Frame payload.
- **Don't:** imply full 3D shell rendering, stability proof, or unsupported constitutive behavior
  from the current projected visualization.
