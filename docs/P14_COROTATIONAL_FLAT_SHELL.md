# P14 corotational Q4 flat shell

## 1. Status and scope

P14 completes one geometrically nonlinear Shell vertical slice:

```text
ModelInput [UX, UY, UZ, RX, RY, RZ]
  -> CorotationalShellAdapter
  -> current element frame and relative nodal rotations
  -> shell-core Q4 membrane/bending + QLLL shear + drilling
  -> common nonlinear solvers and P10 API
  -> raw Gauss-point N/M/Q recovery
```

The formulation supports large rigid-body translation/rotation with small local strain and small
rotation relative to the corotating frame. It is limited to initially flat, four-node,
homogeneous isotropic shells with constant thickness and fixed global nodal, surface, and edge
loads. It is not a general curved-shell, arbitrary finite local-rotation, finite-strain,
follower-load, composite, plastic, damage, contact, bifurcation, or branch-switching formulation.

## 2. Corotational kinematics

The reference and current frames are built from nodes 1, 2, and 4. With row-basis matrices
`Lambda_0` and `Lambda_n`, reference coordinates `X`, current coordinates `x=X+u`, and nodal
rotation matrix `R_i`, the deformational translations and rotations are

```text
d_i_local = Lambda_n (x_i-x_1) - Lambda_0 (X_i-X_1)
R_i_relative = Lambda_n R_i Lambda_0^T
phi_i_relative = log(R_i_relative)
```

The physical shell rotations follow the `shell-core` convention
`theta_x=-phi_y`, `theta_y=phi_x`; `phi_z` is retained as the drilling rotation. A common finite
rigid rotation gives `d_local=0` and `R_relative=I`, so it produces no shell strain or energy.

## 3. Reused operator, internal force, and tangent

P14 uses the installed `shell-core 1.0.0` public interfaces to build the reference Q4 operator:

- plane-stress membrane and Reissner--Mindlin bending blocks;
- production `qlll_assumed_strain` transverse shear;
- production continuum-consistent drilling stabilization; and
- raw membrane/bending/shear/drilling recovery.

The local energy is

```text
U = 1/2 q^T (K_membrane + K_bending + K_shear + K_drilling) q
```

Global internal force and tangent are the first and second derivatives of this same energy through
the nonlinear corotational map. P14 evaluates the gradient with a fourth-order central stencil and
the symmetric Hessian with scaled central differences; `differentiation_step` is explicit in the
element properties and result metadata. V02 verifies the returned tangent against independent
directional differences at element and assembled levels. At zero local deformation the exact
rotated `shell-core` tangent is returned directly.

This energy-Hessian route favors inspectability and correctness for the bounded small models in
this project; it is not presented as an industrial high-performance shell implementation.

## 4. Drilling and virtual-work consistency

`alpha_d` is a required-positive, visible element parameter (default `1e-4`). The stabilization
penalizes the existing core mismatch
`theta_z - 0.5(v,x-u,y)` in the corotational local frame. It does not penalize an exact rigid
rotation. Energy, response metadata, and every Gauss-point drilling mismatch retain the actual
`alpha_d`; changing it cannot be hidden behind a fixed default.

Because internal force is the energy derivative, global virtual work equals the directional
change of local energy. Tests also retain the core transform convention
`q_local=T q_global`, `f_global=T^T f_local`.

## 5. Recovery and result provenance

Each element keeps four raw 2x2 Gauss records containing:

- natural and current global position plus reference `detJ`;
- membrane strain/resultant `N`;
- curvature/bending resultant `M`;
- QLLL assumed shear strain/resultant `Q`;
- top/bottom surface stress;
- membrane, bending, shear, and drilling energy densities; and
- drilling mismatch and `current-corotational-local` result basis.

The API publishes these as raw `gauss_point_response`. P14 performs no nodal extrapolation or
averaging, so a derived nodal field cannot overwrite raw `N/M/Q`.

## 6. Verification evidence

- `tests/unit/test_p14_corotational_flat_shell.py` checks 30-degree rigid-rotation objectivity,
  exact zero-state agreement with `shell-core`, the small-rotation force limit, element V02,
  virtual work, tangent symmetry, and explicit drilling-parameter scaling.
- `tests/integration/test_p14_shell_adapter.py` checks registry isolation from the linear Shell
  adapter, energy and current-frame metadata, raw `N/M/Q`, bounded-load/unit rejection, the common
  solver, and API provenance.
- `tests/verification/test_v09_corotational_shell.py` checks the assembled two-element V02 error
  valley and regular/distorted geometry over two thicknesses, including membrane `t`, bending
  `t^3`, positive `detJ`, and raw-result gates.

The runnable input is `examples/p14/corotational-flat-shell.json`. It is a verified flat-shell
cantilever slice, not evidence for general curved nonlinear shells.

## 7. Frontend integration

The browser workbench now preserves the P14 six-DOF order, 3D reference coordinates, four-node
flat-shell topology, drilling/shear properties, and analysis payload. The Q4 engineering
projection exposes `UZ` lift, translational/rotational reactions, and Gauss-averaged `N/M/Q`
resultant norms. It is not a curved-shell or general 3D postprocessor.
