# P7 Globalization, Adaptive Steps, and Failure Policy

## 1. Status and boundary

P7 adds two layers without changing the P2 adapter contract or the P4 state-transaction rules:

```text
Newton direction
    -> full step / backtracking / conservative orthogonality
    -> accepted alpha or classified rejection

solve_adaptive_load_control(...) or solve_adaptive_displacement_control(...)
    -> fixed-step attempt
    -> accept and optionally grow, or rollback and cut back
```

The existing `solve_load_control()` and `solve_displacement_control()` entry points honor the
configured line search but retain their fixed-step behavior. Automatic step control is enabled
only through the explicit `solve_adaptive_*` wrappers. P8 arc-length continuation is not part of
P7.

## 2. Line-search contract

`apply_line_search()` receives the current equilibrium evaluation, total displacement, Newton
direction, and an evaluator callback. Every sample is evaluated from the same committed baseline;
line-search samples are never committed.

- Disabled line search returns the Newton full step `alpha=1` without an extra evaluation.
- Backtracking starts at `alpha=1`, reduces by `reduction_factor`, respects `min_alpha` and
  `max_iterations`, and accepts sufficient decrease of
  `0.5 * ||r_free||^2`. Its evidence is explicitly labeled
  `residual_l2_nonconservative`; it is not presented as potential energy.
- Orthogonality searches for `delta_u_free^T r_free(alpha)=0`. It is allowed only when adapter
  response metadata explicitly contains `conservative=true`; otherwise it returns a classified
  line-search failure.

Every Newton `IterationRecord` stores `accepted_alpha` plus the method, merit function, sampled
alphas, merit values, directional residuals, evaluation count, and any failure reason.

## 3. Adaptive growth, cutback, and retry

The adaptive wrappers use the existing `StepControlOptions`:

- `target_iterations` decides whether an accepted fast step may grow;
- `growth_factor` and `max_step` bound growth;
- `cutback_factor` and `min_step` bound reduction after a retryable rejection;
- `max_retries` limits consecutive retries of the same physical step;
- `max_steps` limits accepted load steps or requested displacement steps.

Load control applies these values directly to the load-factor increment. Displacement control
scales its configured displacement increment by the ratios `min_step/initial_step` and
`max_step/initial_step`, preserving the increment sign.

A rejected attempt retains its original `StepResult`, iteration records, and failure. Adaptive
evidence adds `attempt_index`, `adaptive_step_size`, `next_step_size`, `will_retry`, and
`adaptive_termination`. A retry begins again from the unchanged committed P4 state and uses the
same physical `step_index`.

Terminal reasons are explicit: `MIN_STEP_REACHED`, `MAX_RETRIES_REACHED`,
`NONRETRYABLE_FAILURE`, or `MAX_STEPS_REACHED`.

## 4. Failure dispositions

`failure_disposition()` covers every public failure code:

| Failure code | P7 disposition |
|---|---|
| `MODEL_ERROR` | Terminate for reference-model errors; retry current-configuration `min_det_f` geometry failures |
| `CONTROL_ERROR` | Retry with cutback |
| `TANGENT_ERROR` | Retry with cutback |
| `STATE_ERROR` | Terminate because state identity/rollback cannot be repaired by step size |
| `LINEAR_SOLVE_ERROR` | Retry with cutback |
| `LOCAL_MATERIAL_ERROR` | Retry with cutback |
| `NONCONVERGENCE` | Retry with cutback |

The terminal `FailureRecord.details` adds the termination reason, terminal step size, and retry
count. Retryable rejected attempts remain visible even when a smaller attempt later succeeds.

## 5. Verification evidence

- `tests/verification/test_v06_line_search.py` proves the V06 orthogonality result `x=[1,1]` at
  `alpha=1`, residual-L2 backtracking to `alpha=0.5`, no-op full-step behavior, and rejection of
  unmarked nonconservative orthogonality.
- `tests/verification/test_p7_adaptive_steps.py` proves successful cutback from `0.2` to `0.1`,
  bounded growth, explicit minimum-step and maximum-retry termination, retained rejected-attempt
  evidence, and a disposition for all seven public failure codes.
- `tests/integration/test_p7_adaptive_displacement.py` grows a real frame-core displacement
  increment from `1e-6` to `2e-6` while preserving P6 equilibrium and reaction semantics.
