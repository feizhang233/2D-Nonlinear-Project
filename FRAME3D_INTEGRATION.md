# Frame 3D integration

The **Frame 3D** workspace adds the space-frame modeling workflow from the local
`2D-Frame-Project` to Nonlinear Studio. Select 3D in the dimension control left of
Frame, then choose Frame. The four 2D documents, Frame 3D and Continuum 3D remain
independent; switching does not convert or merge models. See CONTINUUM3D_INTEGRATION.md.

## Workflow

1. Project → New 3D model, or start with the included space-frame example.
2. Choose XY, XZ or YZ and the plane offset. Draw a member, or use exact XYZ coordinates
   in Properties. Split view links the working plane and rotating orthographic view.
3. Select nodes or members in the navigator, canvas or tables. Materials, Sections,
   Supports and Loads open their corresponding property forms. Material and section
   assignments never overwrite each other. Loads use kN/kN·m; the API uses SI units.
4. Apply properties, then Run analysis. Results include deformation, reactions, local
   end actions, N/Vy/Vz/T/My/Mz, optional section normal stress, and numerical checks.
5. Save project downloads portable 3D JSON. Edits also persist in this browser. Undo/Redo
   retains 50 edits; modification clears old numerical results. Local JSON persistence
   is separate from the existing nonlinear account/archive/restart system.

Small desktop widths retain the existing 1120 px scrollable workbench floor. The
properties pane becomes a bounded drawer below 1050 px. Controls use the existing
MUI theme and numeric field component; no second theme or extra frontend server exists.

## Mathematical and API boundaries

`src/reused_cores/frame3d_linear/` is a self-contained reference-core snapshot, with a
source hash manifest and provenance. It includes assembly, local axes, EB and bounded
Timoshenko stiffness, rotational releases, loads, solve, recovery and validation.
It does not import files from the sibling checkout at runtime.

The existing FastAPI application registers:

- `POST /api/v1/3d/solve`: complete linear-static request and result.
- `POST /api/v1/3d/plots/{component}`: six optional PNG diagrams.
- `GET /api/v1/3d/capabilities`: scope and host resource limits.

Errors use Nonlinear Studio's existing `{error: {code, message, ...}}` envelope.
The host permits 600 DOFs (100 nodes), 400 members, and 1,000,000 sampled field values;
a smaller configured host DOF limit takes precedence. One dense 3D solve runs per
process at a time; a concurrent request returns 429. The request-body size guard is
shared with the other API routes. Client cancellation prevents stale display but does
not interrupt a factorization already executing on the server.

The scope is linear elastic, small displacement/rotation, straight prismatic beams.
Timoshenko members support nodal loading only. Nonlinear geometry/materials, buckling,
dynamics and restrained warping are not implemented by this space-frame extension.
The existing four nonlinear solvers and their request formats remain available.

## Verification

Dedicated numerical tests use beam closed solutions, energy/virtual-work integration,
rigid motions, releases, settlements, distributed loads, equilibrium and comparison
with the existing planar frame core. Host API tests cover real nonempty solves,
invalid/unstable models, sampling and DOF limits, busy recovery and all six PNG plots.
Frontend tests cover work-plane projection, true versus skew intersections, splitting,
independent property assignment, import, undo, workspace preservation, request errors,
cancellation and an actual frontend-generated model sent through the host API.

Browser acceptance created a 3 m cantilever from an empty document, assigned its fixed
end and Fz = -10 kN at the tip, and recovered W = -5.14492 mm, agreeing with
-PL³/(3EIy), using E = 210 GPa and Iy = 8.33e-5 m⁴. The space-frame example returned
maximum translation 0.901686 mm with equilibrium and energy checks passing. Desktop
1120 px and 900 px drawer layouts and an invalid negative material input were inspected.

Run:

```sh
MPLCONFIGDIR=/tmp/nonlinear-mpl XDG_CACHE_HOME=/tmp/nonlinear-cache .venv/bin/python -m pytest tests
.venv/bin/ruff check src tests
npm --prefix frontend test
npm --prefix frontend run build
```
