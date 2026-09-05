# General Nonlinear Shell Math Core Instructions

This folder is the AI-routable math-core package for the `P08 General Nonlinear Shell` stage.

Before changing nonlinear-shell mathematics, code, tests or conclusions:

1. Read `AI_CONTENT_INDEX.json` and route to the smallest relevant file.
2. Read `AI_USAGE.md` before interpreting rotations, stresses, tangents, follower loads or postbuckling paths.
3. Treat `01_核心算法/核心算法与实现顺序.md` as the package-level contract.
4. Use the residual convention `r = f_ext - f_int` and Newton equation `K_t * dq = r`, with `K_t = d(f_int)/dq - d(f_ext)/dq`. Map all signs explicitly if another convention is used.
5. State whether rotation increments act on the left or right of the current rotation. Do not mix spatial and material increments.
6. Preserve work conjugacy: TL commonly pairs Green-Lagrange strain with second Piola-Kirchhoff stress; UL commonly pairs spatial rate of deformation with Cauchy/Kirchhoff stress and an objective algorithm.
7. Keep committed state immutable during global iterations. Recompute every trial response from the same committed state; commit only after global convergence.
8. Include material, geometric, rotational/stabilization and configuration-dependent external-load contributions in the same directional tangent check.
9. Do not assume tangent symmetry for follower loads, non-associative materials or other nonconservative effects.
10. Run V00-V08 before element/material integration changes, V09-V13 before system claims, and V14 before any GMNIA or engineering conclusion.
11. Record units, shell kinematics, thickness treatment, quadrature, boundary conditions, load parameterization, state protocol, mesh, step size, tolerances and reference source with every benchmark.
12. Do not present this package as a complete production element, design-code check, contact solver, fracture/localization model, nonlinear dynamic solver, or experimental calibration.

