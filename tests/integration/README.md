# Integration tests

P2 wires the four existing finite-element cores into `nonlinear_core`. P3 verifies that the same
equilibrium and constrained-correction path reaches all four native linear reference solutions in
one exact Newton correction and classifies an underconstrained frame as a linear failure.

P5 and P6 advance the same four adapters with load and displacement control. P7 verifies that the
frame displacement path uses scaled adaptive increments while retaining the P6 equilibrium and
reaction contract.

P8 advances continuum, frame, plate, and shell linear references with the same spherical
arc-length driver and confirms that each stable path remains proportional to its native solution.

P9 selects the nonlinear Frame adapter from the model formulation, assembles exact element
internal forces and tangents, recovers displacement/reaction/N/V/M and current/reference
configuration data, approaches the installed linear `frame2d` solution at small load, extracts an
accepted load-displacement path, and retains a collapsed-chord failure exactly once at its owner.

P10 publishes the four planned FastAPI endpoints and generated OpenAPI contract. HTTP integration
tests run the P9 shallow arch through the API, retrieve the retained result, preserve semantic JSON
locations, enforce request/DOF limits, and return real nonconvergence as a failed analysis record
instead of HTTP 500.

P12-P14 add nonlinear Continuum, Plate, and Shell adapter/API paths. P15 freezes package/frontend
version agreement, deterministic success and expected-failure release records, complete traceability,
and the checked-in Schema/OpenAPI documents as one non-mutating release check.
