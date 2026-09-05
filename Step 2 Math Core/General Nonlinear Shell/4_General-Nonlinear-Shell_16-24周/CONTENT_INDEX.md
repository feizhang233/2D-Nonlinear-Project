# 内容索引

## A. 快速入口

| ID | 内容 | 文件 | 适用问题 |
|---|---|---|---|
| G00 | 范围、目录、完成边界 | `README.md` | 第一次进入专题包 |
| G01 | 目录级强制规则 | `AGENTS.md` | AI 修改算法、测试或结论前 |
| G02 | AI 路由、符号、职责和禁止推断 | `AI_USAGE.md` | 回答或改代码前 |
| G03 | 人类可读内容索引 | `CONTENT_INDEX.md` | 快速定位文件和测试 |
| A01 | 核心算法与实现顺序 | `01_核心算法/核心算法与实现顺序.md` | 运动学、TL/UL、残量、材料、载荷和求解 |
| L01 | 算法局限与适用边界 | `02_算法局限/算法局限与适用边界.md` | 适用性评审、失败诊断 |
| Q01 | V00-V14 验证题目 | `03_验证题目与答案/验证题目.md` | 独立推导和测试输入 |
| S01 | V00-V14 配套答案 | `03_验证题目与答案/配套答案.md` | 数值、公式和证据核对 |
| V01 | 验证矩阵与阶段闸门 | `03_验证题目与答案/验证矩阵.md` | CI、回归、研究门槛 |
| R00 | 参考资料导航 | `04_参考资料/README.md` | 原书页码和使用边界 |
| M01 | 来源与范围映射 | `05_来源映射/参考资料与范围映射.md` | 追溯公式和综合内容 |
| M02 | P08 机器章节映射 | `05_来源映射/P08_核心章节映射.jsonl` | 按阅读顺序检索原书 |
| P01 | 16/20/24 周路线 | `06_学习路线/16-24周学习路线.md` | 学习与实现排期 |
| T01 | 包结构验证脚本 | `07_可复现脚本/validate_package.py` | 检查 JSON、链接、题答配对、清单 |
| C01 | Python 数学核心入口 | `08_Python数学核心/README.md` | 运行 L0 数学底座、测试和题目演算 |
| C02 | V00-V14 演算报告 | `08_Python数学核心/artifacts/V00-V14_演算报告.md` | 查看逐题数值、状态和未完成门槛 |
| C03 | V00-V14 机器结果 | `08_Python数学核心/artifacts/V00-V14_演算结果.json` | 自动读取计算值、状态和边界 |

## B. 核心算法章节路由

| 主题 | 章节 |
|---|---|
| 目标、壳模型边界 | 0-1 |
| 中面、director 与有限转动 | 2-3 |
| TL/UL 与功共轭 | 4 |
| 弱式、残量和切线 | 5-7 |
| 厚度积分、平面应力、材料状态 | 8-9 |
| 随动力和载荷刚度 | 10 |
| MITC、锁死、钻转和稳定化 | 11 |
| Newton、弧长和失稳路径 | 12 |
| 数据接口、伪代码和实施顺序 | 13-15 |

## C. 验证题与答案配对

| Test ID | 主题 | 最低层级 |
|---|---|---|
| V00 | `SO(3)` 指数更新 | 数学单元 |
| V01 | 有限刚体运动零应变 | 壳运动学 |
| V02 | 应变客观性 | 连续体运动学 |
| V03 | TL/UL 应力转换 | 构形一致性 |
| V04 | 总切线方向差分 | 残量/切线 |
| V05 | 随形压力载荷切线 | 外载线性化 |
| V06 | 线弹性厚度积分 | 壳截面 |
| V07 | 弹塑性材料点与一致切线 | 材料状态 |
| V08 | 平面应力静力凝聚 | 壳本构 |
| V09 | 薄壳锁死与稳定化扫描 | 壳单元 |
| V10 | 大转动纯弯曲条带 | 单元/结构 |
| V11 | 弧长跨越极限点 | 路径跟踪 |
| V12 | 失败步回滚 | 状态事务 |
| V13 | 大变形弹塑性方板 | 系统基准 |
| V14 | GMNIA 结论证据审查 | 研究/工程 |

题目均在 `验证题目.md#vNN`，答案均在 `配套答案.md#vNN`。

可执行结果在 `08_Python数学核心/artifacts/`。`VERIFIED` 只表示报告注明的数学层级通过；`FAILED` 表示已执行但未通过，不能与 `NOT_RUN` 混淆；`PARTIAL`、`REFERENCE_ONLY`、`NOT_RUN` 不得提升为完整壳单元或系统验证。单题完成度与 G0-G7 阶段闸门分别报告。

## D. 原书页码路由

| 目标 | 资料 | PDF 页 |
|---|---|---:|
| 壳面几何与壳模型 | Chapelle-Bathe | 33-50、93-109 |
| 一般壳单元、锁死困难、MITC | Chapelle-Bathe | 190-216、262-301 |
| 非线性壳增量、director 与示例 | Chapelle-Bathe | 302-312 |
| TL/UL、应力度量、几何非线性 | de Borst | 86-118 |
| Newton、线搜索、弧长、稳定性 | de Borst | 131-158 |
| 塑性积分与算法切线 | de Borst | 235-267 |
| 壳、壳塑性、超弹性、大应变塑性 | de Borst | 358-438 |
| 运动学、客观率、超弹性和塑性例题 | Bonet | 54-110 |
| 内外虚功线性化与离散切线 | Bonet | 111-138 |
| 退化曲壳、厚度积分和假定应变基线 | Oñate | 636-687 |

## E. 搜索关键词

- 几何：`midsurface`, `director`, `shell thickness`, `degenerate shell`；
- 旋转：`SO(3)`, `exponential map`, `finite rotation`, `objective`；
- 构形：`Total Lagrangian`, `Updated Lagrangian`, `push-forward`, `pull-back`；
- 切线：`consistent tangent`, `material stiffness`, `geometric stiffness`, `load stiffness`；
- 材料：`plane stress condensation`, `return mapping`, `algorithmic tangent`, `thickness integration`；
- 载荷：`follower pressure`, `configuration dependent load`, `nonsymmetric tangent`；
- 单元：`MITC`, `assumed strain`, `locking`, `drilling rotation`, `hourglass`；
- 路径：`Newton`, `line search`, `arc length`, `snap-through`, `postbuckling`, `GMNIA`。
