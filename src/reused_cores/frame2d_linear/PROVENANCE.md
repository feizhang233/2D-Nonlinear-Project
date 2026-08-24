# Reused frame2d linear primitives

Source project: `/Users/zhangfei/Documents/Codex/2D-Frame-Project`

Source commit: `b8276a1ced4fd5a2913efb23c981f4ec43e59f6e`

Source package: `frame2d==0.2.0`

The sibling source files were clean at capture time. P9 retains only the validated `Node`,
`FrameElement`, and `NodalLoad` records plus reference geometry, transformation, and linear local
stiffness conventions. The nonlinear corotational mathematics is not copied from that project.

Original source SHA-256 values:

- `models.py`: `cdf3016a8f41570b26468dabfb2dcb0abd4f70eeaff9996c5d051524c035cdf5`
- `geometry.py`: `dd3f7f7e553e95f6f8c321261e8f94e7371f384b92b9c77310fc66e033d34195`
- `transformation.py`: `77f811567768d82d44de5f8c31ef246bc800d28fd01086bb0f4a696a95748c07`
- `stiffness.py`: `2b0c8bbf291961d9f71e544497d99bfca3fa4deddbc9fc16c645d84c65307fd0`

The retained files are deliberately isolated under `reused_cores/frame2d_linear` so the inherited
linear conventions cannot be confused with the new P9 corotational element.
