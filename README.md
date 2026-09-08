# Nonlinear Studio

A React, FastAPI, and Python finite-element workbench for Frame, Continuum, Plate, and Shell modeling, quasi-static nonlinear analysis, and independent mathematical reference calculations.

### [🚀 Try Nonlinear Studio Online →](https://nonlinear.feizhang233.com)

## Quick start

Requirements: Python 3.11+, Node.js 22+, and npm. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
npm --prefix frontend ci
nonlinear-api
```

In another terminal, run `npm --prefix frontend run dev`. Open the [workbench](http://127.0.0.1:5173) or [API documentation](http://127.0.0.1:8000/docs). On Windows, activate the environment with `.venv\Scripts\Activate.ps1`.

## Application modules

| Module | Use |
| --- | --- |
| Modeling | Edit geometry through the canvas, model tree, and property panels; assign Frame sections, split members, or define surface outlines and holes |
| Materials and boundaries | Set materials, sections or thicknesses, supports, and supported nodal, member, edge, or surface loads |
| Meshing | Use explicit Frame members or generate Q4 surface meshes with Gmsh; remesh after changing surface geometry |
| Analysis | Configure control methods, increments, and tolerances; run, monitor, cancel, or resume from a committed state |
| Results | Inspect deformation, reactions, internal forces/stresses, load–displacement curves, convergence, and failures |
| Projects | Import/export model JSON or save a project with results; sign in for private server-side history |
| Math Core | Select a reference core and operation, load example parameters, execute, and inspect diagnostics |

Workflow: **Select family → Geometry/materials/boundaries → Mesh → Apply → Run → Results → Save**. Edits remain in a draft until Apply; Cancel discards them. Applying changes invalidates old results. Each family keeps its own workspace, and basic modeling and analysis require no account.

## Mathematical structure

The main analysis chain is `ModelInput → ModelAdapter → Nonlinear solver → SolveResult`. Adapters assemble element forces and tangents and recover responses; the shared solver manages equilibrium iterations, increments, and state transactions.

| Family | Formulation | Nodal DOFs | Scope |
| --- | --- | --- | --- |
| Frame | Two-node corotational Euler–Bernoulli | UX, UY, RZ | Large rigid rotation, small strain; no shear deformation |
| Continuum | Total Lagrangian Q4, Saint-Venant–Kirchhoff elasticity | UX, UY | Plane strain |
| Plate | von Kármán Q4 with MITC4 transverse shear | UX, UY, UZ, RX, RY | Moderate rotation, small strain |
| Shell | Corotational flat Q4, Reissner–Mindlin/QLLL, drilling stabilization | UX, UY, UZ, RX, RY, RZ | Initially flat surfaces, small local strain |

The global equilibrium convention is:

$$
\mathbf r=\mathbf f_{ext}-\mathbf f_{int},\qquad
\mathbf K_t=\frac{\partial\mathbf f_{int}}{\partial\mathbf u}-\frac{\partial\mathbf f_{ext}}{\partial\mathbf u},\qquad
\mathbf K_t\Delta\mathbf u=\mathbf r.
$$

Use **load control** for prescribed load increments, **displacement control** for a selected nodal DOF, and **spherical arc length** to follow paths near limit points. Full/modified Newton, line search, adaptive stepping, and cutback are supported. Trials start from the committed baseline; convergence permits commit, while rejected steps roll back.

**Step 2 Math Core** exposes four independent reference toolsets:

| Core ID | Operations cover |
| --- | --- |
| `plate_shell_buckling` | Linear buckling, critical plate loads, initial imperfections |
| `shell_instability` | Critical-point classification, buckling references, Koiter imperfection relations |
| `constitutive_nonlinearity` | Material-point updates, algorithmic tangents, trial states |
| `general_nonlinear_shell` | Shell kinematics, sections, loads, and state primitives |

Open **Math Core** in the toolbar, or use `GET /api/v1/math-cores` and `POST /api/v1/math-cores/execute` with `{core, operation, parameters}`. Check `status`, `error`, and `diagnostics`, even after HTTP success. See the [interface contract](Step%202%20Math%20Core/INTERFACE.md) for Python usage and parameter definitions.

Reference operations preserve their own sign conventions and verification limits. They do not modify the active model or automatically extend the main solver. Main analyses do not currently include contact, dynamics, production plasticity, or general curved shells.

## Data structures

The public model contract is version `1.0.0`, defined with Python Pydantic and corresponding frontend TypeScript types.

| Structure | Fields and relationships |
| --- | --- |
| `ModelInput` | `schema_version`, `model_id`, `name`, `model_family`, `units`, entity collections, `analysis`, and `extensions` |
| Nodes / elements / materials | Nodes store `id` and `coordinates`; elements link `node_ids` and `material_id` with `formulation` and `properties`; materials store `model` and `parameters` |
| Loads / constraints | Loads identify a target and carry `kind` and `components`; constraints use `{id, node_id, dof, value}` |
| `analysis` | Control method, Newton method, tolerances, stepping, line search, and displacement/arc-length options |
| `extensions` | CAD geometry, section libraries, and other extensions; geometry remains separate from generated FE nodes/elements |
| `SolveResult` | Model hash, solver version, status, `steps`, `failures`, and `post_result`; steps contain iterations and responses |
| `AnalysisRecord` | API task ID, status, progress, and `result` or `error` |
| Restart | `committed_state` stores converged displacement, load factor, history, and identity; arc-length restart also retains increment direction |
| `ProjectDocument` | `{studio_project_version, model, workspace}`; workspace contains run options, an optional analysis record, and result-view settings |

Entities reference one another by ID. Validation rejects duplicate IDs, invalid references, and incompatible DOFs. Global vectors follow node order, then family DOF order. Unit labels do not convert values: inputs must use a consistent unit system.

Frontend state is `StudioState.workspaces[ModelFamily] → WorkspaceState`, containing the model, draft, revision, and analysis record. Revision checks prevent stale asynchronous results from replacing newer model state. A project file saves the current workspace; SQLite stores accounts and saved history, while asynchronous jobs live in one API process.

See [model types](src/nonlinear_core/model.py), [result types](src/nonlinear_core/result.py), [API/project types](src/nonlinear_api/schemas.py), and the [JSON Schema](schemas/model-input-1.0.0.schema.json).

## Repository and checks

```text
frontend/src/             Workbench, canvas, editing state, and results
src/nonlinear_api/        HTTP endpoints, meshing, jobs, and account storage
src/nonlinear_core/       Contracts, adapters, elements, solvers, and state
src/reused_cores/         Provenance-tracked linear Frame foundation
Step 2 Math Core/        Reference implementations and unified interface
tests/                   Unit, integration, and numerical verification
schemas/ · scripts/       Public contracts, audit, and release tooling
```

Study guides, reference books, generated reports, and local deliverables are excluded from Git. Runtime code, build/deployment configuration, API documentation, tests, and required fixtures remain versioned.

```bash
python -m pytest
python scripts/run_math_core_audit.py --check
npm --prefix frontend test
npm --prefix frontend run build
```
