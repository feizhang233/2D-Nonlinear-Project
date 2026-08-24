# P6 Displacement Control and Reactions

## 1. Status and boundary

P6 adds fixed-increment prescribed-displacement control:

```text
solve_displacement_control(adapter, model, number_of_steps=1, initial_state=None)
    -> DisplacementControlSolution(result, committed_state, final_response)
```

The controller is the `analysis.displacement_control.target` DOF and every accepted step advances
it by `analysis.displacement_control.increment`. P6 keeps the existing committed load factor and
uses the controller reaction as the load response. The same driver now honors the P7 line-search
configuration, and `solve_adaptive_displacement_control()` adds scaled increment growth,
cutback, and retry. Arc length remains separate.

## 2. Control validation

Before iteration, the driver requires that the selected node/DOF:

- occurs exactly once in the adapter's deterministic DOF map;
- is not already present in the model constraint map;
- has a finite, non-zero configured increment;
- belongs to a model configured with `control_method="displacement"`.

Missing or conflicting control DOFs are `CONTROL_ERROR` failures and produce no trial step.

## 3. Block Newton solve

The control DOF is added to the constrained partition with the step's absolute target value. For
unknown free DOFs `f` and prescribed/support/controller DOFs `p`, P3 solves:

```text
delta_u_p = u_target,p - u_current,p
K_ff delta_u_f = r_f - K_fp delta_u_p
```

The load factor is fixed during the step and only displacement corrections are solved. Full Newton
selects the current tangent each iteration; explicitly selected modified Newton freezes the first
effective tangent. P4 still recomputes every trial response from the same committed baseline.

Convergence requires the free residual, free correction, energy work, linear residual, controller
gap, and all prescribed-value gaps to pass their tolerances. In a displacement-driven problem the
equilibrated free-force terms can both approach zero, so P6 includes the controller/support
reaction norm in the `eta_R` force scale while retaining only the free residual in its numerator.

## 4. Reaction recovery

After free equilibrium and prescribed-value convergence, reactions are recovered before commit:

```text
q_constrained = f_int - f_ext = -r_constrained
```

The accepted `StepResult.response` separates:

- `controller_reaction` for the selected control DOF;
- `support_reactions` for original model constraints;
- `free_residual` and `free_dofs` for equilibrium evidence;
- `full_imbalance` for sign and balance auditing;
- total control displacement, signed increment, retained load factor, and convergence history.

## 5. Control boundary

Displacement control can cross a load maximum when the chosen displacement remains monotonic. It
cannot continue if that control coordinate reverses along the path. The minimal counterexample
`c=x^2` starts at its turning point: a negative prescribed `c` increment has no real neighboring
equilibrium and the remaining free tangent is singular. P6 classifies this as `CONTROL_ERROR`,
retains the rejected step, and returns the exact previous committed state.

## 6. Verification evidence

- `tests/verification/test_v05_displacement_control.py` embeds the V05 matrix
  `[[4,1],[1,3]]`, obtaining `delta_u1=-0.025` and controller reaction `+0.275`.
- The same file traces the V04 path from `v=8` to `v=2`, crossing
  `v*=2.6276509877`, `F*=7.7528728303`, and entering the descending-force branch.
- Its `c=x^2` test verifies classification and rollback when the control coordinate reverses; a
  pre-existing constraint conflict is also rejected before iteration.
- `tests/integration/test_p6_four_core_displacement_control.py` promotes one free DOF to the
  controller for continuum, frame, plate, and shell adapters, then checks its prescribed value,
  finite reaction, and remaining free equilibrium.

P7 line search, cutback/retry, adaptive increments, and failure policy are documented in
`P7_GLOBALIZATION_AND_ADAPTIVE_STEPS.md`.
