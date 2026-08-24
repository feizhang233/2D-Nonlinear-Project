# P12 Total Lagrangian Q4 continuum

## 1. Status and scope

P12 completes one finite-deformation continuum vertical slice:

```text
ModelInput
  -> TotalLagrangianContinuumAdapter
  -> plane-strain Q4 / 2x2 Gauss integration
  -> Saint-Venant--Kirchhoff hyperelastic response
  -> common load / displacement / spherical arc-length solvers
  -> nodal displacement/reaction and raw Gauss-point recovery
```

The supported formulation is deliberately narrow:

- two-dimensional four-node isoparametric Q4;
- Total Lagrangian kinematics referred to the initial configuration;
- 2x2 full Gauss integration;
- constant reference thickness;
- plane strain with `F33=1` and `E33=0`;
- one objective Saint-Venant--Kirchhoff hyperelastic material; and
- fixed global nodal and boundary-edge reference loads.

Plane stress is rejected because finite-strain thickness recovery requires a separate local solve.
Updated Lagrangian kinematics, reduced/selective integration, hourglass control, mixed pressure
fields, near-incompressible stabilization, follower loads, plasticity, damage, and softening are
not P12 capabilities.

## 2. Kinematics and work-conjugate material response

At each reference Gauss point,

```text
x = X + u
F = I + du/dX
J = det(F)
E = 1/2 (F^T F - I)
```

The engineering Green-strain vector is

```text
e = [E11, E22, 2 E12]
```

and the in-plane second Piola--Kirchhoff stress is

```text
s = [S11, S22, S12] = D e
```

with the plane-strain Saint-Venant--Kirchhoff matrix

```text
D = [[lambda + 2 mu, lambda,          0],
     [lambda,          lambda + 2 mu, 0],
     [0,               0,             mu]]
lambda = E nu / ((1+nu)(1-2nu))
mu     = E / (2(1+nu))
```

`E` and `S` are work conjugate. The first Piola stress and Cauchy stress are recovered from the
same Gauss-point state as `P=F S` and `sigma=F S F^T/J`. `S33=lambda(E11+E22)` and
`sigma33=S33/J` are retained to make the plane-strain out-of-plane stress explicit.

Saint-Venant--Kirchhoff elasticity is objective and gives the required small-strain limit, but it
is not a general-purpose rubber or large-compression material model. Its use here is a verified
P12 reference implementation, not a production constitutive library.

## 3. Internal force and consistent tangent

The nonlinear Green-strain operator `B(F,grad0 N)` gives

```text
f_int = integral(B^T s dV0)
```

The returned tangent is the derivative of that same internal force at the same trial state:

```text
K_t = K_material + K_geometric
K_material  = integral(B^T D B dV0)
K_geometric_ab = integral((grad0 Na)^T S (grad0 Nb) I2 dV0)
```

Both parts are retained separately in the element response for verification. The common solver
continues to use `r=f_ext-f_int` and `K_t du=r`; no continuum-specific branch is introduced into
Newton, line search, state transactions, or path controls.

## 4. Geometry and failure gates

Every element evaluation checks all four Gauss points:

- the reference map must have positive, non-negligible `detJ0`;
- the current deformation must have `detF>0`;
- internal force, tangent, energy, and recovered stresses must remain finite; and
- element forces, tangent, state metadata, and Gauss results must come from one trial vector.

Invalid reference geometry fails adapter validation before analysis. A trial with `detF<=0`
returns the actual minimum determinant through the common response, so the solver rejects and
rolls back the step as `MODEL_ERROR: current configuration has non-positive detF`. It is not
converted into a convergence success or hidden by a looser tolerance.

## 5. Recovery and result provenance

Successful recovery retains:

- node-major displacement and reactions;
- element energy, minimum `detJ0`, and minimum `detF`;
- at each raw 2x2 Gauss point: natural coordinates, shape functions, `detJ0`, `F`, `detF`,
  Green--Lagrange strain, second Piola stress, first Piola stress, Cauchy stress, and energy density;
- stress/strain measure names and current/reference configuration metadata.

The P10 result bridge publishes these values as raw `gauss_point_response` records. A simple
connected-element average is also published as `nodal_smoothed_cauchy`, but it is marked
`is_derived=true`, names its averaging source, and says `visualization only`. It never replaces
the raw integration-point values.

## 6. Verification evidence

- `tests/unit/test_p12_total_lagrangian_q4.py` verifies the plane-strain Lamé matrix, V00 finite
  30-degree rigid-rotation objectivity, element V02 error valley, material/geometric tangent sum,
  symmetry, non-positive `detF`, and clockwise reference-map rejection.
- `tests/integration/test_p12_continuum_adapter.py` verifies registry selection, common response
  assembly, raw recovery, the `continuum-math` Q4 small-strain limit, explicit plane-stress
  rejection, and API raw/derived result labeling.
- `tests/verification/test_v09_total_lagrangian_continuum.py` verifies the assembled two-element
  V02 error valley, three load-step sizes, regular 1/2/4-element mesh sensitivity, positive
  `detF` at every accepted step, and typed solver rejection of an inverting compression step.

The runnable input is `examples/p12/q4-plane-strain-tension.json`. It converges in four fixed load
steps to a uniform plane-strain tension state; the tests use the converged endpoint as a regression
value, not as evidence for materials or meshes outside the stated scope.

## 7. Frontend integration

The browser workbench now preserves `model_family="continuum"`, the two-DOF order, four-node Q4
topology, thickness/material parameters, and the P12 analysis payload end to end. Its surface view
shows the reference/deformed Q4 projection and exposes raw Gauss-point averaged Cauchy components
in the result table. The smoothed nodal field remains explicitly visualization-only.
