# 内容索引

## A. 快速入口

| ID | 文件 | 用途 | 优先级 |
|---|---|---|---:|
| G00 | `README.md` | 范围、目录、最短读取路径和完成边界 | 1 |
| G01 | `AGENTS.md` | 目录级 AI 强制规则 | 1 |
| G02 | `AI_USAGE.md` | 任务路由、术语、符号和禁止推断 | 1 |
| G03 | `AI_CONTENT_INDEX.json` | 机器可读内容、验证和来源路由 | 1 |
| A01 | `01_核心算法/核心算法与实现顺序.md` | 极限点、分岔、特征屈曲、弧长、Koiter、多模态、缺陷和分支切换 | 1 |
| L01 | `02_算法局限/算法局限与适用边界.md` | 数学、离散、求解、实验和工程边界 | 1 |
| Q01 | `03_验证题目与答案/验证题目.md` | V00-V10 独立题目 | 1 |
| S01 | `03_验证题目与答案/配套答案.md` | V00-V10 数值/证据答案 | 1 |
| V01 | `03_验证题目与答案/验证矩阵.md` | 自动化顺序和接受准则 | 1 |
| P01 | `07_学习路线/8-12周研究路线.md` | 10 周主线、8 周压缩、12 周扩展 | 1 |
| R00 | `04_完整参考/Shell_Instability_Research_完整數學邏輯推導與例題_繁中.pdf` | 30 页主讲义 | 1 |
| R01 | `04_完整参考/Plate_Shell_Buckling_完整數學推導與例題_繁中.pdf` | 19 页线性屈曲前置讲义 | 2 |
| B00 | `05_参考资料/README.md` | 四本原书阅读导航 | 2 |
| B07 | `05_参考资料/Koiter_Elastic_Stability.pdf` | Koiter 单/多模态与缺陷主来源 | 2 |
| B04 | `05_参考资料/deBorst_Nonlinear_FEA_2e.pdf` | 特征屈曲、弧长、分类和分支切换 | 2 |
| B06 | `05_参考资料/Timoshenko_Gere_Theory_of_Elastic_Stability.pdf` | 经典板壳基准和试验背景 | 3 |
| B03 | `05_参考资料/Chapelle_Bathe_FEA_of_Shells.pdf` | 壳厚度渐近、纯弯曲和非线性分析衔接 | 3 |
| M01 | `06_来源映射/参考资料与范围映射.md` | 工作区来源、综合内容和排除边界 | 2 |
| M02 | `06_来源映射/P07_核心章节映射.jsonl` | 机器可读页码和主题路由 | 2 |
| C00 | `08_可复现脚本/README.md` | 脚本运行和覆盖风险 | 2 |
| C01 | `08_可复现脚本/generate_shell_instability_research_pdf.py` | 主讲义生成器副本 | 3 |
| C02 | `08_可复现脚本/generate_plate_shell_buckling_pdf.py` | 前置讲义生成器副本 | 3 |
| C03 | `09_Python数学核心/README.md` | Python 数学核心、运行契约和边界 | 1 |
| C04 | `09_Python数学核心/run_validation_problems.py` | V00-V10 自动演算入口 | 1 |
| C05 | `09_Python数学核心/output/V00-V10_演算结果.md` | 逐题数值、误差与验收证据 | 1 |
| H01 | `FILE_MANIFEST.sha256` | PDF 和脚本复制件的 SHA-256 完整性校验 | 2 |

## B. 核心算法章节路由

| 目标 | A01 章节 | 验证 |
|---|---:|---|
| 残量、势能和稳定 | 0-1 | V00 |
| 临界点定位 | 2 | V00、V10 |
| 极限点/分岔分类 | 3 | V01 |
| 线性特征屈曲 | 4 | V02、V08、V09 |
| 弧长跨越极限点 | 5 | V06 |
| 单模态 Koiter | 6 | V03 |
| 模态交互和模态簇 | 7 | V04 |
| 缺陷敏感性 | 8 | V05、V10 |
| 分支切换 | 9 | V07、V10 |
| 端到端流程和输出 | 10-11 | V00-V10 |

## C. 验证题与答案配对

| ID | 题目 | 答案 | 核心参考值/证据 |
|---|---|---|---|
| V00 | Q01 V00 | S01 V00 | `Kp=(0.202,-0.744)`；中心差分二阶区 |
| V01 | Q01 V01 | S01 V01 | `psi^T f_ref` 区分极限/分岔 |
| V02 | Q01 V02 | S01 V02 | `lambda1=7.1494134`、`lambda2=20.6766736` |
| V03 | Q01 V03 | S01 V03 | 超/次临界 Hessian `+0.8/-0.8` |
| V04 | Q01 V04 | S01 V04 | 混合分支能量 `-0.0133333`；Hessian 正定 |
| V05 | Q01 V05 | S01 V05 | 缺陷折减对数斜率 `2/3` |
| V06 | Q01 V06 | S01 V06 | 弧长交点 `(0.5995912434,0.3840323999)` |
| V07 | Q01 V07 | S01 V07 | 正交种子 `(0,-1)`，仍需全阶校正 |
| V08 | Q01 V08 | S01 V08 | 圆柱 `sigma_cr=85.625710 MPa` |
| V09 | Q01 V09 | S01 V09 | 球壳 `p_cr=0.34250284 MPa` |
| V10 | Q01 V10 | S01 V10 | 八类端到端证据 |

## D. 原书页码路由

| 目标 | 文件 | PDF 页 |
|---|---|---:|
| 稳定和二次变分 | Koiter | 11-36 |
| 多模态临界空间和高阶张量 | Koiter | 33-45 |
| 单模态分岔和局部稳定 | Koiter | 42-50 |
| 缺陷敏感性 | Koiter | 51-56 |
| 浅壳、球壳、圆柱壳与局部缺陷 | Koiter | 176-236 |
| 线性屈曲 | de Borst | 119-121 |
| 弧长和 Riks | de Borst | 134-146 |
| 稳定、唯一性、分岔、分支切换 | de Borst | 147-152 |
| 经典薄板屈曲 | Timoshenko-Gere | 268-333 |
| 经典圆柱/球壳 | Timoshenko-Gere | 347-406 |
| 壳厚度渐近、纯弯曲和锁定背景 | Chapelle-Bathe | 127-181 |
| 非线性壳分析衔接 | Chapelle-Bathe | 302-312 |

## E. 搜索关键词

- 临界分类：`limit point`, `bifurcation`, `left null vector`, `tangent singularity`, `inertia`；
- 路径：`arc length`, `Riks`, `predictor corrector`, `snap-through`, `snap-back`；
- Koiter：`reduced potential`, `A3`, `A4`, `second-order correction`, `critical subspace`；
- 模态交互：`multiple modes`, `mode interaction`, `eigenvalue cluster`, `MAC`, `principal angles`；
- 缺陷：`imperfection sensitivity`, `two-thirds law`, `localized dent`, `measured imperfection`；
- 分支：`branch switching`, `phase condition`, `orthogonality constraint`, `modal seed`；
- 壳基准：`cylindrical shell`, `spherical shell`, `sqrt(Rh)`, `short wave`；
- 验证：`directional derivative`, `mesh convergence`, `step convergence`, `rollback`, `subspace tracking`。

## F. 结论边界速查

| 已有证据 | 允许的最强表述 |
|---|---|
| 只有广义特征值 | 完美基本路径的线性中性条件 |
| 完美结构弧长路径 | 指定模型下的 GNA 路径和临界候选 |
| 指定缺陷 GNIA + 收敛矩阵 | 指定缺陷族下的极限载荷与折减趋势 |
| GMNIA + 实验/统计标定 | 指定模型和数据范围内的工程解释 |

不能跨级表述。
