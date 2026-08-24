# P1 Data Contract

## 1. Status and boundary

P1 freezes the first public input, analysis-option, output, and validation contracts for
`nonlinear-core`.

Schema version: `1.0.0`.

P1 does not implement element matrices, residual assembly, Newton iteration, material updates, or
result recovery. The contracts describe the information those later phases must consume and
produce.

## 2. Canonical public entry points

```python
from nonlinear_core import (
    canonical_model_json,
    validate_model_input,
    validate_model_json,
)
```

Use `validate_model_input()` or `validate_model_json()` as the complete validation boundary.
Calling `ModelInput.model_validate()` directly checks structure but intentionally does not perform
duplicate-ID or cross-entity-reference validation.

## 3. ModelInput topology

| Field | Required | Purpose |
|---|---:|---|
| `schema_version` | yes | Must equal `1.0.0` |
| `model_id` | yes | Stable model identifier |
| `name` | yes | Human-readable model name |
| `model_family` | yes | `continuum`, `frame`, `plate`, or `shell` |
| `units` | yes | Declared unit metadata; no conversion |
| `nodes` | yes | Ordered node array |
| `elements` | yes | Ordered connectivity and formulation array |
| `materials` | yes | Ordered material-model array |
| `loads` | no | Ordered nodal, element, body, edge, or surface loads |
| `constraints` | no | Ordered prescribed DOFs |
| `analysis` | yes | Nonlinear control and convergence settings |
| `extensions` | no | Explicit project-specific JSON values |

Unknown fields are rejected at every contract level. New or adapter-specific data must be placed in
an explicit `properties`, `parameters`, or `extensions` object.

## 4. Identifier and reference rules

- IDs are non-empty strings and are unique inside each entity collection.
- Element `node_ids` must reference existing nodes and cannot repeat inside one element.
- Element `material_id` must reference an existing material.
- Nodal loads require an existing `node_id`.
- Element, edge, and surface loads require an existing `element_id`.
- Body loads apply to the model and cannot carry a node or element target.
- Constraint node references must exist.
- A node/DOF target cannot be constrained twice.
- Displacement-control targets must reference an existing compatible node/DOF.

## 5. Deterministic DOF order

Input entity arrays preserve their submitted order. Global DOFs use node-major ordering and the
following fixed family order:

| Family | DOF order per node |
|---|---|
| Continuum | `UX, UY` |
| Frame | `UX, UY, RZ` |
| Plate (linear/default) | `UZ, RX, RY` |
| Plate (`von-karman` formulation) | `UX, UY, UZ, RX, RY` |
| Shell | `UX, UY, UZ, RX, RY, RZ` |

`ModelInput.ordered_dof_refs()` returns the complete order.
`ModelInput.free_dof_refs()` removes prescribed targets without reordering the remaining DOFs.
The P13 Plate extension is selected explicitly by formulation; it does not change the frozen
linear Plate order or reinterpret existing P2 inputs.

Nodal-load component names use these same generalized DOF names. Their values are conjugate nodal
forces or moments in the declared coordinate system.

## 6. Units

`UnitMetadata` requires length, force, and stress labels. Angle defaults to `rad`; time and a system
label are optional.

The contract layer records unit text exactly as supplied. It does not convert geometry, stiffness,
force, displacement, stress, or material parameters. Every adapter and example must use one
self-consistent unit system.

## 7. AnalysisOptions

`AnalysisOptions` contains:

- `control_method`: load, displacement, or arc length;
- `newton_method`: full or modified Newton;
- `max_iterations`;
- residual, displacement, energy, and linear-solver tolerances;
- force, displacement, and energy floors;
- initial, minimum, and maximum step sizes;
- maximum steps, retries, target iterations, cutback, and growth factors;
- optional line-search settings;
- displacement-control target and increment when selected;
- spherical arc-length radius, bounds, beta, and root-selection rule when selected.

Control-specific objects are required only for the selected control method. Supplying irrelevant
control objects is rejected so stale settings cannot silently affect a later analysis.

## 8. Structured validation errors

Every validation failure contains:

```text
code       stable machine-facing category
json_path  location beginning at $
message    human-readable detail
```

P1 error codes include:

| Code | Meaning |
|---|---|
| `CONTRACT_INVALID_JSON` | JSON syntax cannot be parsed |
| `CONTRACT_UNKNOWN_FIELD` | Field is not in the frozen contract |
| `CONTRACT_MISSING_FIELD` | Required field is absent |
| `CONTRACT_INVALID_VALUE` | Type, range, enum, or conditional setting is invalid |
| `CONTRACT_DUPLICATE_ID` | Repeated entity identifier |
| `CONTRACT_DUPLICATE_REFERENCE` | Repeated node in one element |
| `CONTRACT_INVALID_REFERENCE` | Node, element, or material target does not exist |
| `CONTRACT_MISSING_TARGET` | Load target required by its kind is absent |
| `CONTRACT_INVALID_TARGET` | Load carries a target forbidden by its kind |
| `CONTRACT_INVALID_DOF` | DOF is incompatible with the model family |
| `CONTRACT_DUPLICATE_CONSTRAINT` | Same node/DOF is prescribed twice |

## 9. Output contracts

P1 defines but does not yet populate:

- `IterationRecord`: norms, accepted alpha, tangent update and diagnostics;
- `FailureRecord`: classified failure and optional step/iteration location;
- `StepResult`: requested/accepted step, state ID, iteration history and response;
- `PostResult`: separate raw and derived result fields;
- `SolveResult`: schema, model hash, solver version, steps, failures and postprocessing.

`SolveResult.schema_version` is always `1.0.0`. Failed solve results require failure evidence.
Derived postprocessing fields require a source description and cannot be stored in `raw_fields`.

## 10. JSON Schema and examples

The checked-in Draft 2020-12 file is:

```text
schemas/model-input-1.0.0.schema.json
```

Regenerate it with:

```bash
python scripts/generate_schema.py
```

The schema handles structure. Semantic checks remain in `validate_model_input()` and are covered by
the valid and invalid fixtures under `examples/contracts/`.
