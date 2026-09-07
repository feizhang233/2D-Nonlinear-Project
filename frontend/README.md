# Nonlinear Studio frontend

## Try it online

**[Launch Nonlinear Studio in your browser →](https://nonlinear.feizhang233.com)**

No installation is required. Guest mode includes modeling, meshing, analysis,
and export; create an account only when you want to save models.

P11 is a React + TypeScript + Material UI workbench for the existing P10 FastAPI service.

The model-family selector loads complete verified examples for Frame, Continuum, Plate, and Shell.
The navigator and property inspector use each family's node count, formulation, material/property
shape, and DOF order. The canvas renders Frame line elements or Q4 surface projections; recovered
tables show Frame end forces, Continuum Cauchy stress, or Plate/Shell `N/M/Q` resultants.
The left model navigator exposes mesh as a first-class item. Its inspector lets Continuum, Plate,
and flat Shell regenerate an all-Q4 mesh with Gmsh, while Frame reports its explicit line topology. The
load inspector supports Frame member, Continuum edge, and Plate/Shell surface or edge distributed
loads with repeated canvas arrows and explicit units/direction limits.

```bash
npm install
npm run dev
```

Start the API from the repository root in another terminal:

```bash
.venv/bin/python -m nonlinear_api.main
```

Vite proxies `/api` and `/health` to `http://127.0.0.1:8000`. For a separate deployed API, set
`VITE_API_BASE_URL` and allow the frontend origin with `NONLINEAR_CORS_ORIGINS`.

The workspace runs analyses in the local asynchronous API mode, polls live step/iteration progress,
and exposes cooperative cancellation. It clears current results and restart state whenever the
model changes. Versioned restart bundles can be exported from terminal results and imported for a
continued calculation. Arc-length convergence is labelled only as augmented-equilibrium
convergence; the UI does not present it as a stability or branch-uniqueness result.

The top-level `Math Core` tool opens a separate reference-operation dialog backed by
`/api/v1/math-cores`. It exposes server-owned core/operation metadata, executable JSON
examples, residual/state conventions, limits, and the stable response envelope. Running a
reference operation never changes the active workspace, staged model, or Results evidence.


## Workbench interaction

The editor uses a left model navigator, a central drawing canvas, and a right
Properties inspector that opens on selection. Analysis settings opens from the header in its own dialog.
The header button applies staged changes, then becomes Run analysis; the bottom bar cancels edits.
All four model families keep independent documents and results.

- Wheel or +/− controls: zoom about the pointer or viewport center.
- Fit model / F: fit the model to the current viewport.
- Pan view, Alt + drag, or middle drag: move the view; canvas arrow keys also pan.
- Escape: cancel a drag or leave pan/edit placement mode.
- Node/sketch drag: preview while moving; stage one change on release.
- Ctrl/Command + Enter: apply/run/cancel according to state, outside fields, menus, and dialogs.

Generated surface mesh entities are inspectable but remain read-only. Import
validates the model with the backend before replacing the current document.
Requests distinguish schema/limit failures, invalid responses, timeouts, and
cancellation; uncertain server completion is never automatically retried.

See [the September 2026 audit](../FRONTEND_AUDIT_2026-09-05.md) for findings,
fixes, verification, and remaining platform boundaries.

## Project editing and persistence

- Use the category explorer for Geometry, Materials, Sections, Supports, Loads, Mesh, Nodes and Elements.
- Sections support custom A/I, rectangles, circles, I sections, tubes, and surface thickness. Assign to one or all elements; choose a default for new members and remeshing.
- Select a load/support on the canvas or in the explorer, then press Delete or Backspace. The same operation is available as Delete selected. Cancel restores staged removals.
- Select a Frame member and use Split selected / Split member. Half, quarters, thirds or custom fractions/decimals create connected members and preserve distributed loading.
- Save project downloads model/settings and optional results, or saves a private account snapshot. Open accepts project, legacy model and restart JSON. Archived results are verified against the model before restoration.
- Archives are limited to 20 MB. Solver submissions retain the 1 MiB limit. Remeshing applies the default section to new elements; mixed per-element assignments should be reviewed afterward.

## Frame diagrams and point creation

Use Node or New nodes, then click the canvas. Use Member or New elements, then click two points;
endpoints snap to nearby existing nodes, and empty points create new nodes. Cancel restores the
committed model. Load components accept scientific notation such as `-2.5e4`; incomplete or
non-finite values stay invalid until corrected.

After solving, choose Moment M, Shear V, or Axial N. Click a diagram to show its end/peak labels,
or use Result tables → Member section forces for station values. Diagram and table selection
stay synchronized. Recovery belongs to the last accepted state; earlier steps offer a return action.
Distributed member-load correction uses reference axes and is approximate for large rotations.
See [Frame workflow acceptance](../FRAME_WORKFLOW_UPDATE_2026-09-06.md) for conventions and checks.

## Simplified workspace

The compact header keeps Save, Analysis and Apply/Run in stable positions. Project groups Open,
Export, History, Math Core, Guide and example reset. The model list expands one category at a time;
large lists include search. Properties occupies no space when closed and retains unfinished input.
The canvas toolbar owns drawing and placement; Sections and Split member stay in their contextual
locations. Successful analyses foreground the result canvas; Results & tables opens the evidence
panel, which appears automatically for progress and failures. See
[the UI redesign acceptance](../SIMPLE_UI_REDESIGN_2026-09-06.md).

### CAD and load placement

Use **Load**, then click a node for a point load or a member / exposed Q4 edge for a line load.
The placement selector can constrain the kind. Load intensities support decimal and `e` notation.
The same first-click rule applies to **Loads → New load** and **Pick location on canvas**.

In a surface workspace, **Outline** starts a polygon sketch. Click vertices (Shift aligns an edge),
or enter exact X/Y, then **Close outline**. This replaces the domain and its old holes/supports/loads;
**Cancel** restores the committed model. **Hole** offers Circle (radius), Rectangle (width/height),
or Square (side), then a canvas click places its center. Select a hole to update its dimensions.
Generate a new mesh from **Mesh** after geometry changes. Circular CAD edges use Gmsh arcs;
first-order Q4 elements approximate the curved boundary with straight edge segments.
