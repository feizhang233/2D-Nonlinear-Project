# 内容索引

## A. 快速入口

| ID | 内容 | 文件 | 适用问题 |
|---|---|---|---|
| G02 | 目录级 AI 工作规则 | `AGENTS.md` | AI 在资料包内新增或修改内容时 |
| G00 | 范围、目录和完成边界 | `README.md` | 第一次进入资料包 |
| G01 | AI 读取、符号和职责规则 | `AI_USAGE.md` | 回答或改代码前 |
| A01 | 数学模型与实现主线 | `01_核心算法/核心算法与实现顺序.md` | 残量、Newton、状态、控制和弧长 |
| L01 | 局限、风险和升级门槛 | `02_算法局限/算法局限与适用边界.md` | 诊断不收敛、评审适用性 |
| Q01 | 独立验证题 | `03_验证题目与答案/验证题目.md` | 编写测试前 |
| S01 | 配套答案和参考值 | `03_验证题目与答案/配套答案.md` | 完成题目后核对 |
| V01 | 完整验证矩阵 | `03_验证题目与答案/验证矩阵.md` | CI、回归、合并门槛 |
| R00 | 参考资料阅读导航 | `04_参考资料/README.md` | 查原书页码和使用边界 |
| R01 | de Borst 等非线性 FEA | `04_参考资料/deBorst_et_al_2012_Nonlinear_FEA_2e.pdf` | 求解器、控制、弧长、稳定性 |
| R02 | Bonet 等 Worked Examples | `04_参考资料/Bonet_et_al_2012_Worked_Examples_Nonlinear_Continuum.pdf` | 解析题、方向导数和离散算例 |
| M01 | 参考资料和范围映射 | `05_来源映射/参考资料与范围映射.md` | 追溯公式、确认排除范围 |
| M02 | P05 机器可读章节映射 | `05_来源映射/P05_章节映射.jsonl` | AI 按项目阶段检索原书章节 |

## B. 核心算法章节路由

| 目标 | 核心算法章节 |
|---|---|
| 范围、残量和切线符号 | 0-1 |
| 求解器/单元/材料接口 | 2 |
| 2D 有限变形桥接 | 3 |
| 增量-迭代与 Newton | 4-5 |
| trial/commit/rollback | 6 |
| 收敛判据 | 7 |
| 荷载控制 | 8 |
| 位移控制与反力 | 9 |
| 线搜索 | 10 |
| 球形弧长 | 11 |
| 步长、失败和输出 | 12-13 |

## C. 验证题与答案配对

| Test ID | 题目位置 | 答案位置 | 主要模块 |
|---|---|---|---|
| V00 | `验证题目.md#v00` | `配套答案.md#v00` | 2D 有限转动客观性 |
| V01 | `验证题目.md#v01` | `配套答案.md#v01` | 残量符号、线性一步恢复 |
| V02 | `验证题目.md#v02` | `配套答案.md#v02` | 一致切线、方向差分 |
| V03 | `验证题目.md#v03` | `配套答案.md#v03` | Newton、不完美柱 |
| V04 | `验证题目.md#v04` | `配套答案.md#v04` | 极限点、控制方式 |
| V05 | `验证题目.md#v05` | `配套答案.md#v05` | 位移控制、反力 |
| V06 | `验证题目.md#v06` | `配套答案.md#v06` | 线搜索正交 |
| V07 | `验证题目.md#v07` | `配套答案.md#v07` | trial/commit/rollback |
| V08 | `验证题目.md#v08` | `配套答案.md#v08` | 球形弧长、根选择 |
| V09 | `验证题目.md#v09` | `配套答案.md#v09` | 2D 模型集成门槛 |

## D. 原书页码路由

| 目标 | 参考资料 | PDF 页 |
|---|---|---:|
| 平衡、离散、增量-迭代 | de Borst 等，第 2 章 | 50-68 |
| 荷载/位移控制 | de Borst 等，2.5 | 69-71 |
| 线搜索 | de Borst 等，4.1 | 131-133 |
| 弧长法 | de Borst 等，4.2 | 134-141 |
| Riks 实现 | de Borst 等，4.3 | 142-146 |
| 稳定、分岔、branch switching | de Borst 等，4.4 | 147-152 |
| 步长、收敛、拟 Newton | de Borst 等，4.5-4.6 | 152-158 |
| 杆-弹簧与不完美柱 | Bonet 等，第 1 章 | 11-18 |
| 平衡方程线性化 | Bonet 等，第 8 章 | 111-122 |
| 离散、切线与线搜索例题 | Bonet 等，第 9 章 | 123-138 |

## E. 搜索关键词

- 平衡与切线：`residual`, `internal force`, `consistent tangent`, `directional derivative`；
- 求解：`Newton-Raphson`, `modified Newton`, `convergence radius`, `cutback`；
- 控制：`load control`, `displacement control`, `line search`, `arc length`, `Riks`；
- 状态：`trial state`, `commit`, `rollback`, `restart`, `path dependent`；
- 失稳：`limit point`, `snap-through`, `snap-back`, `bifurcation`, `branch switching`；
- 二维接口：`deformation gradient`, `detF`, `objectivity`, `Total Lagrangian`, `follower load`；
- 验证：`one-step linear recovery`, `finite difference tangent`, `reaction`, `root continuity`。
