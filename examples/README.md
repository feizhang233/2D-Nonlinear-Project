# Examples

Runnable examples will be added with the feature that they verify. Each example must identify its
units, assumptions, control method, reference result, and expected acceptance criteria.

P1 contract fixtures are stored in `contracts/`. `valid-minimal-frame.json` is the canonical
round-trip example; the `invalid-*.json` documents preserve required failure modes and JSON paths.

P2 linear adapter fixtures are stored in `adapters/`. The four `*-linear.json` files are solvable
models for continuum, frame, plate, and shell. `reference-results.json` freezes each original
core's displacement vector, reaction vector, strain energy, package version, and full DOF order.

P9 geometrically nonlinear Frame fixtures are stored in `p9/`. The shallow two-bar arch provides
the load/displacement/arc-length limit-point path; the initially imperfect pin-ended column
provides the full-Newton regression. Both declare SI units, fixed global nodal loading, linear
elastic section properties, and their verification purpose in `extensions`.

P12 finite-deformation continuum fixtures are stored in `p12/`.
`q4-plane-strain-tension.json` is the bounded Total Lagrangian Q4 vertical slice: SI units,
Saint-Venant--Kirchhoff elasticity, plane strain, constant reference thickness, 2x2 integration,
fixed global nodal loading, and raw Gauss-point stress recovery.

P13 nonlinear Plate fixtures are stored in `p13/`. `von-karman-mitc4-plate.json` uses the
five-DOF Q4 von Karman/MITC4 contract and retains separate membrane, bending, and shear results.

P14 nonlinear Shell fixtures are stored in `p14/`. `corotational-flat-shell.json` is the bounded
large-rigid-rotation/small-local-strain Q4/QLLL slice with explicit drilling stabilization and raw
Gauss-point `N/M/Q`.

P15 release evidence is stored in `p15/`. The two deterministic records embed their effective
inputs and retain either complete accepted results/iteration history or the expected limit-point
failure, rejected iteration, and last committed path.

The generated V00-V09 calculation audit is stored in `validation/math-core-audit.json`. It records
the guide reference, current public solver/element output, numerical deviation, interpretation,
and pass/fail result for every mathematical-core layer.
