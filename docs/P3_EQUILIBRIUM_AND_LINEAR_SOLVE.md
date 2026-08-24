# P3 Equilibrium, Constraints, and Linear Solve

## 1. Status and boundary

P3 implements the algebra between a `ModelAdapter` response and a future nonlinear iteration
driver. It evaluates one equilibrium state and one constrained Newton correction; it does not run
load steps, convergence loops, cutback, line search, or state commit/rollback.

The fixed sign convention is:

```text
residual          r = f_ext - f_int
effective tangent K = d(f_int)/du - d(f_ext)/du
Newton equation   K * delta_u = r
reaction          q_c = f_int,c - f_ext,c = -r_c
```

## 2. Residual and tangent contract

`build_equilibrium()` retains:

- the complete residual;
- free-DOF residual;
- constrained-DOF residual;
- effective tangent after subtracting an optional external-force tangent;
- free/constrained index arrays and prescribed values;
- relative tangent symmetry error.

The interface records symmetry but does not test or assume positive definiteness. This is required
for limit points, bifurcations, follower loads, and other cases where a valid tangent may be
indefinite or nonsymmetric.

## 3. Constraint elimination

For absolute prescribed values `u_c_bar`, the correction on constrained DOFs is:

```text
delta_u_c = u_c_bar - u_c_current
```

The free equation is then:

```text
K_ff * delta_u_f = r_f - K_fc * delta_u_c
```

This handles zero and nonzero prescribed displacements with the same path. Constraint rows are not
discarded from the original response. After the free residual is equilibrated,
`recover_constraint_reactions()` returns the algebraic support/controller force `-r_c` and retains
the full structural imbalance for auditing.

## 4. Linear solver paths

`solve_linear_system()` provides:

| Backend | Purpose |
|---|---|
| `dense` | NumPy/LAPACK solve for small analytical and verification systems |
| `sparse_lu` | SciPy CSC sparse LU with column ordering and diagonal pivoting |
| `auto` | Dense up to `dense_threshold`, sparse LU above it |

Optional row/column equilibration is applied before factorization. The result always reports the
actual residual of the original equation, `A @ X - B`, rather than only a backend status. A vector
right-hand side returns a vector solution; a non-empty `(n, m)` right-hand-side matrix is solved in
one dense or sparse-LU factorization and returns an `(n, m)` solution.

Failures are data, not convergence states:

- `LINEAR_DIMENSION_MISMATCH`;
- `LINEAR_NONFINITE_INPUT`;
- `LINEAR_SINGULAR_SYSTEM` with estimated nullity;
- `LINEAR_ILL_CONDITIONED_SYSTEM`;
- `LINEAR_BACKEND_UNAVAILABLE`;
- `LINEAR_FACTORIZATION_FAILED`;
- `LINEAR_NONFINITE_RESULT`;
- `LINEAR_EXCESSIVE_RESIDUAL`.

A failed `NewtonCorrectionResult` contains the classified `LinearSolveResult` and no displacement
correction. It cannot be represented as nonlinear convergence.

## 5. Verification evidence

- `tests/verification/test_v01_linear_recovery.py` reproduces the V01 analytical correction
  `[1/11, 7/11]`, zero updated residual, energy `15/22`, and the wrong-sign counterexample.
- `tests/unit/test_p3_equilibrium.py` verifies residual sign, tangent subtraction, nonsymmetry,
  indefinite tangents, V05 nonzero displacement control, and reaction `+0.275`.
- `tests/unit/test_p3_linear_solver.py` verifies dense and sparse-LU paths, actual residuals,
  one-factorization multi-right-hand-side solving, pivoting, singular/nullity, ill-conditioned,
  non-finite, and dimension failure classes.
- `tests/integration/test_p3_four_core_linear_step.py` verifies that one exact correction reproduces
  the original continuum, frame, plate, and shell reference solutions. Removing frame constraints
  produces a classified rigid-mode/singular failure.

P4 adds the state transaction layer documented in `P4_STATE_TRANSACTIONS.md`. P5 will consume the
P3 algebra and P4 state primitives inside a Newton/load-step loop and apply nonlinear convergence
criteria.
