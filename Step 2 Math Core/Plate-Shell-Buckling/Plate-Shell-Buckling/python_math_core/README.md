# Plate-Shell Buckling Python 数学核心

本目录把上级知识包中的核心公式转成可运行、可测试的 Python 参考实现，并直接演算 `V10-V22`。

## 分析范围

- `LBA`：线性预屈曲平衡、压缩削弱正矩阵 `K_G`、对称广义特征值、板/圆柱/球壳解析基准、MAC 与近重根子空间。
- `GNA`：一自由度分岔、浅两杆拱、球形弧长 Newton、根方向连续、失败回滚与步长缩减。
- `GNIA` 准备：法向平移模态到有长度单位缺陷的映射，以及 Koiter `2/3` 次方折减律。
- `GMNIA`：只提供分析层级路由，不实现塑性、残余应力、接触或材料状态回滚。

这是一套稠密参考数学核心，不是通用曲壳有限元。上级资料明确排除了生产屈曲求解器和通用壳单元；因此代码没有虚构 `B_g`、曲壳运动学或材料模型。对于有限元输入，核心只提供受约束预屈曲平衡、薄板 `K_G=∫B_g^T N B_g dA` 积分与方向差分检查。

## 固定正号

平衡残量采用：

```text
r(q, λ) = f_int(q) - λ f_ref = 0
```

LBA 采用“压缩削弱正矩阵”写法：

```text
K_M φ = λ K_G φ
K_G = -K_σ,ref
```

板膜力输入中压缩为正。求解器保留负特征值的符号，不做绝对值排序。

## 目录

```text
plate_shell_buckling_core/
  contracts.py       分析层级、结论边界和正号契约
  lba.py             预屈曲、K_G、特征值、板/圆柱/球壳解析核心
  modes.py           归一化、MAC、主夹角、近重根和可执行伪模态诊断
  imperfections.py   有单位缺陷映射、应用后几何检查、刚体投影和 Koiter 折减
  nonlinear.py       分岔、浅两杆拱和球形弧长
  verification.py    V10-V22 实际演算与验收
tests/                Python 标准库 unittest 独立测试
results/              JSON、中文演算报告和 V21 完整弧长路径 CSV
```

## 运行

从本目录运行，不需要安装包：

```bash
python3 -m unittest discover -s tests -v
python3 -m plate_shell_buckling_core
python3 -m plate_shell_buckling_core --format json
python3 -m plate_shell_buckling_core --format markdown
```

系统需要 Python 3.11+ 和 NumPy。测试使用 Python 标准库 `unittest`，不依赖 pytest。

## 题目映射

| 题目 | Python 入口 | 层级 |
|---|---|---|
| V10 | `quartic_potential_bifurcation` | GNA 基础 |
| V11 | `solve_linear_prebuckling`、`recover_membrane_forces`、`integrate_plate_geometric_stiffness`、`directional_tangent_curve` | LBA |
| V12 | `solve_generalized_buckling` | LBA |
| V13-V14 | `uniaxial_rectangular_plate`、`biaxial_rectangular_plate` | LBA |
| V15 | `pure_shear_square_plate` | LBA |
| V16 | `cylindrical_shell_classical` | LBA |
| V17 | `mac`、`subspace_principal_angles`、`group_repeated_eigenvalues`、`diagnose_mode` | LBA |
| V18 | `map_normal_imperfection`、`apply_normal_imperfection`、`project_out_rigid_body_motion` | GNIA 准备 |
| V19 | `koiter_two_thirds` | GNIA |
| V20 | `TwoBarArch.limit_point` | GNA |
| V21 | `trace_spherical_arc_length`、`run_arch_step_sensitivity` | GNA/GNIA |
| V22 | `analysis_level_for` | 全层级 |

## 证据边界

结果使用两类状态：

- `ANALYTICAL_PASS`：解析式或截断数学基准通过；
- `REFERENCE_CORE_PASS`：本 Python 稠密参考算法及其反例/敏感性检查通过。

两类状态都不代表生产有限元闸门、任意网格、商业软件模型或工程设计已经通过。当前证据包明确记录 `production_fe_gate_claimed: false`。线性特征值也不能直接解释成实际极限载重或规范设计强度。

V21 的 `Δs=1` 完整路径位于 `results/v21_arc_path_ds1.csv`，包含每一步载重、位移、残量、弧长误差、迭代数、预测根和最低切线特征值。
