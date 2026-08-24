<div align="center">

# Nonlinear Studio / nonlinear-core

**A contract-first foundation for quasi-static nonlinear analysis across 2D finite-element models.**

Python 3.11+ numerical core · FastAPI service · React + Material UI workbench

</div>

---

## Project status

**P15 / `nonlinear-core 0.1.0` release gates complete:** V00-V08, all four V09 families, the four
unchanged linear-core references, API execution, and the four-family Material UI flow are
automated. Checked-in release evidence retains one successful five-step nonlinear solve and one
expected limit-point failure with the complete input, result, iteration history, model hash,
solver version, rejected step, and rollback boundary. Ruff, the complete backend and frontend test
suites, TypeScript, production builds, deterministic Schema/OpenAPI checks, a clean wheel install,
and a real HTTP frontend/API smoke are release gates. Supported claims remain bounded by family
below.

Development is governed by the staged
[`2D-Nonlinear-Project_逐步开发计划.md`](2D-Nonlinear-Project_逐步开发计划.md) and the
canonical mathematics in
[`核心算法与实现顺序.md`](2D-Nonlinear-Project_Math-Core-Guide/01_核心算法/核心算法与实现顺序.md).

For a concise, interview-oriented Chinese introduction, start with
[`博士面试准备/README.md`](博士面试准备/README.md). It reorganizes the existing mathematics,
verification evidence, and limitations into a short learning path without moving the engineering
files.

## Verified 0.1.0 support

The release provides one shared quasi-static nonlinear solution layer for four existing
finite-element families:

| Family | Verified nonlinear slice | Explicit boundary |
|---|---|---|
| Frame | 2-node corotational Euler-Bernoulli | Large rigid rotation, small strain; fixed nodal and reference-local distributed loads |
| Continuum | Total Lagrangian plane-strain Q4 with Saint-Venant--Kirchhoff elasticity | Fixed nodal/edge loads; no plane stress, mixed formulation, plasticity, or contact |
| Plate | Q4 von Karman membrane with MITC4 transverse response | Fixed nodal/surface/edge loads; moderate rotation/small strain |
| Shell | 6-DOF corotational flat Q4 with QLLL shear and visible drilling | Fixed nodal/surface/edge loads; initially flat; no general curved shell |

The four sibling projects remain reusable linear baselines and their frozen reference results are
regressed independently. The browser workbench loads, edits, validates, solves, and renders the
verified Frame, Continuum, Plate, and Shell slices through the same P10 API. Surface families use
a labeled Q4 engineering projection; it is not presented as a general-purpose 3D shell viewer.
Their model inspector can regenerate the finite-element mesh with Gmsh from the current exterior
boundary and preserve supported boundary constraints and loads by geometric rebinding.
Users can rename model entities without changing solver-facing IDs. Guest mode keeps the complete
modeling, meshing, solve, import, and export workflow available immediately; an optional account
adds private, owner-isolated model history.

## Release capabilities

- Full Newton-Raphson and optional modified Newton
- Load control and displacement control
- Line search, adaptive step sizing, cutback, and retry
- Basic spherical arc-length path following
- Trial, commit, rollback, and restart-safe state management
- Iteration history, failure diagnostics, reactions, and load-displacement paths
- Geometrically nonlinear Frame, Continuum, Plate, and flat-Shell examples
- FastAPI analysis endpoints and a React/TypeScript workbench
- Guest-first IAM with server-side sessions and private saved-model history (24 snapshots per user)
- User-defined display names for models, materials, supports, loads, nodes, and elements
- Synchronous calls plus local in-process asynchronous polling and cooperative cancellation
- Versioned model/restart JSON import and export, including arc-length continuation direction
- Live step/iteration progress and result provenance
- Gmsh-backed all-Q4 remeshing for Continuum, Plate, and flat Shell models
- Consistent distributed-load conversion for Frame members and Q4 edges/surfaces

## Mathematical contract

The project uses one residual and Newton sign convention throughout:

$$
\mathbf r=\mathbf f_{ext}-\mathbf f_{int},
$$

$$
\mathbf K_t=
\frac{\partial\mathbf f_{int}}{\partial\mathbf u}
-\frac{\partial\mathbf f_{ext}}{\partial\mathbf u},
\qquad
\mathbf K_t\,\delta\mathbf u=\mathbf r.
$$

The P2/P3 model-facing evaluation and correction contract is:

```text
evaluate(trial_u, load_factor, committed_state)
    -> internal_force
    -> tangent
    -> external_force
    -> trial_state
    -> element responses and diagnostics

residual = external_force - internal_force
effective_tangent = tangent - external_tangent
solve effective_tangent_ff * delta_u_f = constrained_rhs_f
```

Committed history must remain immutable during trial iterations. A state is committed only after
global convergence, and every rejected step is rolled back.

## Development setup

The backend baseline is Python 3.11 or newer. Pydantic freezes the public data contract, NumPy owns
the unified response arrays, and jsonschema independently verifies the checked-in Draft 2020-12
Schema. The four linear cores are declared in the `linear-cores` optional dependency group; in this
multi-repository workspace they can be installed directly from the sibling directories.

```bash
python -m pip install -e '.[dev]'
python -m pip install --no-deps -e ../2D-Continuum -e ../2D-Frame-Project \
  -e ../2D-Plate-Project -e ../2D-Shell-Project
python -m pytest
python -m ruff check src tests scripts
python scripts/generate_schema.py
python scripts/generate_openapi.py
python scripts/run_math_core_audit.py --check
python scripts/generate_release_evidence.py --check
python scripts/check_release.py
python -m build --no-isolation
```

Start the P10 service and open its interactive API documentation:

```bash
nonlinear-api
# http://127.0.0.1:8000/docs
```

IAM uses an HttpOnly session cookie. Accounts and saved model snapshots are stored in SQLite at
`frontend/.nonlinear-data/nonlinear-studio.sqlite3` by default; set `NONLINEAR_DATA_DIR` to choose
a different persistent directory. Set `NONLINEAR_COOKIE_SECURE=1` when HTTPS is terminated outside
the application process.

Start the P11 frontend in a second terminal:

```bash
cd frontend
npm install
npm run dev
# http://127.0.0.1:5173
```

Validate the bundled minimal model:

```python
import json
from pathlib import Path

from nonlinear_core import canonical_model_json, validate_model_input

document = json.loads(Path("examples/contracts/valid-minimal-frame.json").read_text())
validation = validate_model_input(document)

if validation.valid and validation.model is not None:
    print(canonical_model_json(validation.model))
else:
    for error in validation.errors:
        print(error.code, error.json_path, error.message)
```

## Current layout

```text
2D-Nonlinear-Project/
├── src/nonlinear_core/          # Contracts, solvers, state, adapters, and P9/P12-P14 elements
├── src/nonlinear_api/           # P10 schemas, limits, status store, service, and ASGI app
├── src/reused_cores/            # Isolated, provenance-tracked reusable linear Frame subset
├── frontend/                    # P11 React/TypeScript/Material UI workbench
├── tests/unit/                  # Contract, algebra, solver, state, and convergence tests
├── tests/verification/          # V00-V09 numerical verification tests
├── tests/integration/           # Cross-layer and adapter tests
├── tests/regression/            # Frozen behavior and result baselines
├── examples/contracts/          # Valid and intentionally invalid P1 fixtures
├── examples/adapters/           # Four P2 models and frozen native references
├── examples/p9/                 # Shallow-arch and imperfect-column nonlinear Frame models
├── examples/p12/                # Plane-strain TL Q4 continuum example
├── examples/p13/                # von Karman Q4/MITC4 Plate example
├── examples/p14/                # corotational Q4/QLLL flat-Shell example
├── examples/p15/                # self-contained success and expected-failure release evidence
├── schemas/                     # Checked-in ModelInput JSON Schema
├── scripts/                     # Contract generation, release evidence, and wheel smoke gates
├── docs/                        # Project-facing technical documentation
├── .github/workflows/           # Frozen-core backend and frontend CI gates
├── 2D-Nonlinear-Project_Math-Core-Guide/
└── 2D-Nonlinear-Project_逐步开发计划.md
```

## Current limitations

The 0.1.0 release does not contain:

- general curved-shell, arbitrary finite-local-rotation, finite-strain, follower-load, composite,
  plastic, damage, or history-dependent Shell formulations;
- arbitrary finite-rotation plates, finite membrane strain, follower Plate loading, or Plate
  branch switching;
- finite-strain plane stress, mixed/near-incompressible continuum, reduced integration, or
  hourglass control;
- shear-deformable, finite-strain, plastic, or damage-capable Frame elements;
- follower or current-configuration distributed loading; all current distributed loads are fixed
  to the reference geometry/direction;
- Gmsh domains with holes, multiple exterior loops, non-planar Shell geometry, or residual
  triangular cells after recombination;
- a durable analysis task queue or a persistent analysis-result store (only account-owned model
  snapshots are persisted);
- multi-process analysis-record sharing or recovery of queued jobs after process shutdown.

The release also excludes contact and friction, dynamics, production plasticity/damage
libraries, fracture and localization regularization, automatic branch switching, general curved
nonlinear shells, multiparameter non-proportional loading, and industrial parallel solving.

See
[`算法局限与适用边界.md`](2D-Nonlinear-Project_Math-Core-Guide/02_算法局限/算法局限与适用边界.md)
for the numerical boundaries that later implementations must preserve.
