# P15 release examples

This directory freezes two self-contained API-level release records:

- `release-success.json` embeds the complete imperfect-column input and a successful response at
  load factor `1.0`. It retains five accepted steps, 20 iterations, postprocessing, model SHA-256,
  Schema `1.0.0`, and solver/package version `0.1.0`.
- `release-expected-failure.json` embeds the complete shallow-arch limit-point input and the
  expected load-control failure requested at load factor `0.31`. Five steps are committed through
  `0.25`; step 6 is rejected after 30 iterations with `NONCONVERGENCE`, while the result preserves
  the last committed path instead of publishing an unconverged displacement as a success.

Regenerate or verify the evidence from the real P10 API path:

```bash
.venv/bin/python scripts/generate_release_evidence.py
.venv/bin/python scripts/generate_release_evidence.py --check
.venv/bin/python scripts/check_release.py
```

The generated timestamps and analysis UUID are intentionally removed. The check requires exact
contracts and record topology, compares floating values with a strict cross-platform tolerance,
and treats state IDs as derived hashes whose exact text may change with roundoff. Model hashes,
solver versions, convergence histories, failure details, and recovered results remain auditable.
