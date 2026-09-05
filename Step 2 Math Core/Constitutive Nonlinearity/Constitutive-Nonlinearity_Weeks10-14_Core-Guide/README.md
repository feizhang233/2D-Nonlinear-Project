# Constitutive Nonlinearity 第 10-14 周数学核心资料包

## 1. 定位

本目录把工作区中与塑性积分、状态变量、一致算法切线和循环加载有关的内容整理为一个独立、可验证、便于后续 AI 路由的资料包。

本包关注有限元材料点层（material point / Gauss point），与根目录已有的 `2D-Nonlinear-Project_Math-Core-Guide` 形成分工：

- 本包负责 `strain -> stress + algorithmic tangent + trial state`；
- 全局求解器资料包负责残量、Newton、步长、控制、全局收敛和最终 commit/rollback 调度。

## 2. 五周范围

| 周次 | 主线 | 必须产出 |
|---|---|---|
| W10 | 弹塑性框架与状态变量 | 状态模式、屈服/流动/硬化约定、trial/commit/rollback |
| W11 | 一维后向欧拉塑性积分 | elastic predictor / plastic corrector、闭式返回、局部验收 |
| W12 | 小应变 J2 径向返回 | 3D 张量算法、等效塑性应变、耗散与屈服面投影 |
| W13 | 一致算法切线与平面应力 | 方向导数检查、Schur 凝聚、外层 `sigma_zz=0` 局部迭代 |
| W14 | 循环加载与组合硬化 | Bauschinger 效应、反向屈服、滞回状态与循环回归 |

## 3. 规范实现范围

当前可直接实现和验证的主模型是：

- 小应变加性分解；
- 率无关关联流动；
- von Mises / J2 屈服；
- 线性各向同性硬化；
- 循环算例使用一维线性各向同性 + 线性随动组合硬化；
- 后向欧拉返回映射；
- 与离散应力更新一致的算法切线；
- 3D、平面应变，以及通过局部 `sigma_zz=0` 约束得到的平面应力材料点。

## 4. 当前明确不包含

- 有限应变乘法分解 `F = Fe Fp` 的生产实现；
- 非关联 Mohr-Coulomb / Drucker-Prager、角点多屈服面和 active-set；
- Chaboche 多背应力、循环记忆面、平均应力松弛和精确棘轮标定；
- 黏塑性、蠕变、损伤、断裂、接触和动力学；
- 软化材料的非局部、梯度或裂带正则化；
- 温度、孔压、各向异性和多物理耦合；
- 对任意 Voigt 排列和剪切 convention 自动成立的矩阵公式。

这些内容的升级门槛与风险见 `02_算法局限/算法局限与升级边界.md`。

## 5. 最短读取路径

1. `AGENTS.md`：目录级强制约定；
2. `AI_CONTENT_INDEX.json`：机器路由；
3. `AI_USAGE.md`：回答、实现和评审规则；
4. `01_核心算法/00_五周总览与材料接口.md`：材料接口与五周依赖；
5. 按任务读取 W10-W14 对应文件；
6. `02_算法局限/算法局限与升级边界.md`：使用边界；
7. `03_验证题目与答案/验证矩阵.md`：最低回归门槛；
8. `04_可复现算例/reference_material_point.py`：独立重算参考值；
9. `04_可复现算例/validate_package.py`：一次检查题答、来源映射和全部数值门槛；
10. 需要原始出处时读取 `06_来源映射/公式与页码映射.md` 和参考 PDF 对应页。

## 6. 目录结构

```text
Constitutive-Nonlinearity_Weeks10-14_Core-Guide/
├── AGENTS.md
├── README.md
├── AI_USAGE.md
├── CONTENT_INDEX.md
├── AI_CONTENT_INDEX.json
├── 01_核心算法/
│   ├── 00_五周总览与材料接口.md
│   ├── W10_状态变量与本构框架.md
│   ├── W11_一维隐式塑性积分.md
│   ├── W12_J2径向返回算法.md
│   ├── W13_一致切线与平面应力.md
│   └── W14_循环加载与组合硬化.md
├── 02_算法局限/
│   └── 算法局限与升级边界.md
├── 03_验证题目与答案/
│   ├── 验证题目.md
│   ├── 配套答案.md
│   ├── Python演算校验报告.md
│   └── 验证矩阵.md
├── 04_可复现算例/
│   ├── README.md
│   ├── reference_material_point.py
│   └── validate_package.py
├── 05_参考资料/
│   ├── README.md
│   ├── deBorst_et_al_2012_Nonlinear_FEA_2e.pdf
│   └── Bonet_et_al_2012_Worked_Examples_Nonlinear_Continuum.pdf
└── 06_来源映射/
    ├── 公式与页码映射.md
    └── source_map.jsonl
```

## 7. 完成边界

本次交付是数学核心、实现契约和可复现验证基线，不是完整材料库代码。后续实现应从一维材料点开始，经 J2、切线方向导数、状态回滚和循环历史逐层验收，再接入有限元全局 Newton。

当前包的统一验收命令为：

```bash
python3 04_可复现算例/validate_package.py
```
