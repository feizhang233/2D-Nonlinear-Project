# Spatial Shell integration

The **3D → Shell** workspace is an independent linear flat-facet shell document
inside Nonlinear Studio. It implements the **L** baseline of the supplied
`docs/3D-Shell_Math-Core-Guide`; N/I chapters remain extension references. The
original guide files were archived unchanged outside the runtime project during cleanup;
the historical source path and vendored kernel hashes remain recorded in the provenance.

## Mathematical contract

- Planar, convex, consistently oriented Q4 facets in global XYZ. Neighbouring facets
  may have different normals and share six global nodal DOFs: UX/UY/UZ/RX/RY/RZ.
- Isotropic linear elasticity, constant thickness, plane stress, Q4 membrane and
  Reissner–Mindlin bending with QLLL assumed shear; all terms use 2×2 integration.
- Local director tilts are `theta_x = -ey · omega`, `theta_y = ex · omega`;
  `a_local = T a_global` and `K_global = Tᵀ K_local T + K_drilling`.
- `epsilon(z) = epsilon_m - z*kappa`, with `M = -integral(z*sigma)`.
  Top/bottom stresses use `z = ±t/2`. N is N/m, M is N·m/m (= N), Q is N/m.
- Continuum-consistent drilling penalizes `omega_z - (v,x - u,y)/2`; default
  alpha_d = 1e-4, allowed host range 1e-6 to 1e-2. It preserves rigid rotations.
- Global nodal forces and moments accumulate. Signed pressure becomes consistent
  dead traction along each undeformed right-hand facet normal. No follower load.
- Exact partitioning handles prescribed nonzero motion. A diagonally equilibrated
  direct solve rejects singular/ill-conditioned free systems (relative eigenvalue
  threshold 1e-13); no pseudo-inverse or artificial support is inserted.
- Reactions use Kd−f. Force/moment equilibrium is checked about the model centroid,
  with moments scaled by characteristic length. Energy includes prescribed-motion
  reaction work and is compared with recovered membrane/bending/shear/drilling energy.

Each Q4 uses the core's explicit `strict_flat_q4_v1` tolerances (warp warning 1e-10,
rejection above 1e-8 relative to characteristic length), plus positive corner
Jacobians. These are this implementation's geometry policy, not universal shell
accuracy thresholds. Duplicate cells, inconsistent shared edges, non-manifold
edges, unused nodes and conflicting constraints are rejected. A folded junction
shares rotations; it is a continuous connection, not an automatic hinge.

## Backend

| Responsibility | Owner |
| --- | --- |
| Frozen element core and packaged schema | `src/reused_cores/shell3d_linear/` |
| Host document, assembly bridge, bounded solve, raw recovery | `src/nonlinear_core/shell3d.py` |
| Capabilities / validate / solve routes | `src/nonlinear_api/shell3d.py` |
| OpenAPI | `schemas/openapi-1.0.0.json` |

The copied shell-core 1.0.0 implementation was verified against the L conventions.
`SOURCE_MANIFEST.json` pins original and packaged hashes; the only transformation
is the import namespace. Runtime does not need the sibling checkout or the optional
installed shell-core. The host uses the frozen core for validation, assembly and
Gauss recovery and NumPy for the equilibrated global solve.

`GET /api/v1/shell3d/capabilities`, `POST /api/v1/shell3d/validate` and
`POST /api/v1/shell3d/solve` use the existing host transport and error envelope.
Limits: 100 nodes / 600 DOFs / 200 elements, with the host DOF limit also enforced
at solve time. One simultaneous shell solve; contention returns 429, host size
limit 413, invalid models 422. Results are finite typed contracts.

## Frontend

| Responsibility | Owner |
| --- | --- |
| Portable shell3d-1 model, flat/folded generator, target selection | `frontend/src/shell3d/model.ts` |
| Modelling and raw-result forms | `frontend/src/shell3d/ShellWorkbench.tsx` |
| Shell quantities, pressure directions and moment visualization | `frontend/src/shell3d/ShellCanvas.tsx` |
| Camera, projection, picking, contour legend | shared `spatial/SurfaceCanvas.tsx` |
| History, local storage, atomic imports, stale-result guards | shared `spatial/useSpatialDocument.ts` |
| Numeric fields, paged tables, family navigation | existing ScientificField / DataTable / WorkspaceSwitcher |

The generator creates an X-directed sheet with an optional crease at half its
developed width. An even transverse division count places nodes exactly on the
crease. Geometry Apply replaces the mesh and clears supports/loads; Undo restores
all of them. Import accepts other valid planar-facet meshes. Generated/imported
node coordinates and element topology are read-only tables.

Supports can target global X minima/maxima, all boundary nodes, or a selected node.
Clamped/pinned/free replaces all restraints on its target; prescribed single DOF
preserves other restraints. Pressure edits replace pressures on the selected
facets; nodal edits replace the selected node's force/moment. Clear operations are
undoable. JSON import validates on the host before changing the active document.

Each spatial workspace remains mounted independently, preserving drafts, camera,
selection and result views. Shell → 2D opens the separate 2D Shell document. Save
exports only the committed portable model; results are session data. History is
bounded to 50 changes. Invalid numeric drafts block Apply, Run and Save. Cancel
restores committed fields. In-flight cancellation ignores late responses; it does
not interrupt server factorization.

All fields use SI units. Raw N/M/Q, strain/curvature, top/bottom stress and reaction
tables preserve the six-degree-of-freedom meaning. Contours use element means;
local components across differently oriented facets are not a global tensor field.
Select a facet to inspect its local basis. Drilling energy is displayed separately,
with a >1% review warning; users can compare alpha_d / 10 and alpha_d × 10.

## Verification and scope

`tests/integration/test_shell3d_api.py` runs actual assembly and solution for:

- The exact frontend folded cantilever fixture: 25 nodes, 16 facets, 150 DOFs;
  energy 0.05638295246675 J and drilling fraction 1.90691758e-5.
- Regular and distorted membrane patches with an unconstrained interior node,
  prescribed-motion work and correctly transformed local stresses.
- Twisting patch, work-conjugate moment signs, top/bottom stresses and zero assumed shear.
- Six rigid-body null modes, symmetry and rank 18 for a free 24-DOF Q4.
- Folded-model rotation/translation covariance and alpha_d = 1e-5 / 1e-4 / 1e-3 sensitivity.
- Simply supported uniform-load square, 2×2 / 4×4 / 8×8 meshes at t/L = .01 and .001,
  convergence toward the thin-plate coefficient 0.00406235; finest error below 3.5%.
- Fully constrained loads, duplicate load accumulation, bad geometry/inputs,
  singular systems, host resource limits, contention and frozen-source hashes.

Frontend tests pin the actual API fixture and cover invalid drafts across navigation,
raw results, invalidation/Undo, geometry replacement, nodal moments, prescribed
DOFs, late-result cancellation, retry and rejected imports. Browser acceptance
uses the real API rather than mocked result data.

Reference formula checks were rerun in a temporary copy: 12/12 groups passed. That
result is deliberately separate from these real solver gates.

This release is **linear small-motion planar-facet shell analysis**. It does not
claim general curved-shell convergence, large rotations, material nonlinearity,
laminate coupling, buckling/post-buckling, contact or dynamics. Mathematical checks
and a small benchmark set do not replace mesh convergence for the user's geometry.

## Delivery checks (2026-09-20)

- Backend: 404 tests passed; 22 dedicated Shell numerical/API cases.
- Frontend: 34 files / 188 tests passed; 11 dedicated Shell model/workbench cases.
- TypeScript/Vite build and Ruff checks passed; OpenAPI regenerated.
- Existing mathematical-reference audit passed with current evidence.
- Strict UI audit: zero findings. DESIGN.md lint: zero errors; nine pre-existing
  orphan-token warnings (theme.ts remains the runtime token owner).
- A built wheel solved the folded fixture from outside the checkout while a test
  import guard blocked the optional `shell_core` package. The legacy 2D adapter's
  optional load helpers are now imported only when that adapter is used; its
  regression tests passed. Packaged schema and all frozen-source hashes verified.
- Real browser at 1280×720 and 900×650: actual folded solve; partial exponent draft
  retention across navigation; cancelled edits; geometry replacement and singular
  error; Undo and successful retry; keyboard table selection; quantity/evidence
  selectors; accessible horizontal overflow; no console errors. Shared camera
  controls sit above coordinate text so narrow canvases do not overlap it.
