# Space-frame reference core

Copied on 2026-09-19 from the local `2D-Frame-Project/src/frame3d` implementation.
`SOURCE_MANIFEST.json` records the original source SHA-256 values. Relative imports
keep this package self-contained; the reference checkout is never required at runtime.
The core is linear elastic, small displacement/rotation, straight prismatic beams.
Six DOFs per node: u, v, w, rx, ry, rz. Local x follows i to j; the reference vector
sets local y, and z = x cross y. Iy, Iz and torsional J are independent properties.
The host API adds bounded resource use and the Nonlinear Studio error envelope.
The standalone reference API is retained for numerical compatibility testing.

Host adaptations: source formatting/import ordering and explicit zip length handling.
No stiffness, load, recovery, or solver formula was replaced.
