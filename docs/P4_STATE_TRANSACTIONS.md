# P4 State Transactions

## 1. Status and boundary

P4 implements trial/commit/rollback state ownership independently of the future Newton loop. It
does not decide whether an iteration converged, select a cutback size, or retry a step. Those
decisions begin in P5/P7; P4 supplies the safe transaction primitives they must use.

The core rule is:

```text
every iteration = evaluate(current total trial displacement, load factor, committed baseline)
never           = evaluate(..., previous trial state)
```

## 2. Immutable state model

`CommittedState` stores the last globally converged point. `TrialState` stores one adapter response
derived from exactly one committed baseline. Both carry:

- model ID, model family, and canonical model SHA-256;
- adapter/core identity and the core-owned state token;
- step and iteration indices;
- total displacement, load factor, and path-dependent history;
- a deterministic content hash (`state_id` or `trial_id`).

Displacements are copied into read-only NumPy arrays. History is deep-copied into immutable mapping
and tuple containers, so later mutation of caller-owned dictionaries, lists, or arrays cannot alter
a committed snapshot.

## 3. Lifecycle

```text
initialize_state(adapter, model)
  -> CommittedState(step=0)

begin_step(committed, target, predictor)
  -> StepContext(base_state=committed)

evaluate_trial(context, adapter, model, trial_u, load_factor, iteration)
  -> adapter.evaluate(..., committed_state=context.base_state)
  -> TrialEvaluation(response, TrialState)

commit(context, trial, converged=True)
  -> new CommittedState

rollback(context, trial)
  -> context.base_state (same object)
```

`commit()` rejects a missing or false convergence confirmation. It also rejects trials created from
another baseline or step. `rollback()` never copies trial history back into the baseline.

For cutback, the caller rolls back the failed context and calls `begin_step()` again with the same
committed state, a smaller target, and an incremented attempt index.

## 4. Restart contract

`serialize_restart()` accepts only `CommittedState` and emits deterministic JSON. The document
contains a frozen schema version, model and adapter identity, state data, and a SHA-256 state ID.

`deserialize_restart()`:

- rejects missing and unknown fields;
- rejects trial documents and unsupported schema versions;
- recomputes and verifies the state hash;
- optionally verifies the supplied model hash and expected adapter ID;
- recreates read-only displacement and deeply immutable history.

This makes accidental edits or loading a snapshot against a different model detectable. The hash
is an integrity check, not a security signature.

## 5. Verification evidence

- `tests/unit/test_p4_state.py` verifies deep immutability, deterministic restart round trips,
  model authentication, tamper detection, and schema rejection.
- `tests/verification/test_v07_state_transactions.py` implements the irreversible V07 history law
  `q_trial=max(q_n, |u_trial|)`. A failed `u=0.5` trial returns `q=0.5`, `f_int=0.75`; rollback then
  gives the same `u=0.3`, `q=0.3`, `f_int=0.39` result as the direct path.
- `tests/integration/test_p4_four_core_restart.py` initializes, evaluates, commits, serializes,
  restores, and continues through the continuum, frame, plate, and shell adapters.

P5 composes the P3 equilibrium algebra and this lifecycle in the Newton/load-control driver
documented by `P5_NEWTON_LOAD_CONTROL.md`, without giving the solver ownership of element/material
history.
