# CAD geometry and first-click loads — 2026-09-07

Implemented the requested drawing and loading workflow in the existing workbench.

## User workflow

- **Load → first canvas click**: a node creates a point load; a Frame member or an exposed
  surface-element edge creates a line load. New load in the model list uses the same flow.
  No default node is assigned before the click. The placement selector can explicitly choose
  Point, Line, or Plate/Shell Surface. Incompatible targets leave placement active with feedback.
- Frame line intensities use local qx/qy in force/length. Surface boundary intensities use global
  components in force/length. Decimal and scientific notation remain supported. Pick location on
  canvas keeps the number and intensity when relocating an existing load of the same kind.
- **Outline**: click successive corners, optionally hold Shift for an aligned edge, or enter
  exact X/Y. Use Undo vertex, Close outline, or Cancel outline. Closing a new outline replaces
  the previous domain, holes, supports and loads as stated beside the tool. Global Cancel restores
  the committed model. Materials and sections are retained.
- **Hole**: choose Circle (radius), Rectangle (width and height), or Square (side length), then
  click its center. Select a hole to edit Center X/Y and dimensions, then Update hole.
  Existing polygon holes retain individual-vertex editing.
- **Mesh** regenerates the domain after geometry changes. Pending geometry hides the old FE
  topology. Gmsh builds circular holes from true arcs; first-order Q4 edges approximate those arcs
  with straight chords. Frame distributed loads retain the existing fixed-reference convention.

## Connection and geometry fixes

The load placement helper is shared by canvas, model-list and inspector entry points. It binds to
actual nodes, members and exposed Q4 edges; generated CAD boundaries include all their edge
segments. A non-coincident geometry vertex no longer silently maps to the nearest remote node.
Changing load kind waits for another target click instead of picking the first entity.

Parameterized hole data survives geometry serialization, project export and remeshing. Frontend
and server reject invalid dimensions, crossed/collapsed outlines and holes outside/touching or
intersecting the domain. Native meshing is preceded by server validation. Circle construction
centers are removed from the FE node list, preventing unconnected degrees of freedom. Generated
boundary ownership uses native CAD curve membership and parameters instead of nearest chord
classification. Concave and triangular outlines use the general Q4 meshing path.

## Verification

- Frontend: **113 tests passed**; TypeScript and production build passed.
- Backend: **220 tests passed**; Ruff checks passed for the changed Python files.
- Strict UI audit: **0 findings**. Official DESIGN.md lint: **0 errors**, nine pre-existing
  token-reference warnings. Git whitespace check passed.
- Native mesher tests cover an L-shaped outline with circle, rectangle and square holes, genuine
  circular boundary coordinates, closed/ordered boundary segment chains, no orphan construction
  nodes, invalid geometry rejection and integrated line-force resultants.
- Browser: Frame first-click member loading, scientific intensity and relocation; load cancellation;
  exact-coordinate L outline; hole-specific inputs; out-of-domain rejection; circle positioning;
  **302 nodes / 262 Q4 elements** at mesh size 0.25; line load on **Boundary 2, length 2 m**;
  supports and line load retained after remeshing at 0.4; successful **four-step Continuum solve,
  final load factor 1**.
- Plate uses the same geometry form. At **1120 × 800**, the shape popup and trigger are both
  **191 px**, with no document overflow beyond the supported width.

Local frontend remains at http://127.0.0.1:5173/ and the updated API at http://127.0.0.1:8000/.
Verification outputs are `/tmp/cad-load-tests.json`, `/tmp/cad-backend-tests.log`,
`/tmp/cad-build.log`, `/tmp/cad-ui-audit.json`, and `/tmp/cad-design-lint.json`.
