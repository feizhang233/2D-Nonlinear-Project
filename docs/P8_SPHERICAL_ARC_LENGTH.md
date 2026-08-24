# P8 Spherical Arc-Length Path Following

## 1. Status and boundary

P8 adds a solver-level path-following control without changing element, material, or P4 state
ownership:

```text
solve_arc_length(adapter, model, number_of_steps, initial_state, previous_increment)
    -> tangent predictor
    -> equilibrium plus spherical-constraint corrector
    -> direction-continuous root
    -> commit or radius cutback and retry
```

This basic implementation requires a fixed proportional mechanical load
`f_ext=lambda*f_hat` on the free DOFs. It rejects configuration-dependent external-force
directions, non-zero follower-load tangents, non-proportional loading, and simultaneous P7 line
search instead of silently applying an invalid formula. It is a quasi-static path tracer, not a
stability proof, bifurcation detector, or production branch-switching algorithm.

## 2. Spherical constraint and predictor

The reduced free-DOF constraint is

```text
g = Delta_u^T Delta_u
    + beta^2 Delta_lambda^2 f_hat^T f_hat
    - Delta_l^2 = 0
```

`ArcLengthOptions.radius`, `min_radius`, `max_radius`, and `beta` provide `Delta_l` and its bounds.
At a converged state the predictor solves

```text
K_ff delta_u_I = f_hat_f
```

and scales the augmented direction to the requested radius. The first step takes the positive
load-factor direction. Later steps choose the predictor sign with the weighted augmented inner
product against the previous converged `ArcLengthIncrement`.

The returned `ArcLengthSolution.last_increment` and every accepted `StepResult.response` retain
the displacement and load-factor increments. A restarted solve passes `last_increment` back as
`previous_increment`; the solver verifies that its augmented norm matches the recorded radius and
that constrained-DOF increments remain zero before starting a new step. No solver-private direction
data is injected into adapter/material history.

## 3. Corrector and two roots

At every iteration the same selected tangent matrix is used for two right-hand sides:

```text
K_ff delta_u_I  = f_hat_f
K_ff delta_u_II = r_f
```

The two columns are passed to `solve_linear_system()` together, so equilibration, SVD diagnostics,
and dense/sparse factorization run once per corrector iteration. Each column's residual is then
recomputed against the original tangent and checked independently. `linear_solves` records right-
hand-side count, while `linear_factorizations` records the actual factorization count.

The total corrected increment is

```text
Delta_u_new      = Delta_u + delta_u_II + delta_lambda delta_u_I
Delta_lambda_new = Delta_lambda + delta_lambda
```

Substitution into the sphere produces the Crisfield quadratic `a1*x^2 + a2*x + a3 = 0`.
`select_arc_length_root()` retains both real candidates, all three coefficients, the
discriminant, displacement continuity, weighted augmented continuity, direction cosine, selected
index, and selection reason. The first step chooses positive loading; later iterations choose the
candidate with maximum continuity in the same spherical metric. This augmented comparison allows
the load component to preserve direction when one displacement coordinate reverses in snap-back.
Quadratic degeneracy, discriminant, and continuity checks are scaled from their actual coefficient
or inner-product magnitudes, so small but valid engineering-unit systems are not compared with an
unrelated unit-scale tolerance. If finite inputs still overflow the quadratic coefficients or
discriminant, the selector requests model rescaling explicitly instead of returning invalid roots.

Complex roots and the absence of a direction-continuous root are classified failures. Strong
curvature is detected when the accepted augmented direction cosine is below `0.25`; the current
converged point is retained and the following radius is reduced.

## 4. Convergence, state, and radius policy

A step commits only when all of the following pass together:

- scaled free equilibrium residual `eta_R`;
- displacement correction `eta_u`;
- energy correction `eta_E`;
- normalized spherical residual `eta_arc=abs(g)/Delta_l^2`;
- both actual linear-solve residuals.

Every iteration is recomputed from the same committed P4 baseline. A failed attempt rolls back to
that exact state and remains in `SolveResult.steps`. Retryable failures reduce the radius with
`step_control.cutback_factor`; fast accepted steps may grow it with `growth_factor`, while detected
strong curvature reduces the next radius. `min_radius`, `max_radius`, and `max_retries` are always
enforced. Terminal reasons include `MIN_RADIUS_REACHED`, `MAX_RETRIES_REACHED`, and
`NONRETRYABLE_FAILURE`.

Adapter or state exceptions during the step-baseline evaluation are converted into a rejected
`StepResult` with a classified, non-retryable failure; they do not escape the public solver or
replace the last committed state.

Before stepping, the solver samples the external load at the committed factor and at offsets `0.5`
and `1.0`. All three responses must satisfy the same `lambda*f_hat` law and have zero external-force
tangent. This rejects non-proportional or follower loading before it can enter the basic P8 formula.

## 5. Verification evidence

- `tests/verification/test_v08_arc_length.py` matches the V08 predictor
  `Delta_u=Delta_lambda=0.1/sqrt(2)` and corrected intersection
  `(u,lambda)=(0.0708885680,0.0705323396)`.
- The same suite verifies both roots, complex-root classification, radius cutback, minimum-radius
  and maximum-retry termination, retained rejected attempts, restart direction equivalence and
  malformed-restart rejection, scale-independent small-root classification, non-proportional-load
  preflight rejection, coefficient-overflow classification, structured step-baseline failure,
  one-factorization/two-right-hand-side evidence, V04 continuation beyond `F*=7.7528728303`, and a
  snap-back path that continues when one displacement control fails.
- `tests/integration/test_p8_four_core_arc_length.py` advances continuum, frame, plate, and shell
  linear references through the same P8 solver and recovers each native proportional path.

P9 now supplies the first geometrically nonlinear Frame adapter and uses this unchanged P8 driver
for the shallow-arch limit-point path; see `P9_COROTATIONAL_FRAME.md`.
