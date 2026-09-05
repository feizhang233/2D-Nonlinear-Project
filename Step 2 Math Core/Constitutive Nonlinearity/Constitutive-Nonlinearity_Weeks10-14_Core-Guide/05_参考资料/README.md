# 参考资料阅读导航

## 1. de Borst 等：Non-linear Finite Element Analysis of Solids and Structures, 2nd ed.

包内稳定文件名：

```text
deBorst_et_al_2012_Nonlinear_FEA_2e.pdf
```

与本包直接相关的 PDF 页路由：

| 主题 | 原书标题 | PDF 页 |
|---|---|---:|
| 弹塑性直观、加性分解 | 7.1 A Simple Slip Model | 235-239 |
| 屈服函数与流动法则 | 7.2-7.2.2 Flow Theory / Yield / Flow Rule | 239-248 |
| 各向同性与随动硬化 | 7.2.3 Hardening Behaviour | 248-254 |
| 返回映射和后向 Euler | 7.3 Integration of the Stress-strain Relation | 255-265 |
| 随动硬化离散方程 | Box 7.3 Von Mises Plasticity with Kinematic Hardening | 259-260 |
| 径向返回、稳定和 substepping | 7.3 后半 | 263-265 |
| 一致算法切线 | 7.4 Tangent Stiffness Operators | 265-268 |
| J2 各向同性硬化切线 | Box 7.6 | 267 |
| 对称/非对称离散切线 | Box 7.7 | 268 |
| 多屈服面和角点 | 7.5 | 268-283 |
| 体积锁死与单元技术 | 7.8 | 287-293 |

推荐顺序：先读 235-254 的模型结构，再读 255-268 的积分和切线。角点、多面和锁死用于理解当前简化核心的边界，不应直接拼接到 J2 代码。

## 2. Bonet 等：Worked Examples in Nonlinear Continuum Mechanics for FEA

包内稳定文件名：

```text
Bonet_et_al_2012_Worked_Examples_Nonlinear_Continuum.pdf
```

直接相关的扩展页：

| 主题 | 原书标题 | PDF 页 |
|---|---|---:|
| 有限应变弹塑性公式摘要 | Chapter 7 Large Elasto-plastic Deformations | 105-106 |
| `F=Fe Fp` 与塑性速度梯度 | Examples 7.1-7.3 | 106-109 |
| 自由能与塑性耗散 | Example 7.4 | 109-110 |

这些页用于说明从小应变升级到有限应变时必须重建的理论对象。本包没有实现其中的有限应变算法。

## 3. 使用边界

- PDF 是来源导航，不是规范代码接口；规范接口以 `01_核心算法` 为准。
- 页码采用 PDF 文件页码，不是纸书印刷页码。
- 公式转写需同时核对符号、应力/应变度量、硬化变量和适用构形。
- 参考资料仅供当前学习与研究使用；不要从本包批量传播全文。
