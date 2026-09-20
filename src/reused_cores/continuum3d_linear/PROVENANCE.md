# Continuum 3D reference snapshot

`reference.py` is an unmodified snapshot of the local `FEA Document/3D-Continuum_Math-Core-Guide/07_可复现验证/reference_continuum3d.py`, resolved from `docs/3D-continuum/AI_CONTENT_INDEX.json`. SHA-256 is recorded in SOURCE_MANIFEST.json. The source package is retained unchanged. There is no runtime import from another checkout or docs.

Scope: small-strain isotropic linear static Tet4 and 2×2×2 full-integration Hex8. Voigt order xx, yy, zz, xy, yz, zx uses engineering shear; J has physical rows and natural columns; reactions are Ku−F. Native integration-point stress is authoritative. The host adapter fixes Hex8 integration to order 2, validates topology/loads, bounds resources, and supplies product recovery and checks.

Reference-package checks alone are not product evidence. Dedicated host tests exercise nonempty solves and analytical solutions. No claim of production certification, nonlinear solids, reduced integration, contact, dynamics, or locking removal is made. Positive Jacobians at sampled points do not certify a warped element everywhere.
