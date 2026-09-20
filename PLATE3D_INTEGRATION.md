# Spatial Plate integration

The Plate entry in 3D mode opens a separate plate document inside the existing
Nonlinear Studio project. Its frontend and backend are independently organized;
the source guide was archived outside the runtime project during cleanup. Its historical
path, `docs/3D-Plate_Math-Core-Guide`, and kernel hash remain recorded in the provenance.

## Mathematical contract

A00–A05 define arbitrarily oriented **coplanar, constant-thickness isotropic linear
Reissner–Mindlin plate bending**, with Q4 MITC4 covariant assumed shear. Local DOFs
are [w, theta_x, theta_y]; u=-z theta_x, v=-z theta_y, gamma=grad(w)-theta.
The declared plane has origin, orthonormal ex/ey and n=ex×ey. All nodes must lie
within 1e-10 model extent of that plane. Every Q4 mapping checks corners, edge
midpoints and center; integration additionally checks its actual Gauss points.

The full model solves three local unknowns per node in one common frame. Spatial
output is displacement=w*n and rotation=-theta_x*ey+theta_y*ex. Generalized nodal
forces [Fw,Mtheta_x,Mtheta_y] map to force=Fw*n and moment=-Mtheta_x*ey+Mtheta_y*ex.
No artificial six-DOF solve, membrane stiffness, drilling penalty or pseudoinverse
is introduced. Nodal loads and pressures accumulate when repeated in the API.
The UI replaces loads on its chosen target; positive pressure follows +n.

Bending and reconstructed shear use 2×2 quadrature; consistent normal pressure uses
3×3. The constrained system includes -Kfc*dc for nonzero supports. Symmetric diagonal
equilibration precedes an eigenvalue stability check and dense direct solve.
Eigenvalue ratio <=1e-13 is rejected as singular/ill-conditioned. The complete K/F
remain available for reactions R=Kd-F and energy checks. Prescribed reactions only
are reported as support forces; free residuals are separate numerical evidence.

At each of four Gauss points the API returns curvature, reconstructed shear strain,
M=Db*kappa, Q=Ds*gamma and local top/bottom bending stresses ∓6M/t². Stress components
are XX, YY, XY; moment order is Mx, My, Mxy. Full 3D stress, nodal stress smoothing
and transverse thickness stress recovery are not represented. All units are SI:
m, N, Pa, rad, J; M is N·m/m (N), Q is N/m, nodal moments are N·m.

## Backend

- `src/reused_cores/plate3d_linear/reference.py`: byte-identical teaching kernel
  snapshot, pinned by SOURCE_MANIFEST.json with provenance. Runtime never imports docs.
- `src/nonlinear_core/plate3d.py`: strict Pydantic model/result contracts, plane,
  references, topology/mapping validation, assembly, constrained solve, recovery
  and force/moment/energy/residual checks.
- `src/nonlinear_api/plate3d.py`: capabilities, validation, and solve routes using
  the established error envelope, host limits and a single concurrent plate slot.
- `POST /api/v1/plate3d/validate` validates schema, references and coplanar geometry.
  Stability of the constrained system is assessed on solve.
- `POST /api/v1/plate3d/solve` returns a nonempty typed result or actionable 422;
  host size limits return 413 and occupied solve slot returns 429.
- `GET /api/v1/plate3d/capabilities` declares scope, units and limits.

Bounds are 200 nodes / 600 DOFs, 400 elements, 600 constraints, 1,200 nodal loads
and 1,200 pressure records; a stricter host max_dofs wins. Inputs reject unknown
fields, nonfinite values, invalid material/thickness, duplicate/unused nodes,
duplicate cells, conflicting constraints, missing references, non-manifold edges,
flipped/degenerate Q4s, nonorthonormal frames and out-of-plane geometry. Overlap
between distinct coplanar elements is not a general geometric intersection check.

## Frontend

- `frontend/src/plate3d/model.ts`: portable document, oriented rectangle mesh,
  example and defensive local shape checks. Imported documents additionally pass
  the host validator before replacing the current model.
- `PlateWorkbench.tsx`: geometry/material/support/load forms, 50-revision Undo,
  local autosave, JSON open/export, independent Model/Results modes, raw tables.
- `PlateCanvas.tsx`: plate-specific quantity and load adapters.
- `frontend/src/spatial/SurfaceCanvas.tsx`: shared solid/plate projection, camera,
  face/nodal display, selection, load arrows/couple arcs, local/global axes,
  deformed reference and contours.

The 2D Plate document, Frame 3D and Continuum 3D remain independent. Draft fields,
selection and camera survive hidden-workspace navigation. Invalid scientific text
blocks Apply; Run/Save/Results are unavailable until Apply or Cancel. Regeneration
clears supports/loads tied to old topology and has Undo. Changing a model invalidates
results. Switching workspace aborts the browser wait and prevents late responses.
Cancellation does not stop server factorization. Models persist locally; results
are session-local. Browser-storage failure is explicit and export remains available.

Geometry uses rectangular mesh divisions, lengths, global origin, tilt and azimuth.
Other ordered coplanar Q4 meshes can be imported. Mesh node/element tables are
read-only with paged keyboard selection. Supports apply clamped, soft simple, hard
simple or free conditions on local-extreme edges; selected-node supports allow
clamped/soft/free. Hard all-edge conditions preserve both rotations at corners.
Nonzero w is editable; arbitrary nonzero tilt constraints are available in JSON.
Uniform pressure applies to all/selected elements. Nodal loads use local generalized
components. Visual stress/moment values are arithmetic element means; all four
integration points remain available in tables. The |w| contour averages nodal
magnitudes per element and does not interpolate or smooth stress across cells.

## Verification and limits

The default frontend fixture is a 2×1 m cantilever, 8×4 elements, t=0.05 m,
E=210 GPa, nu=0.3, ks=5/6, tilt 25°, azimuth 15°, local X-minimum clamped, q=-1 kPa.
The real browser/API solve gives max |w| ≈8.70533e-4 m, strain energy ≈0.345903 J,
w/t≈0.0174107 and free residual ≈2.89e-12. This is a product smoke case, not an
independent analytic accuracy oracle.

Independent host checks cover an exact twisting patch with free interior nodes and
nonzero prescribed displacements, recovered moments/stresses, spatial rotation and
translation invariance, force/moment equilibrium, accumulated pressure/nodal loads,
fully constrained models, invalid inputs, resource/busy recovery and source hash.
A hard simply supported unit-square sine load uses independently integrated nodal
forces and W=q/(4D*pi^4)+q/(2S*pi^2); 4/8/12 grids must converge with final error <2% at t/a=0.1, 0.01 and 0.0001.
The source's 18 groups / 59 checks were separately rerun in a temporary copy. These
are reference evidence distinct from host and browser validation.

No geometric/material nonlinearity, membrane effects, noncoplanar plate connections,
curved shells, buckling, dynamics, contact or arbitrary CAD meshing. High distortion,
extreme thickness/condition number and point-load singularities require separate
convergence assessment. A w/t>0.2 warning is a review trigger, not a validated universal
small-deflection criterion; smaller w/t is not proof of accuracy. The module is a
bounded implementation with the listed numerical evidence, not certification.


### Current acceptance record (2026-09-20)

- Backend: 382 tests passed, including 20 dedicated Plate API/numerical cases.
- Frontend: 32 test files / 177 tests passed (`npm --prefix frontend test -- --maxWorkers=2`); two workers avoid concurrent UI-test CPU timeouts.
- Source reference: 18/18 groups, 59 checks, executed in a temporary copy.
- Math-core audit: passed; existing evidence is current.
- TypeScript typecheck and production build: passed.
- Python lint and strict UI audit: passed. DESIGN.md lint has zero errors and nine
  pre-existing unused-token warnings; theme.ts remains the runtime token owner.
- Browser: real plate solve, solid solve regression, raw moments table, contour
  selector with keyboard, invalid exponent preservation across workspace changes,
  Cancel, mesh regeneration, singular-model failure, Undo/retry recovery, and
  900×650 horizontal navigation to all controls were inspected. Browser error log
  was empty. The final build was reopened and its result view visually inspected.
