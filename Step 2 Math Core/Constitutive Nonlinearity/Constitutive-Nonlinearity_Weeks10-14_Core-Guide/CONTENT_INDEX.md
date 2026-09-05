# 内容索引

## A. 快速入口

| ID | 内容 | 文件 | 适用问题 |
|---|---|---|---|
| G00 | 范围、目录和完成边界 | `README.md` | 第一次进入资料包 |
| G01 | 后续 AI 路由与禁止推断 | `AI_USAGE.md` | 回答、实现或评审前 |
| G02 | 目录级强制工作规则 | `AGENTS.md` | AI 在包内修改内容时 |
| G03 | 人类可读内容索引 | `CONTENT_INDEX.md` | 快速查文件、验证和来源 |
| G04 | 机器可读索引 | `AI_CONTENT_INDEX.json` | 后续 AI 自动路由 |
| A00 | 五周依赖、材料接口和事务 | `01_核心算法/00_五周总览与材料接口.md` | 接口设计、职责和实现顺序 |
| A10 | W10 状态变量与框架 | `01_核心算法/W10_状态变量与本构框架.md` | KKT、历史变量、耗散 |
| A11 | W11 一维隐式积分 | `01_核心算法/W11_一维隐式塑性积分.md` | predictor-corrector、局部 Newton |
| A12 | W12 J2 径向返回 | `01_核心算法/W12_J2径向返回算法.md` | 3D J2、`3G+H`、状态更新 |
| A13 | W13 一致切线与平面应力 | `01_核心算法/W13_一致切线与平面应力.md` | 方向导数、Schur 凝聚 |
| A14 | W14 循环与组合硬化 | `01_核心算法/W14_循环加载与组合硬化.md` | 反向屈服、Bauschinger、路径回归 |
| L01 | 局限和升级边界 | `02_算法局限/算法局限与升级边界.md` | 判断模型是否适用 |
| Q01 | V00-V11 独立题目 | `03_验证题目与答案/验证题目.md` | 编写测试前 |
| S01 | V00-V11 配套答案 | `03_验证题目与答案/配套答案.md` | 完题后核对 |
| S02 | V00-V11 Python 演算报告 | `03_验证题目与答案/Python演算校验报告.md` | 查看实际执行值和 PASS 证据 |
| V01 | 分层验证矩阵 | `03_验证题目与答案/验证矩阵.md` | CI、回归和合并门槛 |
| X00 | 可复现算例说明 | `04_可复现算例/README.md` | 运行和修改参考脚本 |
| X01 | 独立材料点参考脚本 | `04_可复现算例/reference_material_point.py` | 重算 V00-V11 数值 |
| X02 | 整包自动校验脚本 | `04_可复现算例/validate_package.py` | 检查索引、来源路由、题答配对和全部演算 |
| R00 | PDF 阅读导航 | `05_参考资料/README.md` | 查原书完整上下文 |
| R01 | de Borst 非线性 FEA | `05_参考资料/deBorst_et_al_2012_Nonlinear_FEA_2e.pdf` | 小应变塑性、积分、切线、局限 |
| R02 | Bonet 非线性连续体算例 | `05_参考资料/Bonet_et_al_2012_Worked_Examples_Nonlinear_Continuum.pdf` | 有限应变升级边界 |
| M01 | 人类可读来源映射 | `06_来源映射/公式与页码映射.md` | 公式追溯与适用范围 |
| M02 | 机器可读来源映射 | `06_来源映射/source_map.jsonl` | AI 按主题定位原书页 |

## B. 五周路由

| 周次 | 先读 | 验证 | 原书页 |
|---|---|---|---|
| W10 | A00、A10 | V00、V07 | de Borst PDF 235-254 |
| W11 | A11 | V01、V02、V10 | de Borst PDF 255-265 |
| W12 | A12 | V03-V05 | de Borst PDF 263-267 |
| W13 | A13 | V06、V09、V11 | de Borst PDF 265-268 |
| W14 | A14 | V02、V07、V08 | de Borst PDF 248-260 |

## C. 问题路由

| 问题 | 最小读取集 |
|---|---|
| 为什么塑性变量不能在迭代中直接覆盖？ | A00 + A10 + V07 |
| 一维返回分母与切线是什么？ | A11 + V01 |
| J2 为什么是 `3G+H`？ | A12 第 3-4 节 + V04 |
| `q`、`s` 和 `alpha` 如何定义？ | A10 + A12 |
| 如何判断切线真正一致？ | A13 第 1-3 节 + V06 |
| plane strain 与 plane stress 有何不同？ | A13 第 4-6 节 + V09 |
| 反向屈服怎么算？ | A14 第 2-3 节 + V08 |
| 为什么线性组合硬化不能代表完整循环塑性？ | A14 第 7 节 + L01 第 9 节 |
| 非线性硬化局部 Newton 怎么保护？ | A11 第 5 节 + V10 |
| 材料切线如何接全局 Newton？ | A00 + A13 + V11 |
| 何时必须升级有限应变？ | L01 第 3、15 节 + R02 |
| 软化为什么网格依赖？ | L01 第 10 节 |

## D. 验证题与答案配对

| Test ID | 题目 | 答案 | 主要模块 |
|---|---|---|---|
| V00 | `验证题目.md#v00---弹性分支与零状态` | `配套答案.md#v00---弹性分支与零状态` | 弹性、初始状态 |
| V01 | `验证题目.md#v01---一维线性硬化闭式返回` | `配套答案.md#v01---一维线性硬化闭式返回` | 1D 返回 |
| V02 | `验证题目.md#v02---弹性卸载和状态保持` | `配套答案.md#v02---弹性卸载和状态保持` | 卸载状态 |
| V03 | `验证题目.md#v03---j2-静水不变性` | `配套答案.md#v03---j2-静水不变性` | J2 不变量 |
| V04 | `验证题目.md#v04---3d-j2-单步径向返回` | `配套答案.md#v04---3d-j2-单步径向返回` | 径向返回 |
| V05 | `验证题目.md#v05---塑性不可压缩kkt-与耗散` | `配套答案.md#v05---塑性不可压缩kkt-与耗散` | 物理约束 |
| V06 | `验证题目.md#v06---一致切线方向导数` | `配套答案.md#v06---一致切线方向导数` | 算法切线 |
| V07 | `验证题目.md#v07---trial--rollback--commit` | `配套答案.md#v07---trial--rollback--commit` | 状态事务 |
| V08 | `验证题目.md#v08---组合硬化循环历史` | `配套答案.md#v08---组合硬化循环历史` | 循环加载 |
| V09 | `验证题目.md#v09---平面应力局部约束` | `配套答案.md#v09---平面应力局部约束` | plane stress |
| V10 | `验证题目.md#v10---voce-非线性硬化局部-newton` | `配套答案.md#v10---voce-非线性硬化局部-newton` | 局部 Newton |
| V11 | `验证题目.md#v11---材料点与全局-newton-的一自由度连接` | `配套答案.md#v11---材料点与全局-newton-的一自由度连接` | 全局耦合 |

## E. 原书页码路由

| 目标 | 资料 | PDF 页 |
|---|---|---:|
| 小应变弹塑性结构 | R01 | 235-249 |
| 流动和硬化 | R01 | 244-254 |
| 隐式返回映射 | R01 | 255-265 |
| 随动硬化示例 | R01 | 259-260 |
| 径向返回 | R01 | 263-267 |
| 一致切线 | R01 | 265-268 |
| 多屈服面与角点 | R01 | 268-283 |
| 体积锁死 | R01 | 287-293 |
| 有限应变乘法弹塑性 | R02 | 105-109 |
| 有限应变耗散 | R02 | 109-110 |

## F. 搜索关键词

- 本构框架：`constitutive update`, `material point`, `Gauss point`, `internal variable`, `state variable`；
- 塑性积分：`elastic predictor`, `plastic corrector`, `backward Euler`, `return mapping`, `radial return`；
- J2：`von Mises`, `deviatoric stress`, `equivalent stress`, `plastic multiplier`, `3G+H`；
- 切线：`consistent tangent`, `algorithmic tangent`, `directional derivative`, `Schur complement`；
- 状态：`trial`, `committed`, `rollback`, `restart`, `history variable`；
- 循环：`cyclic loading`, `Bauschinger`, `kinematic hardening`, `backstress`, `ratcheting`, `Chaboche`；
- 局限：`finite strain`, `pressure sensitive`, `non-associated`, `softening`, `localization`, `volumetric locking`；
- 中文：`塑性积分`、`状态变量`、`一致切线`、`循环加载`、`随动硬化`、`反向屈服`。
