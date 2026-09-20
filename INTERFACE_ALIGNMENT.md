# Mathematical core and frontend interface alignment

Original audit: 2026-09-15. Whole-project follow-up: 2026-09-20.

The [architecture review](ARCHITECTURE.md) extends this alignment to all four
spatial workspaces. Python/OpenAPI now generates frontend wire contracts, spatial
capabilities and error envelopes are explicit, shared execution/document lifecycle
code has neutral ownership, and CI rejects contract drift. The 2D nonlinear and
reference-operation conventions below remain in force.

## Scope

The four **2D nonlinear** structural workspaces (Frame, Continuum, Plate, Shell) use the existing
`/api/v1/analyses` API. The four independent Step 2 reference cores expose 18 operations
through `/api/v1/math-cores`. These remain separate workflows with their original
numerical conventions and state ownership.

## Corrections

| Area | Previous mismatch | Corrected behavior |
| --- | --- | --- |
| Operation parameters | Required/optional names duplicated in metadata and handlers | `OperationSpec` owns names; dispatch validates once; registry checks handlers and examples |
| Request contracts | Python dataclass requests bypassed validation; Python and HTTP accepted different envelope fields | Both Python entry forms validate identifiers, request IDs, schema version and extra fields; frontend accepts optional parameters and null request IDs like HTTP |
| Numerical JSON | Nonfinite NumPy values bypassed recursive serialization | Reject nonfinite parameters; serialize nonfinite diagnostic values as JSON null recursively |
| Math Core results | A pending result could appear after editing/resetting/switching input | Invalidate and abort the old browser request; only the current request can populate the result |
| Parameter editor | Only JSON syntax/object shape checked | Use server-owned required/optional names, depth/value limits and finite-number validation |
| Analysis input | Empty or incomplete numbers could become zero/fallback values; step counts silently rounded | Shared ScientificField retains raw drafts and validates finite numbers, ranges and integer counts |
| Displacement control | A loaded but constrained DOF could be selected automatically | Select only existing unconstrained family DOFs |
| Arc length | Unused common step-size fields remained editable | Use arc radius bounds; retain common retry/growth/iteration controls |
| Hidden settings | Maximum step, growth/iteration controls, linear-solver tolerance and normalization floors lacked frontend controls | Expose supported settings in existing disclosures |
| Unsupported line search | Orthogonality could be submitted but structural responses lacked conservative metadata | Disable that option and reject enabled requests before queueing; preserve the direct-core conservative algorithm |
| Draft lifecycle | Closing settings discarded raw intermediate field text | Lazily mount settings on first use and retain fields across close/reopen |

## Control mapping

| Control | Run request | Initial/minimum/maximum size | Line search |
| --- | --- | --- | --- |
| Load | `target_load_factor` | `step_control.initial_step/min_step/max_step` | Optional backtracking |
| Displacement | `number_of_steps` | Signed `displacement_control.increment`; bounds scale by `min_step/initial_step` and `max_step/initial_step` | Optional backtracking |
| Arc length | `number_of_steps` | `arc_length.radius/min_radius/max_radius` | Unavailable |

Full and modified Newton retain the existing solver implementations. HTTP 200 Math Core
execution errors remain errors. Aborting a reference request stops browser waiting; it does
not promise cancellation of the server calculation.

## Verification

- Every published operation example executed through the HTTP catalog/detail/execute flow.
  Missing required and unknown parameters checked against every operation.
- Four structural families × three control methods checked for the correct run-request field.
- Regression coverage includes response invalidation, HTTP 200 errors, numeric drafts,
  constrained DOFs, input bounds, serialization and unsupported line-search rejection.
- Browser at 1120 × 800: material update completed; missing parameters blocked; incomplete
  exponent retained across settings close/reopen and blocked Apply; unsupported orthogonality
  disabled; backtracking Frame analysis completed at step 2 and load factor 0.1.
- No solver equations, element formulations, material laws or residual conventions changed.

Final checks: backend and unified-interface tests **234 passed, 22 subtests passed**;
frontend **137 tests passed across 25 files**; TypeScript/Vite production build passed;
Ruff, current mathematical audit evidence, strict UI audit and whitespace checks passed.
