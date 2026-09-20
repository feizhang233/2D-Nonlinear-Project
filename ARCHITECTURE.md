# Architecture and contract ownership

Reviewed: 2026-09-20. This review covers the Studio frontend, host API, nonlinear
adapters/solver, four spatial integrations, reference-core gateway, persistence,
packaging and CI. The review was performed on the working tree, including the
new spatial workspaces, without reverting the existing uncommitted work.

## Execution paths

| Workflow | Frontend owner | HTTP entry | Numerical owner |
| --- | --- | --- | --- |
| 2D nonlinear Frame / Continuum / Plate / Shell | `App.tsx`, `state.ts`, family editors and analysis hooks | `/api/v1/analyses` | `nonlinear_core/adapters` → shared nonlinear solver → `SolveResult` |
| Linear Frame 3D | `spatial/SpatialWorkbench.tsx` and its CAD document | `/api/v1/3d/solve` | Preserved `reused_cores/frame3d_linear` contract and solver |
| Linear Continuum 3D | `continuum3d/SolidWorkbench.tsx` | `/api/v1/continuum3d/solve` | `nonlinear_core/continuum3d.py` → preserved solid kernel |
| Linear Plate 3D | `plate3d/PlateWorkbench.tsx` | `/api/v1/plate3d/solve` | `nonlinear_core/plate3d.py` → preserved plate kernel |
| Linear Shell 3D | `shell3d/ShellWorkbench.tsx` | `/api/v1/shell3d/solve` | `nonlinear_core/shell3d.py` → preserved shell kernel |
| Independent reference operations | `MathCoreDialog.tsx`, `mathCore.ts` | `/api/v1/math-cores/execute` | Math Core operation registry and reference handlers |

The nonlinear solver continues to own residuals, Newton iteration, stepping,
commit and rollback. Adapters provide forces, tangents and recovery. Spatial
linear-static requests remain independent of that state machine and its model
family enum. Reference operations do not automatically become model capabilities.

## Dependency direction

```text
frontend workbenches
  ├─ domain/editor models → generated/api.ts
  ├─ api.ts / api/spatial.ts → api/transport.ts
  └─ shared controls, spatial vector/canvas/table helpers

FastAPI app → family routes → spatial_execution + errors
                           → numerical family adapter → preserved reference core
numerical family adapters → spatial_contracts

Python models → OpenAPI snapshot → generated TypeScript wire contracts
```

`spatial_contracts.py` owns only common finite numbers, identifiers, vectors,
nodes and equilibrium-check shapes. It imports no solver or HTTP module.
Numerical families must not import another family's adapter to borrow contracts;
HTTP routers must not borrow private functions from sibling routers. The
integration tests enforce this boundary for the spatial Python modules.

## Single source of interface truth

Python/Pydantic models own HTTP wire shapes. `schemas/openapi-1.0.0.json` is the
reviewable snapshot; `frontend/src/generated/api.ts` is generated from it. The
generator preserves required/optional fields, nullability, enum literals,
fixed-length tuples and route request/response types. Unsupported schema shapes
fail generation. Runtime numeric bounds and referential/physical validity remain
the backend's responsibility; TypeScript does not validate arbitrary network JSON.

`domain.ts`, `mathCore.ts` and the spatial model modules derive their wire types
from the generated contracts. Editor state may require explicitly materialized
defaults and add draft/selection/camera fields. These are UI concerns, not a
second manually maintained definition of solver results. Generic JSON reference
parameters intentionally remain recursively typed JSON rather than fictitious
per-operation structural models.

`api/transport.ts` owns credentials, timeout, abort propagation and readable API
errors. `api/spatial.ts` binds each 3D POST path to its generated request and
response types. The existing `api.ts` exports remain compatible with callers;
2D/auth/reference wrappers use generated-derived result types and checked request
payloads. Error details include the backend's authentication error category.

Update contracts from the project root with the activated Python environment:

```bash
python scripts/generate_openapi.py
python scripts/generate_frontend_contracts.py
python scripts/check_release.py
python scripts/generate_frontend_contracts.py --check
npm --prefix frontend run typecheck
```

CI checks both runtime Python → OpenAPI and OpenAPI → TypeScript drift. The
generated file is committed source and must not be edited manually. Spatial
routes explicitly publish their error envelopes and typed capabilities. Frame
force plots publish `image/png` and are excluded from JSON client generation.

## Shared execution boundary, distinct physical models

`spatial_execution.py` owns node/element budgets, nonblocking admission, expected
numerical/input error translation and semaphore release. Each family retains its
own solve slot, error-code prefix and physical conventions. Frame additionally
limits result-station/section-point recovery volume. `errors.py` owns `ApiProblem`
so spatial routes do not depend on the nonlinear analysis service.

| Family | DOFs per node | Default node cap | Element cap |
| --- | --- | --- | --- |
| Frame 3D | 6 | 100 | 400 |
| Continuum 3D | 3 | 200 | 1200 |
| Plate 3D | 3 | 200 | 400 |
| Shell 3D | 6 | 100 | 200 |

The effective node cap is `min(600, api_limits.max_dofs) // dofs_per_node`;
capability endpoints report the effective value. Admission is process-local,
as before. Multiple server workers do not share these semaphores. Cancelling a
browser request stops waiting and discards late results; it cannot terminate
an already executing dense factorization.

## Frontend state ownership

`workspaces.ts` owns dimension/family identity. `useSpatialNavigation` records
the active and visited spatial families; `SpatialWorkspaces` hosts them. Visited
workbenches stay mounted so camera state and incomplete scientific input survive
navigation. Switching dimension selects the corresponding family document and
does not convert its geometry or results. Existing 2D unsaved-change guards remain.

`useSpatialDocument` owns the common Solid/Plate/Shell lifecycle:

- Local load/persistence, validated atomic import and portable export.
- Model replacement with a bounded 50-entry undo history and redo.
- One pending request, cancellation and revision invalidation.
- No old success or failure may overwrite state after an edit or navigation.
- A cancelled file read must not proceed to server validation.

Family workbenches own their forms, topology generation, numeric drafts and result
presentation. Frame retains its distinct CAD document lifecycle because incomplete
topology is a valid editing state. It receives the same stale-import protection;
its exported solver request is validated at solve time. Solid/Plate/Shell imports
also pass their respective backend `/validate` endpoint before replacement.

Spatial vector helpers now live in `spatial/vector.ts`; Shell no longer imports
Plate's model module merely for vector arithmetic. Shared MUI controls, scientific
fields, tables and theme tokens remain the UI owners. No visual redesign is part
of this refactor.

## Review findings and resolution

| Finding | Resolution |
| --- | --- |
| Handwritten frontend results omitted fields and could drift from Python | Generated wire types, derived editor types and CI drift gates |
| Routers imported a private Frame helper; Shell/Plate borrowed sibling contracts | Neutral execution, error and spatial-contract modules |
| Capabilities and 3D errors were incompletely described in OpenAPI | Typed capability responses and explicit shared error envelopes |
| Solid and Plate duplicated persistence/import/undo/request ownership | Reused the shared spatial document hook and tested cancellation races |
| A delayed Frame import could replace a newer document | Import token/revision checks around asynchronous confirmation and file reading |
| Four visited flags and repeated host routing diverged | Centralized navigation/hosting and consistent same-family dimension switching |
| Concurrent UI tests exceeded normal deadlines under heavy worker contention | Limited the default test command to two workers; retained existing deadlines and assertions |

Existing nonlinear state transactions, persistence semantics, API URLs, reference
kernel source and solver equations were retained. Large family-specific editors
remain separate because their topology, DOFs and result conventions differ. The
review does not establish support beyond each integration's documented numerical
scope, nor does it make the desktop workbench a mobile interface.

## Verification

Repository hygiene: current examples and release fixtures have one owner in
`tests/fixtures/`. Standalone study packages, historical reports, unrelated
deliverables and obsolete build output are archived outside the application
checkout. `Step 2 Math Core` and its verification resources remain runtime
dependencies. TypeScript checks unused locals and parameters during normal builds;
the retired workflow bar and unreferenced meshing helper have been removed.

- Backend regression: 416 tests passed, including numerical regressions, source
  provenance, API error/limit handling and generated-contract checks.
- Frontend regression: 197 tests across 36 files passed in the full suite,
  including document-lifecycle races and four-family dimension round trips.
  TypeScript and production build pass.
- Real HTTP: all four nonlinear asynchronous analyses and all four spatial solves
  completed; spatial schema round trips and numerical checks passed.
- Real browser: Frame/Solid/Plate/Shell example solves, retained results during
  family navigation, Shell dimension round trip, and Solid missing-support error
  → Undo → successful solve. Keyboard result selection worked without console errors.
- 1024 × 768 browser check: existing 1120 px desktop floor retained with document
  horizontal scrolling; result controls and tables retained their layout.
- Math Core audit and release evidence are current; release/OpenAPI checks, Ruff
  and strict UI audit pass. The built wheel includes the shared modules and all
  spatial reference packages; imports and all four spatial solves also passed
  using the extracted wheel rather than the source tree.

See [interface alignment](INTERFACE_ALIGNMENT.md), [UX contract](UX-CONTRACT.md),
and each family integration document for the detailed behavior and numerical limits.
