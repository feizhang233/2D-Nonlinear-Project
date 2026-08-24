# P13 von Karman MITC4 plate

## 1. Status and scope

P13 completes one geometrically nonlinear Plate vertical slice:

```text
ModelInput
  -> formulation-specific UX/UY/UZ/RX/RY plate DOFs
  -> VonKarmanPlateAdapter
  -> Q4 membrane + Reissner--Mindlin bending + MITC4 transverse shear
  -> common nonlinear solvers and P10 API
  -> separate membrane/bending/shear energy and raw 2x2 Gauss recovery
```

The scope is deliberately narrow: small in-plane strain and moderate transverse rotation in a
fixed reference planform, isotropic linear elasticity, constant thickness, four-node Q4 geometry,
2x2 integration, and fixed global nodal/surface/edge loads. It is not an arbitrary finite-rotation
plate/shell model and does not cover follower loads, finite membrane strain, plasticity, damage,
layered composites, drilling rotation, buckling-mode extraction, or branch switching.

## 2. DOF and formulation contract

The existing linear Plate contract remains `UZ, RX, RY`. An element whose formulation contains
`von-karman` activates the P13 node-major order:

```text
UX, UY, UZ, RX, RY
```

The supported explicit formulation is `Q4-von-karman-MITC4`. Every element must use
`plate_method="M"` and `shear_scheme="mitc4"`; mixed nonlinear/linear Plate formulations and
silent fallback to DKQ or reduced/full shear are rejected by adapter validation.

## 3. Kinematics, internal force, and tangent

With `u`, `v`, and `w` as mid-surface displacements, the engineering membrane strain is

```text
epsilon_x = u,x + 1/2 w,x^2
epsilon_y = v,y + 1/2 w,y^2
gamma_xy  = u,y + v,x + w,x w,y
```

The membrane resultant is `N = t D_plane-stress epsilon`. Bending curvature and MITC4 assumed
transverse shear use the public `mindlin-plate-core` 0.3 operators and their existing sign
convention. The element energy is retained as three independent contributions:

```text
Pi_int = U_membrane + U_bending + U_shear
```

The internal force is the derivative of this energy. The returned consistent tangent contains
the current von Karman membrane material term, the membrane geometric term, and the unchanged
linear bending/shear terms. The common solver therefore keeps the project convention
`r=f_ext-f_int` and `K_t du=r` without a Plate-specific Newton branch.

## 4. Reused core and recovery provenance

P13 calls the installed core's public `plate_element_matrices()`, `kinematic_matrices()`,
`element_response()`, `q4_consistent_load()`, and `q4_edge_consistent_load()` interfaces. It does
not copy the MITC4 tying implementation into this repository.

Every element recovery retains four raw 2x2 Gauss records containing physical/natural position,
`detJ`, membrane strain/resultant, transverse gradient, curvature, bending moment, MITC4 shear
strain/force, top/bottom bending stress, and three energy densities. The API publishes these as
raw `gauss_point_response`; Plate recovery performs no nodal averaging, so no smoothed field can
replace the integration-point values.

## 5. Verification evidence

- `tests/unit/test_p13_von_karman_mitc4.py` checks the nonlinear strain terms, exact zero-state
  transverse tangent against `mindlin-plate-core`, element V02, tangent symmetry, separate energy
  accounting, and MITC4 pure-bending shear behavior for thin and thick plates.
- `tests/integration/test_p13_plate_adapter.py` checks formulation-specific DOFs without linear
  Plate regression, registry selection, small-displacement core agreement, explicit option
  rejection, raw recovery, and API provenance.
- `tests/verification/test_v09_von_karman_plate.py` checks the four-element assembly V02 error
  valley, three load-step sizes, and regular 1x1/2x2/4x4 mesh convergence.

The runnable input is `examples/p13/von-karman-mitc4-plate.json`. Its in-plane boundary restraints
make membrane stiffening observable; the example is a vertical-slice regression, not a universal
plate benchmark.

## 6. Frontend integration

The browser workbench now preserves the P13 five-DOF order, four-node topology, MITC4 properties,
and nonlinear analysis payload. Its labeled engineering projection visualizes `UZ` as a diagonal
lift, and the result table reports Gauss-averaged membrane, bending, and shear resultant norms.
This projection is not an arbitrary finite-rotation 3D plate claim.
