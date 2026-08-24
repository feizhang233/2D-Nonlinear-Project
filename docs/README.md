# Documentation

Project-facing technical documents belong here. The package-level mathematics, limitations, and
V00-V09 verification design remain in `../2D-Nonlinear-Project_Math-Core-Guide/`.

- `P1_DATA_CONTRACT.md` documents the frozen `1.0.0` input/output topology, validation rules,
  deterministic DOF order, error codes, and Schema boundary.
- `P2_LINEAR_ADAPTERS.md` documents the unified adapter/response contract, four public-core
  mappings, supported linear loads, and frozen native-reference evidence.
- `P3_EQUILIBRIUM_AND_LINEAR_SOLVE.md` documents residual and tangent signs, constraint
  elimination, reaction recovery, dense/sparse solve paths, and classified linear failures.
- `P4_STATE_TRANSACTIONS.md` documents immutable committed/trial snapshots, lifecycle guards,
  cutback isolation, authenticated restart JSON, and V07 evidence.
- `P5_NEWTON_LOAD_CONTROL.md` documents fixed load increments, full/modified Newton behavior,
  scaled convergence metrics, iteration evidence, and classified termination boundaries.
- `P6_DISPLACEMENT_CONTROL.md` documents control-DOF validation, block elimination, controller and
  support reaction recovery, V05, and the V04 load-limit/control-reversal contrasts.
- `P7_GLOBALIZATION_AND_ADAPTIVE_STEPS.md` documents full-step/backtracking/orthogonality
  globalization, adaptive growth and cutback, retry limits, failure dispositions, and retained
  rejection evidence.
- `P8_SPHERICAL_ARC_LENGTH.md` documents the predictor/corrector equations, two-root continuity
  policy, radius adaptation, restart direction evidence, V08, V04, and snap-back boundaries.
- `P9_COROTATIONAL_FRAME.md` documents the separated reused-core provenance, corotational
  kinematics, energy-consistent internal force/tangent, Frame recovery, scope limits, and V09
  evidence.
- `P10_FASTAPI_SERVICE.md` documents synchronous/local-asynchronous execution, live progress,
  restart/cancellation, request/DOF limits, error categories, and API acceptance evidence.
- `P11_NONLINEAR_STUDIO.md` documents the Material UI workbench, unified revision-safe state,
  control-specific settings, result bridge, visualization boundaries, and frontend acceptance.
- `P12_TOTAL_LAGRANGIAN_CONTINUUM.md` documents the plane-strain TL Q4/Saint-Venant--Kirchhoff
  formulation, consistent tangent, `detF` gate, raw Gauss recovery, limitations, and V09 evidence.
- `P13_VON_KARMAN_PLATE.md` documents the formulation-specific five-DOF Plate contract, von
  Karman membrane terms, reused MITC4 operators, energy split, raw recovery, and V09 evidence.
- `P14_COROTATIONAL_FLAT_SHELL.md` documents the current-frame/relative-rotation map, reused
  Q4/QLLL/drilling operators, energy Hessian, virtual work, raw `N/M/Q`, and V09 evidence.
- `P14_ACCEPTANCE_AND_ARCHITECTURE.md` records the P14 acceptance matrix, Mermaid implementation
  structure, code/data flow, executed quality gates, and non-blocking follow-up boundaries.
- `P15_RELEASE_ACCEPTANCE.md` records the 0.1.0 cross-family release matrix, control-method
  contrasts, deterministic success/failure evidence, version checks, and isolated-wheel gate.
- `GMSH_AND_DISTRIBUTED_LOADS.md` documents the all-Q4 Gmsh bridge, boundary metadata, consistent
  member/edge/surface load vectors, units, and fixed-reference limitations.
- `MATH_CORE_CALCULATION_AUDIT.md` records the fresh V00-V09 calculations, numerical deviations,
  their causes, major-problem decision, and the reproducible machine-readable audit command.
