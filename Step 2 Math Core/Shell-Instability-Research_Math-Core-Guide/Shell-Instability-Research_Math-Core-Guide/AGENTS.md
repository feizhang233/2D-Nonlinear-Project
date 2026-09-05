# Shell Instability Research Math Core Instructions

This folder is the AI-routable research package for an 8-12 week shell-instability study.

Before changing instability mathematics, numerical procedures or validation evidence:

1. Read `AI_CONTENT_INDEX.json`, then route to the smallest relevant files.
2. Read `AI_USAGE.md` before interpreting an eigenvalue, limit point, bifurcation or postbuckling path.
3. Treat `01_核心算法/核心算法与实现顺序.md` as the package-level algorithm contract.
4. Use the residual convention `R(q,lambda)=f_int(q)-lambda*f_ref=0` and Newton equation `K_T*dq-f_ref*dlambda=-R`. If another package uses `r=f_ext-f_int`, map all signs explicitly.
5. Distinguish five objects: linear eigenvalue, tangent singular point, limit point, bifurcation point and imperfect-shell limit load. Never use them as synonyms.
6. At a singular point, classify with a left null vector. For a symmetric conservative tangent the left and right null vectors coincide; for follower loads or nonsymmetric tangents they generally do not.
7. Treat a cluster of critical eigenvalues as a critical subspace. Track clustered subspaces rather than individual eigenvectors, which may rotate or exchange order.
8. Single-mode Koiter coefficients and the `1/2` or `2/3` imperfection laws are local asymptotic results. Do not apply them blindly to interacting modes, finite imperfections or remote postbuckling states.
9. Branch switching requires a converged critical point, a resolved null space, a controlled seed and a corrected equilibrium solution. An eigenvector plot or arbitrary perturbation is not branch-switch evidence.
10. Run V00-V09 in `03_验证题目与答案/验证矩阵.md` for algorithm changes. Run V10 for any research or engineering claim.
11. Preserve evidence for mesh, step size, boundary conditions, imperfection field, mode normalization, tangent consistency and negative-eigenvalue history.
12. The two PDFs in `04_完整参考` are canonical study references, not proof that a particular finite-element implementation satisfies the algorithms.
13. Do not present this package as a design-code check, experimental calibration, complete GMNIA implementation, production shell element, contact solver, material failure model or probabilistic reliability method.
14. When adding a formula, benchmark or threshold, record its source, units, normalization, applicability and paired acceptance criterion.
