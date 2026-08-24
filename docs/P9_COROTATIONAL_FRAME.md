# P9 Corotational 2D Frame

## 1. Status and scope

P9 completes the first real geometrically nonlinear vertical slice:

```text
ModelInput
  -> CorotationalFrameAdapter
  -> element internal force + consistent tangent
  -> load / displacement / spherical arc-length solver
  -> displacement, reaction, N/V/M, configuration, and path recovery
```

The element is a two-node corotational Euler-Bernoulli frame for large rigid-body rotation and
small elastic strain. Its local DOF order is `[u_i, v_i, phi_i, u_j, v_j, phi_j]`; positive
rotation and moment are counter-clockwise. It is not a finite-strain beam, Timoshenko beam,
material-nonlinear element, stability proof, bifurcation detector, or branch-switching method.

## 2. Reused-core boundary

The sibling `2D-Frame-Project` at commit
`b8276a1ced4fd5a2913efb23c981f4ec43e59f6e` contains the validated linear `frame2d==0.2.0`
records and sign conventions, but no corotational or geometric-stiffness implementation. P9 keeps
the reusable subset in a visibly separate package:

```text
src/reused_cores/frame2d_linear/
  models.py           # Node, FrameElement, NodalLoad
  geometry.py         # reference length and direction cosines
  transformation.py   # inherited local/global convention
  stiffness.py        # inherited linear Euler-Bernoulli stiffness
  PROVENANCE.md       # source commit and original SHA-256 values
```

The new mathematics lives in `src/nonlinear_core/elements/frame_corotational.py`; it is not
presented as copied capability. The normal P2 linear adapter still calls the installed `frame2d`
package directly. `PROVENANCE.md` is included in built wheels so this distinction survives
distribution.

## 3. Kinematics, internal force, and tangent

For reference chord `L, alpha_0` and current chord `l, alpha`, P9 uses the principal chord
rotation

```text
gamma = atan2(sin(alpha-alpha_0), cos(alpha-alpha_0))
v = [l-L, phi_i-gamma, phi_j-gamma]
```

and the elastic basic relation

```text
q = C v
C = [[EA/L,   0,     0],
     [0,    4EI/L, 2EI/L],
     [0,    2EI/L, 4EI/L]]
```

The global element response is derived from the same energy at the same trial point:

```text
f_int = B^T q
K_t   = B^T C B + N Hessian(l) - (M_i+M_j) Hessian(alpha)
```

The first term is retained as `material_tangent`; the last two terms are retained as
`geometric_tangent`. Their sum is the exact derivative of the returned internal force on the
principal angle branch. A current chord shorter than `1e-12 L` produces the typed local failure
`FRAME_CURRENT_LENGTH_COLLAPSED` rather than an invalid frame basis.

## 4. Assembly and recovery

`CorotationalFrameAdapter` is selected only when a Frame model contains a formulation name with
`corotational`. It assembles the six element DOFs into the common residual convention
`r=f_ext-f_int` without adding element-type branches to the solvers. P9 accepts SI labels
`m/N/Pa/rad`, linear-elastic `E/A/I`, fixed global nodal loads, and reference-local member loads.
Member `qx/qy` values are integrated with the Euler-Bernoulli consistent load vector and then
transformed to global DOFs. Follower, configuration-dependent, and non-proportional loads remain
outside this adapter.

Recovery returns:

- global nodal displacement and reactions;
- local end resultants `[-N, V, M_i, N, -V, M_j]` with `V=(M_i+M_j)/l`;
- strain energy and basic deformation/force;
- reference length/angle and current length/angle/chord rotation;
- material/geometric tangent norms and axial stretch `l/L`;
- accepted load-displacement points through `recover_frame_path()`.

`min_det_f` carries the one-dimensional axial stretch `l/L` for this adapter; it must not be
interpreted as a two-dimensional continuum determinant.

## 5. Verification evidence

- `tests/unit/test_p9_corotational_frame.py` verifies V00 with a finite 30-degree rigid rotation,
  exact zero-state reduction to the isolated linear stiffness, an element directional-derivative
  error valley, collapse classification, and reusable-core provenance.
- `tests/integration/test_p9_frame_adapter.py` verifies registry selection, assembly-level
  directional differences, the small-load `frame2d` limit, N/V/M and configuration recovery,
  load-displacement extraction, and non-duplicated local failures.
- `tests/verification/test_v09_corotational_frame.py` verifies three-control agreement at
  `(lambda,u_y)=(0.1,-0.0148011536)`, three displacement step sizes, the shallow-arch first limit
  near `lambda=0.296`, expected load-control failure above the limit, arc-length continuation down
  the descending path, restart equivalence, a full-Newton imperfect-column regression, and
  regular/distorted cantilever meshes.
- Existing V04/V08 tests retain the independent rigid-bar/spring and snap-back control-boundary
  counterexamples required by the mathematical guide. P9 adds a real frame-element shallow-arch
  snap-through path; it does not claim automatic branch switching or physical dynamic stability.

The runnable inputs are `examples/p9/shallow-arch-snap-through.json` and
`examples/p9/imperfect-column.json`.
