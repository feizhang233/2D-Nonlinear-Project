# Constitutive Nonlinearity Weeks 10-14 Instructions

Before changing constitutive mathematics, material-point code or validation files in this folder:

1. Read `AI_CONTENT_INDEX.json` and route to the smallest relevant document set.
2. Read `AI_USAGE.md` for tensor, state, shear and tangent conventions.
3. Treat `01_核心算法/00_五周总览与材料接口.md` as the package-level interface contract.
4. Preserve the canonical material call: total strain plus committed state returns stress, algorithmic tangent, trial state and diagnostics; it must not mutate committed state.
5. Recompute every rejected trial from the same committed state. Commit only after the global equilibrium step converges.
6. Keep tensor formulas and engineering-Voigt formulas distinct. Never transfer shear factors without an explicit mapping and metric.
7. For the canonical J2 model preserve `f = q - (sigma_y0 + H_iso * alpha)`, `alpha_(n+1) = alpha_n + Delta_gamma`, and the denominator `3G + H_iso`.
8. Call a tangent “consistent” only when it is the derivative of the implemented discrete stress-update map and passes the multi-step directional-derivative check V06.
9. Run V00-V08 for any canonical material update change; also run V09 for plane stress, V10 for nonlinear hardening, and V11 for material/global coupling when those paths change.
10. Do not present the small-strain J2 core as a finite-strain, pressure-sensitive, anisotropic, softening, damage, viscous or production cyclic-plasticity implementation.
11. When adding a benchmark, provide its units, initial committed state, full increment history, expected state variables, tolerances, and paired answer.
12. Preserve failed-local-iteration and rollback evidence; a clean final stress alone is not sufficient validation.
13. Before claiming the package is complete, run `python3 04_可复现算例/validate_package.py` and require `PACKAGE_VALIDATION: OK`.
