# Step 3｜Constitutive Nonlinearity：J2 各向同性硬化材料点演算

> 本步骤训练一个完整材料点更新链：从 committed state 出发，完成弹性预测、屈服判断、径向回归、状态更新、算法一致切线验证，以及被拒绝试算后的 rollback。建议先独立完成第 2 节，再查看第 3 节答案。

## 1. 学习链

```text
模型与状态定义
  → 弹性预测 stress trial
    → J2 屈服判断
      → 塑性乘子与径向回归
        → 应力/塑性应变/alpha 候选更新
          → 离散算法一致切线
            → 同一 committed state 的方向导数验证
              → 全局接受时 commit；拒绝时 rollback
                → 从未污染的状态继续卸载
```

完成本题后，应能回答以下问题：

1. 为什么线性各向同性硬化 J2 返回映射的分母是 $3G+H_{\mathrm{iso}}$，而不是 $2G+H_{\mathrm{iso}}$？
2. 为什么塑性回归只改变偏应力，不改变静水压力？
3. 为什么“更新后屈服残差接近零”不能单独证明算法切线一致？
4. 为什么被拒绝的候选状态即使局部计算完全正确，也不得进入下一次材料更新？

## 2. 完整题目区

### 2.1 模型、单位与 convention

采用小应变、率无关、关联流动、线性各向同性硬化 J2 模型：

$$
\boldsymbol\varepsilon
=\boldsymbol\varepsilon^e+\boldsymbol\varepsilon^p,
\qquad
\boldsymbol\sigma
=\mathbb C^e:(\boldsymbol\varepsilon-\boldsymbol\varepsilon^p),
$$

$$
\mathbf s=\operatorname{dev}(\boldsymbol\sigma),
\qquad
q=\sqrt{\frac32\mathbf s:\mathbf s},
$$

并定义

$$
p=\frac13\operatorname{tr}(\boldsymbol\sigma).
$$

这里采用拉应力为正，因此 $p$ 是平均正应力；它不是某些连续介质文献中“压缩为正”的压力变量。

$$
f=q-[\sigma_{y0}+H_{\mathrm{iso}}\alpha]\le 0,
\qquad
\Delta\boldsymbol\varepsilon^p
=\Delta\gamma\frac{3\mathbf s}{2q},
\qquad
\alpha_{n+1}=\alpha_n+\Delta\gamma.
$$

- 应力和模量单位：MPa；
- 应变、
  $\alpha$ 和 $\Delta\gamma$：无量纲；
- 使用 $3\times3$ 真二阶张量和 $3\times3\times3\times3$ 真四阶张量；
- 双点积采用 Frobenius 内积；
- 不使用未经映射的工程剪应变 Voigt 形式。

材料参数：

```text
E          = 210000 MPa
nu         = 0.3
sigma_y0   = 250 MPa
H_iso      = 1000 MPa
yield_tol  = 1.0e-10 MPa
```

初始 committed state：

$$
\mathcal S_0=
\left\{
\boldsymbol\varepsilon^p_0=\mathbf0_{3\times3},
\alpha_0=0
\right\}.
$$

> **重要警告：** 本题是三维应变控制材料点。给定的横向总应变为零，不代表横向应力为零，因此这不是单轴应力试验，也不是 plane-stress 更新。

### 2.2 任务 A：加载、弹性预测和屈服判断

从 $\mathcal S_0$ 加载到目标总应变：

$$
\boldsymbol\varepsilon_1=
\begin{bmatrix}
0.002&0&0\\
0&0&0\\
0&0&0
\end{bmatrix}.
$$

求：

1. 剪切模量 $G$、体积模量 $K$ 和 Lamé 常数 $\lambda$；
2. 试算应力 $\boldsymbol\sigma^{tr}$；
3. $p^{tr}$、$\mathbf s^{tr}$、$q^{tr}$ 和 $f^{tr}$；
4. 判断本步为弹性分支还是塑性分支。

### 2.3 任务 B：径向回归和状态候选值

若任务 A 判定为塑性分支，求：

1. $\Delta\gamma$；
2. 试算流动方向 $\mathbf n^{tr}$；
3. $\boldsymbol\varepsilon^p_1$ 和 $\alpha_1$；
4. 径向缩放系数 $a$；
5. 更新应力 $\boldsymbol\sigma_1$ 和等效应力 $q_1$；
6. 更新后的屈服残差；
7. 塑性不可压缩、KKT 条件和简化耗散自检。

假定该全局步最终收敛，因而把候选状态提交为 committed state $\mathcal S_1$。

### 2.4 任务 C：算法一致切线和方向导数

在线性各向同性硬化塑性分支，使用：

$$
\mathbb C^{alg}
=K\mathbf I\otimes\mathbf I
+2Ga\mathbb I_{dev}
-4G^2\left[
\frac{1}{3G+H_{\mathrm{iso}}}
-\frac{\Delta\gamma}{q^{tr}}
\right]
\mathbf n^{tr}\otimes\mathbf n^{tr}.
$$

取扰动方向：

$$
\mathbf D_0=
\begin{bmatrix}
0.6&0.2&0\\
0.2&-0.1&0\\
0&0&0.3
\end{bmatrix},
\qquad
\mathbf D=\frac{\mathbf D_0}{\|\mathbf D_0\|_F}.
$$

求：

1. 切线各标量系数及 $\mathbb C^{alg}:\mathbf D$；
2. 对

   ```text
   h = [2e-5, 1e-5, 5e-6, 2.5e-6]
   ```

   计算

   $$
   \mathbf y_h=
   \frac{
   \mathcal S(\boldsymbol\varepsilon_1+h\mathbf D;\mathcal S_0)
   -\mathcal S(\boldsymbol\varepsilon_1-h\mathbf D;\mathcal S_0)
   }{2h};
   $$

3. 报告相对误差及相邻误差比，并判断是否呈中心差分二阶趋势。

所有正负扰动都必须从同一个 virgin committed state $\mathcal S_0$ 重算，并检查两侧仍位于塑性分支。

### 2.5 任务 D：生成但拒绝一个候选状态

从已经提交的 $\mathcal S_1$ 对下列总应变做一次材料更新：

$$
\boldsymbol\varepsilon_R=
\begin{bmatrix}
0.003&0&0\\
0&0&0\\
0&0&0
\end{bmatrix}.
$$

求该试算的 $\boldsymbol\sigma_R^{tr}$、$q_R^{tr}$、$f_R^{tr}$、$\Delta\gamma_R$、候选应力和候选状态。然后假定全局迭代失败，明确说明哪些量必须被丢弃、哪些量必须保持不变。

### 2.6 任务 E：回滚后卸载

拒绝任务 D 的候选状态后，从原 committed state $\mathcal S_1$ 重新计算：

$$
\boldsymbol\varepsilon_2=
\begin{bmatrix}
0.001&0&0\\
0&0&0\\
0&0&0
\end{bmatrix}.
$$

求：

1. 弹性试算应力、$p_2$、$q_2$ 和 $f_2^{tr}$；
2. 分支、算法切线和内部变量；
3. 与“没有执行任务 D、直接从 $\mathcal S_1$ 卸载”的结果比较；
4. 至少列出五项 rollback 证据。

---

## 3. 完整解答

### 3.1 弹性常数

$$
G=\frac{E}{2(1+\nu)}
=\frac{210000}{2(1.3)}
=80769.230769\ \text{MPa},
$$

$$
K=\frac{E}{3(1-2\nu)}
=\frac{210000}{3(0.4)}
=175000\ \text{MPa},
$$

$$
\lambda=K-\frac{2G}{3}
=121153.846154\ \text{MPa}.
$$

### 3.2 任务 A：弹性预测和屈服判断

virgin state 下：

$$
\boldsymbol\sigma^{tr}
=\lambda\operatorname{tr}(\boldsymbol\varepsilon_1)\mathbf I
+2G\boldsymbol\varepsilon_1.
$$

由于 $\operatorname{tr}\boldsymbol\varepsilon_1=0.002$：

$$
\boldsymbol\sigma^{tr}=
\begin{bmatrix}
565.384615&0&0\\
0&242.307692&0\\
0&0&242.307692
\end{bmatrix}\ \text{MPa}.
$$

$$
p^{tr}=\frac13\operatorname{tr}\boldsymbol\sigma^{tr}
=350\ \text{MPa},
$$

$$
\mathbf s^{tr}=
\begin{bmatrix}
215.384615&0&0\\
0&-107.692308&0\\
0&0&-107.692308
\end{bmatrix}\ \text{MPa}.
$$

$$
\mathbf s^{tr}:\mathbf s^{tr}
=(215.384615)^2+2(-107.692308)^2
=69585.798817\ \text{MPa}^2,
$$

$$
q^{tr}=\sqrt{1.5(69585.798817)}
=323.076923\ \text{MPa}.
$$

初始屈服半径为 $250\ \text{MPa}$，故：

$$
f^{tr}=323.076923-(250+1000\times0)
=73.076923\ \text{MPa}>0.
$$

答案：本步进入塑性分支。

### 3.3 任务 B：径向回归和状态更新

一致性条件的分母为：

$$
3G+H_{\mathrm{iso}}
=3(80769.230769)+1000
=243307.692308\ \text{MPa}.
$$

其中 $3G$ 来自 J2 等效应力沿返回方向的减少率；硬化半径同时以 $H_{\mathrm{iso}}\Delta\gamma$ 增加。因此：

$$
\Delta\gamma
=\frac{f^{tr}}{3G+H_{\mathrm{iso}}}
=\frac{73.076923}{243307.692308}
=0.000300347771103383.
$$

流动方向：

$$
\mathbf n^{tr}
=\frac{3\mathbf s^{tr}}{2q^{tr}}
=\operatorname{diag}(1,-0.5,-0.5),
$$

且

$$
\mathbf n^{tr}:\mathbf n^{tr}=1^2+2(-0.5)^2=1.5.
$$

塑性应变候选状态：

$$
\boldsymbol\varepsilon^p_1
=\boldsymbol\varepsilon^p_0+\Delta\gamma\mathbf n^{tr}
=
\begin{bmatrix}
0.000300347771&0&0\\
0&-0.000150173886&0\\
0&0&-0.000150173886
\end{bmatrix}.
$$

$$
\alpha_1=\alpha_0+\Delta\gamma
=0.000300347771103383.
$$

径向缩放系数：

$$
a=1-\frac{3G\Delta\gamma}{q^{tr}}
=1-\frac{72.776575306}{323.076923077}
=0.774739171672.
$$

$$
\mathbf s_1=a\mathbf s^{tr}
=\operatorname{diag}
(166.866899,-83.433449,-83.433449)\ \text{MPa}.
$$

塑性流动为偏量，故静水压力仍为 $350\ \text{MPa}$：

$$
\boxed{
\boldsymbol\sigma_1
=\operatorname{diag}
(516.866899,266.566551,266.566551)\ \text{MPa}
}.
$$

$$
q_1=q^{tr}-3G\Delta\gamma
=323.076923-72.776575
=250.300347771\ \text{MPa}.
$$

屈服残差：

$$
q_1-(\sigma_{y0}+H_{\mathrm{iso}}\alpha_1)
=2.84\times10^{-14}\ \text{MPa}\approx0.
$$

KKT 条件逐项为

$$
f_1\le0,
\qquad
\Delta\gamma\ge0,
\qquad
\Delta\gamma f_1=0.
$$

本题按显示精度有 $f_1\approx2.84\times10^{-14}\ \text{MPa}$；在 $10^{-10}\ \text{MPa}$ 屈服容差下视为零，因此三项均满足。

状态与物理自检：

$$
\operatorname{tr}(\Delta\boldsymbol\varepsilon^p)
=\Delta\gamma(1-0.5-0.5)=0,
$$

其浮点参考值为 $-1.63\times10^{-19}$。另外：

$$
\Delta\gamma>0,
\qquad
\alpha_1-\alpha_0=\Delta\gamma,
$$

$$
\sigma_{y0}\Delta\gamma
=250(0.000300347771103383)
=0.075086943\ \text{MPa}\ge0.
$$

全局步接受后，提交：

$$
\mathcal S_1
=\{\boldsymbol\varepsilon^p_1,\alpha_1\}.
$$

### 3.4 任务 C：算法一致切线和方向导数

计算切线中的系数：

$$
2Ga=2(80769.230769)(0.774739171672)
=125150.173886\ \text{MPa},
$$

$$
\frac{1}{3G+H_{\mathrm{iso}}}
-\frac{\Delta\gamma}{q^{tr}}
=3.18037426795\times10^{-6}\ \text{MPa}^{-1},
$$

$$
B=4G^2\left[
\frac{1}{3G+H_{\mathrm{iso}}}
-\frac{\Delta\gamma}{q^{tr}}
\right]
=82990.831489\ \text{MPa}.
$$

所以：

$$
\mathbb C^{alg}
=175000\,\mathbf I\otimes\mathbf I
+125150.173886\,\mathbb I_{dev}
-82990.831489\,\mathbf n^{tr}\otimes\mathbf n^{tr}.
$$

注意 Frobenius 范数会把对称张量的两个非对角分量都计入：

$$
\|\mathbf D_0\|_F
=\sqrt{0.6^2+(-0.1)^2+0.3^2+2(0.2)^2}
=\sqrt{0.54}
=0.734846923.
$$

$$
\mathbf D=
\begin{bmatrix}
0.816496581&0.272165527&0\\
0.272165527&-0.136082763&0\\
0&0&0.408248290
\end{bmatrix}.
$$

解析切线作用结果：

$$
\boxed{
\mathbb C^{alg}:\mathbf D=
\begin{bmatrix}
190817.032128&34061.563027&0\\
34061.563027&156303.724234&0\\
0&0&224426.850287
\end{bmatrix}\ \text{MPa}
}.
$$

四个步长的正负扰动均从同一个 $\mathcal S_0$ 重算。中心差分矩阵的非零独立分量如下；对称位置满足 $y_{yx}=y_{xy}$，其余剪切分量为零：

| $h$ | $y_{xx}$ | $y_{yy}$ | $y_{zz}$ | $y_{xy}$ | $f^{tr}_+$ / $f^{tr}_-$ (MPa) |
|---:|---:|---:|---:|---:|---:|
| $2.0\times10^{-5}$ | 190819.541887 | 156301.653815 | 224426.410947 | 34062.378566 | 75.282314 / 70.885892 |
| $1.0\times10^{-5}$ | 190817.659556 | 156303.206614 | 224426.740479 | 34061.766932 | 74.177842 / 71.979594 |
| $5.0\times10^{-6}$ | 190817.188984 | 156303.594828 | 224426.822837 | 34061.614004 | 73.626936 / 72.527808 |
| $2.5\times10^{-6}$ | 190817.071342 | 156303.691882 | 224426.843425 | 34061.575771 | 73.351818 / 72.802253 |

所有 $f^{tr}_+$ 与 $f^{tr}_-$ 都大于零，所以两侧均保持在塑性分支。相对误差为：

| $h$ | 相对误差 | 前一误差/当前误差 |
|---:|---:|---:|
| $2.0\times10^{-5}$ | $1.0327488819\times10^{-5}$ | — |
| $1.0\times10^{-5}$ | $2.5818911828\times10^{-6}$ | $4.0000$ |
| $5.0\times10^{-6}$ | $6.4547396646\times10^{-7}$ | $4.0000$ |
| $2.5\times10^{-6}$ | $1.6136856478\times10^{-7}$ | $4.0000$ |

最小步长的中心差分结果为：

$$
\mathbf y_h=
\begin{bmatrix}
190817.071342&34061.575771&0\\
34061.575771&156303.691882&0\\
0&0&224426.843425
\end{bmatrix}\ \text{MPa}.
$$

步长每减半，误差约除以四，显示中心差分二阶截断误差；最终相对误差小于 $10^{-6}$。因此该方向上的切线检查通过。

### 3.5 任务 D：被拒绝的候选状态

此时输入状态必须是已经提交的 $\mathcal S_1$，而不是任务 C 中任一扰动的候选状态。

对 $\boldsymbol\varepsilon_R$ 的弹性预测为：

$$
\boldsymbol\sigma_R^{tr}
=\operatorname{diag}
(799.559206,387.720397,387.720397)\ \text{MPa},
$$

$$
p_R^{tr}=525\ \text{MPa},
\qquad
q_R^{tr}=411.838809\ \text{MPa}.
$$

当前屈服半径为：

$$
\sigma_{y0}+H_{\mathrm{iso}}\alpha_1
=250.300347771\ \text{MPa},
$$

因此：

$$
f_R^{tr}
=411.838809-250.300348
=161.538462\ \text{MPa}>0,
$$

$$
\Delta\gamma_R
=\frac{161.538462}{243307.692308}
=0.000663926651913.
$$

沿相同的比例加载方向返回，候选状态为：

$$
\boldsymbol\varepsilon^p_R
=\operatorname{diag}
(0.000964274423,-0.000482137212,-0.000482137212),
$$

$$
\alpha_R=0.000964274423016.
$$

候选应力为：

$$
\boldsymbol\sigma_R
=\operatorname{diag}
(692.309516,441.345242,441.345242)\ \text{MPa},
$$

更新后 $q_R=250.964274423\ \text{MPa}$，屈服残差约为 $-2.84\times10^{-14}\ \text{MPa}$。

虽然该候选状态满足局部本构方程，但题设规定全局试算失败，所以必须丢弃：

- $\boldsymbol\sigma_R$；
- 本次 $\mathbb C_R^{alg}$；
- $\boldsymbol\varepsilon^p_R$；
- $\alpha_R$；
- 所有仅属于该候选试算的局部缓存。

必须保留原 committed state：

$$
\boxed{
\mathcal S_{\mathrm{committed,after\ reject}}
=\mathcal S_1
}.
$$

### 3.6 任务 E：回滚后的弹性卸载

从未被污染的 $\mathcal S_1$ 重新计算：

$$
\boldsymbol\varepsilon^e_2
=\boldsymbol\varepsilon_2-\boldsymbol\varepsilon^p_1
=\operatorname{diag}
(0.000699652229,0.000150173886,0.000150173886).
$$

弹性试算应力为：

$$
\boxed{
\boldsymbol\sigma_2^{tr}
=\operatorname{diag}
(234.174591,145.412705,145.412705)\ \text{MPa}
}.
$$

$$
p_2=175\ \text{MPa},
\qquad
q_2=88.761886\ \text{MPa}.
$$

$$
f_2^{tr}
=88.761886-250.300348
=-161.538462\ \text{MPa}<0.
$$

因此本步为弹性卸载：

$$
\Delta\gamma_2=0,
\qquad
\boldsymbol\sigma_2=\boldsymbol\sigma_2^{tr},
$$

$$
\boldsymbol\varepsilon^p_2=\boldsymbol\varepsilon^p_1,
\qquad
\alpha_2=\alpha_1,
$$

$$
\mathbb C^{alg}_2=\mathbb C^e.
$$

真四阶弹性张量的代表性分量为：

$$
C_{xxxx}=282692.307692\ \text{MPa},
$$

$$
C_{xxyy}=121153.846154\ \text{MPa},
\qquad
C_{xyxy}=80769.230769\ \text{MPa}.
$$

“先生成并拒绝 $\mathcal S_R$，再从 $\mathcal S_1$ 卸载”与“完全跳过被拒绝试算、直接从 $\mathcal S_1$ 卸载”的参考计算满足：

$$
\|\boldsymbol\sigma_{\mathrm{retry}}
-\boldsymbol\sigma_{\mathrm{direct}}\|_F
=0\ \text{MPa},
$$

$$
\|\boldsymbol\varepsilon^p_{\mathrm{retry}}
-\boldsymbol\varepsilon^p_{\mathrm{direct}}\|_F=0,
$$

$$
|\alpha_{\mathrm{retry}}-\alpha_{\mathrm{direct}}|=0.
$$

最低 rollback 证据包括：

1. 被拒绝的全局步和迭代 ID；
2. 被拒绝试算的目标总应变；
3. 候选应力、候选内部变量和诊断摘要；
4. 拒绝原因；
5. 回滚前后 committed state 的逐变量相等检查或哈希；
6. 重试所用步长或目标应变；
7. 重试结果与未经历被拒绝试算的直接路径比较。

## 4. 自检表

| 检查项 | 本题结果 | 最低验收 | 结论 |
|---|---:|---:|---|
| 塑性分支 $\Delta\gamma$ | $3.0034777\times10^{-4}>0$ | $\Delta\gamma\ge0$ | 通过 |
| $\operatorname{tr}\Delta\boldsymbol\varepsilon^p$ | $-1.63\times10^{-19}$ | 绝对值 $\le10^{-12}$ | 通过 |
| 硬化状态更新 | $\alpha_1-\alpha_0=\Delta\gamma$ | 必须相等 | 通过 |
| 塑性步屈服残差 | $2.84\times10^{-14}\ \text{MPa}$ | $\le10^{-9}\ \text{MPa}$ | 通过 |
| 径向回归静水压力 | 返回前后均为 $350\ \text{MPa}$ | 必须不变 | 通过 |
| 简化塑性耗散 | $0.075086943\ \text{MPa}$ | 非负 | 通过 |
| 方向导数最小误差 | $1.61\times10^{-7}$ | $<10^{-6}$ | 通过 |
| 中心差分误差比 | 约 $4,4,4$ | 至少三次减半呈二阶趋势 | 通过 |
| 方向扰动分支 | 正负两侧均为 plastic | 不得跨分支 | 通过 |
| 弹性卸载状态 | $\boldsymbol\varepsilon^p,\alpha$ 逐项不变 | 必须保持 | 通过 |
| rollback 后应力路径 | retry 与 direct 差为 $0\ \text{MPa}$ | 必须一致 | 通过 |
| rollback 后内部变量 | retry 与 direct 差均为 $0$ | 必须一致 | 通过 |

## 5. 适用边界与易错点

1. **不是单轴应力。** 本题给定 $\varepsilon_{yy}=\varepsilon_{zz}=0$，所以会产生非零 $\sigma_{yy}$ 和 $\sigma_{zz}$。若要求 plane stress，必须把厚度应变作为局部未知量求解 $\sigma_{zz}=0$，不能在三维更新后直接删掉 $\sigma_{zz}$。
2. **仅限小应变。** 当转动、塑性转动或总变形不再小时，不能把本题公式直接换成 Green-Lagrange 应变后继续使用。
3. **J2 对压力不敏感。** 本模型适合作为延性金属基线，不适合显著受围压影响的土、岩、混凝土、泡沫或颗粒材料。
4. **纯各向同性硬化不能描述屈服面平移。** 本题不能用于解释明显的 Bauschinger 效应、棘轮或复杂循环记忆。
5. **一致切线只说明切线与离散更新匹配。** 它不能单独证明材料模型、参数、网格结果或热力学行为全部正确。
6. **方向导数必须远离分支切换面。** 若正负扰动跨越 elastic/plastic 切换面，经典双侧导数可能不存在，应改做单侧或半光滑检查。
7. **张量和工程 Voigt 不得混用。** 在工程剪应变中 $\gamma_{xy}=2\varepsilon_{xy}$；未经完整映射，不能把本题的 $\mathbf n\otimes\mathbf n$ 逐项抄成 $6\times6$ 外积。
8. **rollback 是状态事务，不是物理卸载。** 被拒绝候选的局部屈服残差即使接近零，也不能成为提交该状态的理由。
9. **线性硬化为闭式回归。** 本题不包含 Voce 硬化的局部 Newton、有限应变塑性、损伤、软化、黏塑性、各向异性或生产级循环塑性。
10. **材料点正确不等于有限元整体正确。** 单元锁死、全局残量符号、几何切线、约束和路径控制仍需独立验证。

## 6. 资料依据

本题使用文件夹内资料完成，不需要额外网络资料。以下行号均相对于 `Constitutive-Nonlinearity_Weeks10-14_Core-Guide`：

| 内容 | 来源文件与行号 |
|---|---|
| J2 规范符号、状态与张量 convention | `AI_USAGE.md:19-46,48-95` |
| $3G+H_{\mathrm{iso}}$、状态安全及能力边界 | `AGENTS.md:7-15` |
| 无副作用材料接口、commit/rollback 流程 | `01_核心算法/00_五周总览与材料接口.md:18-39,49-73,90-108,110-122` |
| 弹性预测、J2 径向回归、状态更新与数值保护 | `01_核心算法/W12_J2径向返回算法.md:3-29,31-118,120-147` |
| 离散一致切线和中心方向导数 | `01_核心算法/W13_一致切线与平面应力.md:3-84` |
| V04、V06、V07 原验证题 | `03_验证题目与答案/验证题目.md:67-130` |
| V04–V07 配套参考答案 | `03_验证题目与答案/配套答案.md:100-181` |
| 数值容差、方向导数和路径回归标准 | `03_验证题目与答案/验证矩阵.md:23-28,68-84` |
| J2 可执行参考更新 | `04_可复现算例/reference_material_point.py:56-73,84-150` |
| V04–V07 可复现检查 | `04_可复现算例/reference_material_point.py:411-475` |
| 能力边界、非光滑点、Voigt 风险和状态安全 | `02_算法局限/算法局限与升级边界.md:3-18,30-59,110-133` |
| 理论来源映射 | `06_来源映射/公式与页码映射.md:3-22,39-47` |

包内来源映射进一步指向 de Borst 等《Non-linear Finite Element Analysis of Solids and Structures》第 7 章：J2 径向返回对应 PDF 第 263–267 页，一致切线对应第 265–268 页。原书理论不能替代本题的方向导数和 rollback 数值验证。

参考脚本已用带 NumPy 的工作区 Python 运行，首行输出：

```text
PACKAGE_REFERENCE_CHECK: OK
```

任务 D–E 的三维 rollback 扩展数值，是对同一个 `j2_update` 从固定 committed state 独立重算得到；参考脚本和资料包文件均未修改。
