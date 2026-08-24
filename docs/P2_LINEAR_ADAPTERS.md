# P2 Linear Adapter Baseline

## 1. Status and boundary

P2 connects the four existing linear mathematics packages to one solver-facing contract. The
adapters translate `ModelInput`; they do not copy or reimplement any core element formulation.

| Family | Package | Version | Global DOFs per node |
|---|---|---:|---|
| Continuum | `continuum-math` | 0.7.0 | `UX, UY` |
| Frame | `frame2d` | 0.2.0 | `UX, UY, RZ` |
| Plate | `mindlin-plate-core` | 0.3.0 | `UZ, RX, RY` |
| Shell | `shell-core` | 1.0.0 | `UX, UY, UZ, RX, RY, RZ` |

P2 is a linear reference layer. It does not implement residual iteration, Newton updates,
geometric stiffness, finite-deformation kinematics, constitutive history, commit/rollback, or a
nonlinear solve driver.

## 2. Public contract

`ModelAdapter` freezes these operations:

```python
validate(model)
initial_state(model)
dof_map(model)
constraint_map(model)
evaluate(model, displacement, load_factor=1.0, committed_state=None)
recover(model, displacement, load_factor=1.0, committed_state=None)
```

`evaluate()` returns the same `ModelResponse` for every family:

- global internal force `K @ u`;
- global tangent `K`;
- scaled external force `lambda * f`;
- optional external tangent (`None` for the current fixed linear loads);
- immutable trial state;
- element contributions in global DOF coordinates;
- strain energy, minimum `detJ`, optional `detF`, and local failures.

`detF` is intentionally `None` for these small-deformation linear references. Frame elements do not
use a 2D isoparametric Jacobian, so their `detJ` is also `None`. The other three adapters report a
positive minimum element Jacobian.

Use the registry at the application boundary. Later solver code receives only the protocol:

```python
from nonlinear_core import get_adapter

adapter = get_adapter(model)
response = adapter.evaluate(model, trial_displacement, load_factor=0.5)
residual = response.external_force - response.internal_force
```

## 3. P2 property mapping

| Family | Required element properties | Material parameters | P2 formulations |
|---|---|---|---|
| Continuum | `thickness` (default `1.0`) | `young`, `poisson`, optional `plane_mode` | T3 or Q4 |
| Frame | `area`, `second_moment` | `young` | 2-node frame |
| Plate | `thickness`, optional `shear_correction`, `plate_method`, `shear_scheme` | `young`, `poisson` | Q4 DKQ/MITC4 public operator |
| Shell | `thickness`, optional `shear_correction_factor` | `young`, `poisson` | Q4 flat shell RM |

Aliases `young_modulus`/`E`, `poisson_ratio`/`nu`, `A`, and `I` are accepted where applicable.
The contract layer and adapters do not perform unit conversion. The shell adapter targets the
shell core's fixed SI contract, so shell reference inputs must be SI.

## 4. Supported linear loads

- All four adapters accept generalized nodal loads.
- Continuum accepts model-wide body force and edge traction. An edge traction identifies its two
  nodes through `extensions.edge_node_ids`.
- Frame accepts local element distributed loads with `qx_i`, `qy_i`, `qx_j`, and `qy_j`.
- Plate accepts per-element surface pressure and edge data. Edge data uses
  `extensions.local_edge` in the core's zero-based edge order.
- Shell accepts nodal, surface, edge, and body loads. Distributed shell loads are global and do not
  accept moment components.

Unsupported combinations fail adapter validation instead of being silently ignored.

## 5. Reference evidence

The four inputs are under `examples/adapters/*-linear.json`. Their original-core displacement,
reaction, energy, version, and complete DOF order are frozen in
`examples/adapters/reference-results.json`.

`tests/integration/test_p2_linear_adapters.py` verifies:

- all four adapters satisfy the runtime protocol and response shapes;
- element contributions scatter to the model response;
- adapter recovery matches the original public-core solve;
- saved displacement, reaction, energy, and DOF-order references remain unchanged;
- a generic residual consumer contains no element-family branch.

The sibling source repositories are read-only inputs to P2. Local development installs them as
editable packages, but all production calls go through their exported public interfaces.
