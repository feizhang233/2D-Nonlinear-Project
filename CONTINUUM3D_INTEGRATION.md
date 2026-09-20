# Continuum 3D integration

The dimension control immediately left of **Frame** selects independent 2D and 3D
documents. In 3D, all four families are enabled. Plate and Shell have their own contracts in
PLATE3D_INTEGRATION.md and SHELL3D_INTEGRATION.md. The projected nonlinear Shell workspace remains a 2D-mode document;
it is not advertised as a full spatial shell editor. The former fifth Frame 3D tab
is represented by Frame in 3D mode. Existing Frame 3D files and storage keys survive.

## Source and mathematical scope

`docs/3D-continuum/` contained CONTENT_INDEX.md and AI_CONTENT_INDEX.json only. Their
linked algorithm and verification files were resolved in the local sibling package
`FEA Document/3D-Continuum_Math-Core-Guide`. The unmodified reference kernel is pinned
in `src/reused_cores/continuum3d_linear/reference.py`; PROVENANCE.md and
SOURCE_MANIFEST.json record the source and SHA-256. Runtime never imports docs or
another repository. The original package remains unchanged.

This implementation covers **small-strain isotropic linear static elasticity**,
Tet4 and full-integration Hex8. Each node has UX/UY/UZ, with engineering strain order
XX/YY/ZZ/XY/YZ/ZX. Jacobian rows are physical coordinates and columns are natural
coordinates. Reactions use Ku−F. Product inputs and results use **m, N, Pa, J**.
The source's alternative recommended N–mm–MPa convention is not an implicit conversion.

## Backend

- `src/nonlinear_core/continuum3d.py`: strict model/result schemas, topology and
  material validation, element assembly, consistent body/face loads, prescribed
  translations including nonzero settlements, constrained solve, and point recovery.
- `src/nonlinear_api/continuum3d.py`: bounded host routes and shared API error envelope.
- `POST /api/v1/continuum3d/validate`: structural schema and reference validation
  for import. Geometry quality and stiffness stability are checked during solve.
- `POST /api/v1/continuum3d/solve`: complete nonempty solve with displacements,
  reactions, original integration-point strains, stresses, principal stresses,
  von Mises values, volume, energy, free residual, force/moment and energy checks.
- `GET /api/v1/continuum3d/capabilities`: element types, units and resource limits.

The service permits 200 nodes / 600 DOFs and 1,200 elements; a stricter host DOF
limit wins. One solid solve runs per process; concurrent solid requests return 429.
Hex8 always uses 2×2×2 integration, Tet4 uses its exact constant-strain centroid rule.
Face loads require exposed element faces and use consistent integration, including
nonrectangular quadrilateral faces. Face IDs are zero-based local faces in `FACES`;
connectivity follows the source package's node order. Vector traction is not an
automatically oriented pressure. Repeated nodal or face loads accumulate in the API.
No pseudoinverse hides unrestrained or disconnected models. Cancellation stops the
client's wait and suppresses stale responses; it cannot interrupt a running factorization.

## Frontend

`frontend/src/continuum3d/` separates the portable model/mesh helpers, projected 3D
canvas and workbench. The application reuses WorkspaceSwitcher, the MUI theme,
ScientificField, the spatial DataTable and browser-storage helpers.

- Geometry creates structured blocks with editable dimensions and subdivisions,
  either Hex8 or a conforming six-Tet4 subdivision of each brick.
- Imported solid JSON supports other valid Tet4/Hex8 topologies and multiple materials.
- Materials can be added, edited and assigned to a selected element or all elements.
- Supports prescribe any translation on a coordinate-extreme face or selected node.
- Loads support boundary vector traction, selected-node force and uniform body force.
- The view supports orbit, pan, fit, zoom, principal planes, node/element selection,
  deformed mesh and displacement/stress contours. Tables provide a keyboard-accessible
  selection alternative and exact displacement/reaction/raw stress evidence.
- Contour stress is explicitly labelled as the arithmetic element mean; it never
  replaces the original integration-point values returned by the API.
- Edits invalidate results, autosave the model locally, and support 50-step undo/redo.
  Save project downloads model JSON. Numerical results are session-local; rerun after
  reopening a file. Storage failure stays visible. Account archives are unchanged.
- Unfinished property input survives switching modules or dimension. Run/Save/Results
  are disabled until Apply or Cancel. Moving between property categories requires
  applying or cancelling the active draft; dimensional navigation preserves it.
- Regeneration explicitly clears supports/loads tied to the old mesh and retains the
  first material. Undo restores the entire prior model. Imported models are validated
  before replacement; failed import preserves the current document.

## Validation and remaining limits

The actual frontend-generated Hex8 and Tet4 examples are committed as API fixtures.
The uniaxial specimen is 2×1×1 m with roller planes UX=0 at X=0, UY=0 at Y=0,
UZ=0 at Z=0. A 1 MPa X traction with E=200 GPa and nu=0.3 gives
UX=5e−6 X, UY=−1.5e−6 Y, UZ=−1.5e−6 Z, energy 5 J and X reaction −1 MN.
Product tests use 1e−14 m displacement tolerance and 1e−4 Pa stress tolerance.

Dedicated checks include nonzero prescribed displacement/free coupling, free internal
nodes, force and moment balance, affine skew-element patches, six rigid modes,
body/nodal loads, invalid topology/material/mapping, busy recovery and model limits.
A manufactured u=(.001 X²,0,0) Hex8 problem with nonzero body force and exact boundary
displacements uses 2³ and 4³ meshes with free internal nodes; displacement L2 error
decreases by 4 and energy-norm error by 2 (relative tolerance 1e−7).

The source's 19 verification groups / 152 checks were independently rerun in a
temporary copy, not by modifying the source package. These remain reference evidence,
distinct from the host tests and browser acceptance. V16 is a material diagnostic;
V18 is beam arithmetic and does not validate a solid bending mesh.

No nonlinear geometry/materials, contact, dynamics, buckling, mixed incompressibility,
high-order elements, reduced integration or automatic arbitrary-volume CAD meshing
are implemented. Tet4 and full-integration Hex8 can lock in bending or near
incompressibility. Sampled Jacobian tests are not a proof of validity everywhere in
warped elements. General distorted-mesh convergence and external solver comparison
remain separate work. The module is not a production certification claim.

Run the host tests, frontend tests, build and lint using README's existing commands.
OpenAPI is generated with `scripts/generate_openapi.py`.
