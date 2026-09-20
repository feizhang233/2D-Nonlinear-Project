# Shell 3D linear core provenance

Frozen from the local `2D-Shell-Project/src/shell_core` 1.0.0 implementation on 2026-09-20. `SOURCE_MANIFEST.json` records original and packaged SHA-256 values. Only import namespaces change; formulas and packaged schema are preserved. No sibling checkout or optional installed shell-core is needed at runtime.

The L baseline in `docs/3D-Shell_Math-Core-Guide` defines the integration contract: planar Q4 facets, QLLL assumed shear, six global nodal DOFs, consistent drilling, epsilon(z)=epsilon_m-z*kappa and M=-integral(z*sigma). N/I chapters are not implemented capabilities.

The host supplies bounded validation, NumPy diagonally equilibrated direct solution, equilibrium checks and JSON recovery. Original core validation, element assembly and raw Gauss recovery remain authoritative. See SHELL3D_INTEGRATION.md and tests/integration/test_shell3d_api.py for independently executed evidence.
