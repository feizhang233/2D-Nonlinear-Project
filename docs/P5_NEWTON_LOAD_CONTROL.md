# P5 Newton and Load Control

## 1. Status and boundary

P5 combines the P3 residual/correction algebra and P4 state transactions into a quasi-static
fixed-increment load-control driver:

```text
solve_load_control(adapter, model, target_load_factor, initial_state=None)
    -> LoadControlSolution(result, committed_state, final_response)
```

P5 originally stopped at fixed load increments. The same driver now honors the P7 line-search
configuration; the explicit `solve_adaptive_load_control()` wrapper adds automatic growth,
cutback, and retry. Arc-length control remains outside this driver.

## 2. Load-step and Newton loop

Each step prescribes a signed load-factor increment with magnitude no greater than
`analysis.step_control.initial_step`:

```text
lambda_target = lambda_committed + delta_lambda
f_ext          = lambda_target * f_hat
```

The load factor remains fixed inside the iteration loop; only the total displacement is corrected.
Every iteration calls P4 `evaluate_trial()` with the same immutable committed baseline, then builds
the P3 residual and constrained Newton equation.

Full Newton selects the current response tangent on every iteration. Modified Newton is used only
when `newton_method="modified"`; it freezes the step's first effective tangent while continuing to
recompute response, residual, and trial state at every displacement. Because the current adapter
contract returns response and tangent together, `tangent_assemblies` records solver-selected
tangent assemblies/reuse, not low-level adapter floating-point work.

## 3. Convergence gates

The public `convergence_metrics()` function implements the math-guide definitions on free DOFs:

```text
eta_R = ||r_f|| / (||f_ext,f|| + ||f_int,f|| + F_floor)
eta_u = ||delta_u_f|| / (||u_f|| + U_floor)
eta_E = |delta_u_f^T r_f| / (|delta_u_f^T f_ext,f| + E_floor)
```

A step commits only when all three indicators and the actual linear equation's relative residual
satisfy their configured tolerances. The final negligible Newton correction is used as a
convergence check; the already evaluated equilibrium trial is committed.

Before convergence, the driver also rejects:

- NaN/Inf in response construction, energy, `detJ`, or `detF` diagnostics;
- non-positive `detJ` or `detF`;
- adapter-reported element/material local failures;
- classified linear-solve failures;
- exhaustion of the configured Newton iteration count.

## 4. Result and failure evidence

Every `IterationRecord` retains:

- `eta_R`, `eta_u`, `eta_E` and their dimensional norms/scales;
- total displacement, residual vector, candidate correction, and effective-tangent diagonal;
- actual absolute and relative linear residuals;
- whether the tangent was selected again, cumulative tangent-assembly count, status, and
  termination reason.

Every accepted `StepResult` stores total load factor, signed load increment, total displacement,
forces, energy, final indicators, and committed state ID. A rejected step remains in the result and
P4 rollback returns the exact previous committed state.

A singular or severely ill-conditioned tangent under fixed load control is classified as
`CONTROL_ERROR`: near a limit point this control method may be unable to represent the path. Other
linear failures remain `LINEAR_SOLVE_ERROR`; maximum iterations are `NONCONVERGENCE`. P7 maps these
failures to an explicit retry or termination disposition in the adaptive wrapper.

## 5. Verification evidence

- `tests/verification/test_v03_newton_load_control.py` reproduces the V03 imperfect-column
  `theta/R/K` table, final angle `0.0985643775`, and lateral displacement `0.9840486391`.
- The same file proves that full Newton updates the tangent and converges rapidly, modified Newton
  freezes one tangent and converges in more iterations, a limit-point zero tangent becomes
  `CONTROL_ERROR`, and NaN/local/nonconvergence paths reject without committing.
- `tests/unit/test_p5_load_control.py` independently checks the three scale formulas and records the
  P7 backtracking merit function, accepted `alpha`, and sample count.
- `tests/integration/test_p5_four_core_load_control.py` advances continuum, frame, plate, and shell
  references through `lambda=0.1` and `0.2` and reaches `0.2` times each native linear solution.

P6 builds displacement control on the same P3 partition algebra and P5 iteration evidence in
`P6_DISPLACEMENT_CONTROL.md`, with explicit prescribed-control and reaction semantics.
P7 globalization and adaptive stepping are documented in
`P7_GLOBALIZATION_AND_ADAPTIVE_STEPS.md`.
