# 后续 AI 使用规则

## 1. 任务路由

| 用户问题或代码任务 | 首读 | 必须联读 |
|---|---|---|
| 设计材料接口或状态对象 | `01_核心算法/00_五周总览与材料接口.md` | W10、V07 |
| 一维塑性积分 | W11 | V01、V02 |
| 3D J2 / von Mises 返回映射 | W12 | V03-V05 |
| 一致切线、不收敛或方向差分 | W13 | V06、局限第 5 节 |
| 平面应力材料点 | W13 | V09 |
| 循环加载或 Bauschinger 效应 | W14 | V08 |
| 非线性硬化局部 Newton | W11、W12 | V10 |
| 接入全局 Newton | 总览接口、W13 | V07、V11；必要时再读根目录全局求解器资料包 |
| 有限应变、土塑性、损伤或软化 | 先读局限文件 | 不得直接套用当前闭式公式 |

## 2. 规范符号

默认使用小应变张量形式：

$$
\boldsymbol\varepsilon
=\boldsymbol\varepsilon^e+\boldsymbol\varepsilon^p,
\qquad
\boldsymbol\sigma
=\mathbb C^e:(\boldsymbol\varepsilon-\boldsymbol\varepsilon^p).
$$

J2 模型使用：

$$
\mathbf s=\operatorname{dev}(\boldsymbol\sigma),
\qquad
q=\sqrt{\frac32\mathbf s:\mathbf s},
$$

$$
f=q-[\sigma_{y0}+R(\alpha)]\le 0,
\qquad
\Delta\boldsymbol\varepsilon^p
=\Delta\gamma\,\frac{3\mathbf s}{2q},
\qquad
\alpha_{n+1}=\alpha_n+\Delta\gamma.
$$

线性各向同性硬化时 `R(alpha) = H_iso * alpha`。

## 3. 状态和返回值契约

推荐材料函数概念签名：

```text
update(total_strain_np1, committed_state, material, options)
    -> stress_np1
    -> C_alg_np1
    -> trial_state_np1
    -> diagnostics
```

`committed_state` 至少包含：

- `plastic_strain`；
- `equivalent_plastic_strain alpha`；
- 随动硬化模型的 `backstress`；
- 需要时的温度、损伤、黏性或其他内部变量，但这些不是当前核心模型的一部分。

`diagnostics` 至少包含：

- elastic/plastic 分支；
- trial yield value `f_trial`；
- `Delta_gamma`；
- 更新后 yield residual；
- 局部 Newton 次数和是否收敛；
- 切线类型与剪切 convention；
- 失败原因。

线性 J2 参数模式与 Voce J2 参数模式必须分开。前者使用 `H_iso`；后者使用 `Q, b, H_linear`，不得让一个非零 `H_iso` 字段在 Voce 更新中被静默忽略。

材料更新不得原地修改 committed state。

## 4. 张量与 Voigt 的边界

本包的规范推导使用真二阶/四阶张量和双点积。若代码使用工程剪应变向量，例如

```text
[eps_xx, eps_yy, eps_zz, gamma_xy, gamma_yz, gamma_zx]
```

则 `gamma_xy = 2 eps_xy`。应力向量、应变向量、四阶张量到矩阵的映射和内积度量必须成套定义。未经映射，不得把张量式 `n tensor n` 逐项抄成 6x6 外积。

## 5. “一致切线”的判断

只有满足以下三项才称为一致算法切线：

1. 它是实际离散更新 `sigma_(n+1) = S(eps_(n+1); state_n)` 的导数；
2. 扰动计算从同一个 committed state 重算；
3. V06 中心差分误差在截断误差区间按约二阶下降，并在舍入误差区间前达到规定阈值。

连续体弹塑性切线、弹性切线、割线、数值差分切线和算法一致切线不是同一对象。

## 6. 禁止推断

- 不得因更新后 `f` 接近零就宣称切线一致。
- 不得因全局 Newton 收敛就宣称状态更新无污染。
- 不得把一次总应变直接传入“增量接口”而不说明历史基准。
- 不得在 `f_trial <= tolerance` 时增加塑性变量。
- 不得把纯各向同性硬化用于解释明显的 Bauschinger 平移效应。
- 不得把一维线性随动硬化等同于 Chaboche 循环塑性。
- 不得把 3D 或平面应变更新通过截断 `sigma_zz` 伪装成平面应力。
- 不得在局部返回失败后仍返回貌似有效的应力和切线。
- 不得用放宽全局容差掩盖局部屈服残差或方向导数失败。
- 不得把未正则化软化结果解释为网格客观材料响应。

## 7. 建议回答结构

1. 适用范围和应力/应变 convention；
2. committed state 与输入增量；
3. trial state、屈服判断和返回映射；
4. 更新后状态与一致切线；
5. 对应验证 ID 和验收阈值；
6. 局限、未验证内容和升级条件。
