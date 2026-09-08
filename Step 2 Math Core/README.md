# Step 2 Math Core

A unified Python, CLI, and HTTP interface for four bounded mathematical reference implementations. The repository contains executable code, interface documentation, tests, and request examples. Study guides, source maps, reference books, and generated reports remain local and are excluded from Git.

## Use in Nonlinear Studio

Open **Math Core** in the toolbar, choose a core and operation, load example parameters, and execute. These calculations do not change the active FE model or its analysis results.

HTTP endpoints: `GET /api/v1/math-cores`, `GET /api/v1/math-cores/{core_id}`, and `POST /api/v1/math-cores/execute`. See [INTERFACE.md](INTERFACE.md) for parameters, sign conventions, diagnostics, and limits.

## Python and CLI

From this directory, install with `../.venv/bin/python -m pip install -e .`, then use:

```python
from step2_math_core import execute

response = execute({
    "core": "plate_shell_buckling",
    "operation": "linear_buckling",
    "parameters": {
        "material_stiffness": [[12.0, -2.0], [-2.0, 6.0]],
        "geometric_stiffness": [[1.0, 0.2], [0.2, 0.5]],
    },
})
if not response.ok:
    raise RuntimeError(response.error)
result = response.to_dict()["data"]
```

```bash
step2-math-core list
step2-math-core describe constitutive_nonlinearity
step2-math-core call --file examples/constitutive_1d_request.json
step2-math-core verify general_nonlinear_shell
```

## Reference cores

| Core ID | Scope |
| --- | --- |
| `plate_shell_buckling` | Buckling references, critical plate loads, and imperfections |
| `shell_instability` | Critical-point classification, modal interaction, and continuation references |
| `constitutive_nonlinearity` | Small-strain material-point updates and algorithmic tangents |
| `general_nonlinear_shell` | Shell kinematics, loads, sections, materials, and state primitives |

The `step2_math_core/` adapters load the original Python implementations from their existing subdirectories. Keep those paths intact. Use `list_cores()` or `describe_core()` for machine-readable operation metadata.

Run interface tests from this directory with `../.venv/bin/python -m unittest discover -s tests -v`. The `verify` operation runs the original verification entry point; diagnostic labels such as `PARTIAL`, `REFERENCE_ONLY`, `NOT_RUN`, and `FAILED` retain their original meaning and must not be interpreted as production FE validation.
