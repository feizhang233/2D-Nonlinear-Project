# General Nonlinear Shell Python 数学核心

## 1. 定位

本目录把上级资料中的 V00-V14 转换为可执行的 Python 数学底座、自动测试和演算报告。当前版本为 `0.2.0`。默认约定与上级算法合同一致：

- 残量：`r = f_ext - f_int`；
- 切线：`K_t = ∂f_int/∂q - ∂f_ext/∂q`；
- 有限转动：空间增量左乘 `R_new = exp([Δθ]x) R_old`；
- 状态：全局迭代只生成 trial，只有收敛后才 commit，失败时 rollback。

这是验证型 L0 数学核心，不是生产级一般非线性壳单元。它不会把解析条带、二维压力线或一自由度弧长题冒充 V09/V13 的壳系统结果。

## 2. 已实现

| 模块 | 数学内容 | 对应题目 |
|---|---|---|
| `rotations.py` | `SO(3)` 指数映射、稳定小角度分支、左/右增量、正交性诊断 | V00 |
| `kinematics.py` | Green-Lagrange 应变、小应变对照、TL→UL 应力推前、Q4 中心点壳运动学、有向 Jacobian/反转检查 | V01-V03 |
| `contracts.py` | 材料/几何/旋转/稳定化/外载切线的规范组合 | V04-V05 前置 |
| `tangent.py` | 规范残量负号、多步长中心方向差分 | V04 |
| `loads.py` | 二维随形压力节点力与非对称载荷切线 | V05 |
| `section.py` | Gauss 厚度积分、平面应力 Schur 补 | V06、V08 |
| `materials.py` | 一维双线性硬化返回映射、一致切线、不可变 committed 状态 | V07、V12 前置 |
| `benchmarks.py` | 大转动纯弯曲条带解析参考 | V10 |
| `continuation.py` | 一自由度球形弧长预测-校正 | V11 |
| `state.py` | 节点/director/厚度/材料/平面应力/局部基/稳定化的 trial/commit/rollback 与 SHA256 快照 | V12 |
| `verification.py` | V00-V14 统一执行、分层状态和 JSON/Markdown 报告 | 全部 |

## 3. 可复现命令

先选择任意满足 `Python >= 3.9` 且可导入 NumPy 的解释器。当前工作区已验证的隔离解释器如下；它只是测试运行时，不是本包对相邻项目的代码依赖：

```bash
cd "/Users/zhangfei/Documents/Codex/General Nonlinear Shell/4_General-Nonlinear-Shell_16-24周/08_Python数学核心"
SHELL_MATH_PYTHON="/Users/zhangfei/Documents/Codex/2D-Nonlinear-Project/.venv/bin/python"
"$SHELL_MATH_PYTHON" -c "import sys, numpy; print(sys.version); print(numpy.__version__)"
"$SHELL_MATH_PYTHON" -m unittest discover -s tests -v
"$SHELL_MATH_PYTHON" -m general_nonlinear_shell_math --output artifacts
PYTHONPYCACHEPREFIX=/tmp/general-nonlinear-shell-pycache "$SHELL_MATH_PYTHON" -m compileall -q general_nonlinear_shell_math tests
```

演算输出：

- `artifacts/V00-V14_演算报告.md`：人类可读逐题结果；
- `artifacts/V00-V14_演算结果.json`：机器可读结果、状态和边界。

## 4. 验证状态含义

| 状态 | 含义 |
|---|---|
| `VERIFIED` | 本题在当前数学层级的数值/代数验收通过 |
| `PARTIAL` | 数学底层通过，但完整壳单元/壳面/全局事务仍未具备 |
| `REFERENCE_ONLY` | 解析参考已计算，尚未由真实壳模型复现 |
| `NOT_RUN` | 缺少必要壳单元、网格或数字化参考数据，诚实停止 |
| `AUDIT_RESULT` | 完成证据审查，不代表完成 GMNIA 数值验证 |
| `FAILED` | 题目已经执行，但数值、状态或证据未满足验收；与 `NOT_RUN` 明确区分 |

当前结果：V00、V02、V03、V06、V07、V08、V11、V12 为 `VERIFIED`；V01、V04、V05 为 `PARTIAL`；V10 为 `REFERENCE_ONLY`；V09、V13 为 `NOT_RUN`；V14 的题设结论因证据不足被拒绝；没有 `FAILED`。报告将单题状态与 G0-G7 阶段闸门分开，目前没有任何 G 阶段通过。

## 5. 后续实现门槛

下一阶段若要从 L0 进入真实壳单元，必须先选择并冻结具体的非线性 Reissner-Mindlin/MITC 插值、自由度和积分方案，然后：

1. 将真实单元的材料、几何、旋转、稳定化和随形载荷切线放入 V04 同一次方向差分；
2. 用真实壳面完成 V05；
3. 完成 V09 的厚跨比、规则/畸变网格、积分和稳定化扫描；
4. 用实际条带完成 V10，并把所有节点/director/厚度点历史纳入 V12；
5. 数字化原书第 311 页曲线后再运行 V13；
6. 只有 V00-V14 和模型敏感性矩阵全部具备，才进入 GMNIA 工程结论。
