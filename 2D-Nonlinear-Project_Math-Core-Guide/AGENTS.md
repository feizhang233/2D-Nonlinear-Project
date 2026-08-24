# 2D-Nonlinear-Project Math Core Instructions

Before changing nonlinear-solver mathematics or related tests in this folder:

1. Read `AI_CONTENT_INDEX.json` and route to the smallest relevant documents.
2. Read `AI_USAGE.md` for the residual sign, state protocol and prohibited inferences.
3. Treat `01_核心算法/核心算法与实现顺序.md` as the package-level canonical contract.
4. Preserve `r = f_ext - f_int` together with `K_t * du = r`; if another convention is used, map the complete chain explicitly.
5. Keep the solver independent of element and material type. Element/material modules own internal force, consistent tangent and trial state.
6. Never mutate committed history during a trial iteration. Commit only after global convergence; rollback every rejected step.
7. Run V00-V08 in `03_验证题目与答案/验证矩阵.md` for core changes. Run V09 when the element/material interface changes.
8. Do not present this package as a complete finite-strain element, material library, contact solver, dynamic solver, localization regularization or branch-switching implementation.
9. When adding a formula, benchmark or tolerance, record its source, units, applicability, sign convention and paired acceptance criterion.
10. Preserve failure evidence: load-step cuts, rejected trials, iteration history and control-method limits are part of the result.
