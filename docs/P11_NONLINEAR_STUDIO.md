# P11 Nonlinear Studio frontend

## Scope

P11 adds a local React, TypeScript, Material UI, and Vite workbench on top of the P10 analysis
FastAPI contract. It does not change the nonlinear residual, tangent, state transaction, control,
or convergence algorithms.

The UI uses four persistent work areas:

1. a left model navigator for nodes, elements, materials, constraints, and loads;
2. a central engineering canvas for line/Q4 reference and deformed geometry, reactions, and
   family-specific element recovery;
3. a right inspector with property and nonlinear-analysis tabs; and
4. a bottom results dock for iteration monitoring, path/convergence curves, tables, and failures.

This organization follows the discoverable entity tree and central visualization patterns used by
CAE workbenches while keeping the primary run action and model/result status visible.

## Model editing and result ownership

The frontend edits the versioned `ModelInput` document directly. The family selector replaces the
complete working document with a verified Frame, Continuum, Plate, or Shell example. The entity
tree, property inspector, analysis controls, DOF choices, and add-entity templates derive from the
selected family instead of coercing every payload to Frame. JSON model import/export therefore
remains compatible with the P1/P10 contract. The
frontend also imports and exports a versioned restart bundle containing the exact model and
authenticated P10 continuation payload rather than creating a browser-only state shape.

All model and analysis-definition edits pass through one reducer action. That action:

- increments `modelRevision`;
- cancels the active API analysis and aborts its polling request;
- removes the current `AnalysisRecord`;
- resets result visualization to the model view; and
- records that the former result was invalidated.

An analysis response carries the revision captured at submission. A late response whose revision
does not match the current model is ignored, so stale output cannot become current again.

## Gmsh remeshing and distributed loads

Continuum, Plate, and flat Shell model properties expose a Gmsh target size and an explicit
`使用 Gmsh 生成网格` action. The service derives one exterior loop from the current Q4 topology,
calls Gmsh, and accepts the result only when every generated surface cell is a first-order Q4.
The current bridge supports one loop without holes; Shell input must be flat and parallel to the
XY plane. A mesh operation has its own abort controller and model revision guard, so changing
family or editing the model prevents a late response from replacing newer state.

Applying a mesh replaces nodes and elements, remaps nodal constraints and concentrated loads to
the nearest generated node, propagates matching end constraints along a generated boundary, and
records ordered Gmsh boundary segments in `model.extensions.gmsh`. Boundary distributed loads use
that metadata to target every Q4 edge segment after remeshing. The canvas `显示背景网格` control
therefore means only the plotting grid; the visible Q4 edges are the actual finite-element mesh.

The load inspector exposes only the load kinds supported by each family:

| Family | Distributed load | Components and unit | Direction contract |
|---|---|---|---|
| Frame | member | `qx`, `qy` in N/m | reference-member local axes; fixed, not follower |
| Continuum | boundary edge | `UX`, `UY` in N/m | fixed global direction |
| Plate | surface or boundary edge | `UZ` in N/m2 or N/m | fixed global direction |
| Shell | surface or boundary edge | `UX`, `UY`, `UZ` in N/m2 or N/m | fixed global direction |

The adapters integrate these loads into consistent element nodal vectors. Surface/edge load arrows
repeat across the selected elements or Gmsh boundary, while the inspector remains the numerical
source of truth.

## Control-specific settings

The analysis inspector progressively discloses the applicable settings:

- load control accepts a target load factor;
- displacement control accepts a node/DOF, signed increment, and number of steps;
- spherical arc length accepts the radius bounds, beta, and number of steps;
- load and displacement control expose the P7 adaptive cutback settings used by the API;
- arc length disables P7 line search because the P8 algorithm does not combine the two; and
- the arc-length view explicitly says convergence is not proof of stability, branch uniqueness,
  or successful branch switching.

## Result bridge

The P10 runner now serializes the existing adapter recovery into the already-versioned
`SolveResult.post_result` field after a successful solve:

- node-major displacement records;
- node-major reaction records; and
- element-local response records, including Frame end forces, Continuum Cauchy stress samples,
  and Plate/Shell membrane, bending, and shear resultants.

Frame elements render as line segments. Continuum, Plate, and Shell elements render as Q4 faces;
Plate/Shell `UZ` is shown using a labeled diagonal engineering lift. The results table is the exact
alternative to the color projection and keeps the Gauss averaging qualifier visible.

Failed solves still have no fabricated post-result. Their accepted/rejected steps, iteration
history, structured failure, JSON location, and solver details remain visible in the results dock.
While running, the monitor polls the retained record and shows the live step, iteration, accepted
step count, and server message. The primary action becomes an explicit cancellation control.

## Local run and acceptance

```bash
# terminal 1, repository root
.venv/bin/python -m nonlinear_api.main

# terminal 2
cd frontend
npm install
npm run dev
```

The Vite server proxies `/api` and `/health` to `127.0.0.1:8000`.

Verified P11 gates:

- `npm run typecheck`;
- `npm test`;
- `npm run build`;
- the full Python `pytest` suite; and
- real asynchronous HTTP analyses for the four verified families through the Vite proxy, in
  addition to deterministic mocked UI tests.
