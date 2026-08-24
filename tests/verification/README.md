# Verification tests

The V00-V09 mathematical suite is added phase by phase.

- P3 implements V01: exact linear one-step recovery, residual/Newton sign, energy, and the
  wrong-sign counterexample.
- P4 implements V07: failed trial `u=0.5` produces `q_trial=0.5` and `f_int=0.75`, but rollback
  preserves `q_n=0.2`; the next `u=0.3` trial and the direct path both produce `q_trial=0.3` and
  `f_int=0.39`. Restart and uninterrupted continuation also produce identical canonical states.
- P5 implements V03: the imperfect-column full-Newton history matches the four reference
  `theta/R/K` rows and converges to `theta=0.0985643775`. Modified Newton is verified separately
  as a slower frozen-tangent method, and a zero-tangent limit point is retained as the expected
  load-control failure contrast.
- P6 implements V05: prescribing `delta_u2=0.1` gives `delta_u1=-0.025` and controller reaction
  `+0.275`. The V04 force-displacement path is continued through its load maximum using prescribed
  displacement, while a reversing `c=x^2` control coordinate is retained as the expected failure.
- P7 implements V06: conservative orthogonality reaches `x=[1,1]` at `alpha=1`, while
  nonconservative backtracking records an explicit residual-L2 merit. Adaptive tests retain a
  rejected large step before successful cutback, verify bounded step growth, and terminate
  explicitly at the minimum step or retry limit.
- P8 implements V08: the tangent predictor is `du=dlambda=0.1/sqrt(2)` and the corrected point is
  `(u,lambda)=(0.0708885680,0.0705323396)`, with equilibrium and the spherical constraint both
  converged. Separate paths cross the V04 load limit, retain radius-cutback failures, reproduce
  the same root after restart, and continue a snap-back contrast where one displacement control
  fails. Counterexamples also cover scale-sensitive real/complex roots, malformed restart
  increments, non-proportional loading, minimum radius, maximum retry termination, structured
  step-baseline exceptions, and explicit coefficient-overflow classification. Corrector evidence
  distinguishes two solved right-hand sides from the single shared matrix factorization.
- P9 implements V00/V09 with a real corotational Frame element: a finite 30-degree rigid rotation
  has zero deformation and energy, element and assembly directional differences show interior
  error valleys, and the small-load solution reduces to `frame2d`. Three controls agree at
  `(lambda,u_y)=(0.1,-0.0148011536)`. The shallow arch reaches its first limit near `lambda=0.296`;
  load control fails as expected above it while spherical arc length follows the descending path.
  Three step sizes, restart equivalence, a full-Newton imperfect column, and regular/distorted
  cantilever meshes complete the gate.
- P12 implements Continuum V00/V02/V09 with a plane-strain Total Lagrangian Q4: a finite
  30-degree rigid rotation has unit `detF` and roundoff-level energy, element and two-element
  assembly tangents show interior directional-difference valleys, and the zero-state tangent is
  the installed `continuum-math` Q4 tangent. Three load-step sizes and regular 1/2/4-element
  tension meshes reproduce the same endpoint. Every accepted step has positive `detF`; an
  inverting compression trial is rejected with its minimum determinant. Raw Gauss stress remains
  available while nodal averaging is explicitly derived.
- P13 implements Plate V02/V09 with a five-DOF Q4 von Karman/MITC4 element. The zero-state
  transverse tangent is the installed `mindlin-plate-core` tangent; element and four-element
  assembly directional differences show interior error valleys. Membrane, bending, and shear
  energies remain independently auditable, and the MITC4 pure-bending shear field stays at
  roundoff for thin and thick plates. Three step sizes reproduce one endpoint, regular
  1x1/2x2/4x4 meshes stabilize under refinement, and raw Gauss resultants are not node-averaged.
- P14 implements Shell V00/V02/V09 with a six-DOF corotational Q4 flat shell. A finite 30-degree
  rigid rotation has roundoff local deformation, zero internal force, and zero `N/M/Q`; the
  zero-state tangent is exactly the installed `shell-core` Q4/QLLL/drilling tangent. Element and
  assembled differences show interior error valleys, virtual work is preserved, explicit
  `alpha_d` scaling is verified, and regular/distorted two-thickness cases retain membrane `t`,
  bending `t^3`, positive `detJ`, and raw Gauss resultants.

P15 runs V00-V09 as one release gate and preserves the three-control stable-point match,
load-control limit-point failure, displacement-control snap-back failure, three step-size studies,
and multi-mesh/geometry studies without relaxing their existing tolerances.
