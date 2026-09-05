# Step 4｜一般非线性壳数学核心演算题

## 一、学习链

这一步把一般非线性壳最容易割裂的五段数学链放进同一个可手算模型：

1. **有限转动**：用指数映射更新 director，检查旋转矩阵、单位长度和正交性。
2. **客观应变与功共轭应力**：在 Total Lagrangian（TL）框架内使用 Green–Lagrange 应变与第二 Piola–Kirchhoff 应力，并把应力正确推到当前构形。
3. **残量与一致切线**：固定采用
   $$
   r=f_{ext}-f_{int},
   \qquad
   K_t=\frac{df_{int}}{dq}-\frac{df_{ext}}{dq},
   \qquad
   K_t\Delta q=r.
   $$
4. **随动力**：外力方向随当前 director 改变，因此必须对外力关于位形的变化进行线性化。
5. **Newton 与状态事务**：所有全局迭代量都是 trial；只有全局收敛后才能一次性 commit，失败或缩步必须 rollback。

建议先独立完成题目，再阅读完整解答。该演算对应项目验证链中的 V00–V05 与 V12，但不能替代真实壳单元的独立验证。

---

## 二、完整题目区

### 2.1 模型

考虑一个教学用单模态壳条。参考参数为：

| 量 | 数值 | 单位 |
|---|---:|---|
| 长度 $L$ | 100 | $\mathrm{mm}$ |
| 宽度 $b$ | 10 | $\mathrm{mm}$ |
| 厚度 $h$ | 1 | $\mathrm{mm}$ |
| 参考体积 $V_0=Lbh$ | 1000 | $\mathrm{mm^3}$ |
| 教学用材料模量 $C$ | 1 | $\mathrm{MPa}=\mathrm{N/mm^2}$ |
| 端部随形法向合力幅值 $P$ | 2 | $\mathrm N$ |
| 目标载荷因子 $\lambda$ | 1 | — |

参考切向与 director 分别为

$$
\mathbf A=\mathbf e_1,
\qquad
\mathbf D=\mathbf e_3.
$$

采用一个无量纲广义变量 $q$。为了把有限伸展、有限转动、内力和随动力压缩到一道手算题中，**本教学模态人为规定：轴向伸展增量与绕 $y$ 轴转角均取同一个数值 $q$**：

$$
\mathbf U(q)=\operatorname{diag}(1+q,1,1),
$$

$$
\mathbf R(q)
=\exp\!\left(q[\mathbf e_2]_\times\right)
=\mathbf R_y(q),
$$

$$
\mathbf F(q)=\mathbf R(q)\mathbf U(q).
$$

其中转角用弧度表示；弧度在量纲分析中视为无量纲。

当前切向、director 与壳条端点为

$$
\mathbf a(q)=\mathbf R(q)\mathbf e_1,
\qquad
\mathbf d(q)=\mathbf R(q)\mathbf e_3,
$$

$$
\mathbf x(q)=L(1+q)\mathbf a(q).
$$

端部随形力始终沿当前负 director：

$$
\mathbf p(q,\lambda)=-\lambda P\mathbf d(q).
$$

材料采用教学用单轴 St. Venant–Kirchhoff 形式：

$$
E_{11}=\frac12\left[(1+q)^2-1\right],
\qquad
S_{11}=C E_{11}.
$$

### 2.2 转动与状态约定

本题明确采用**空间转动增量左乘**：

$$
\mathbf R_{j+1}
=\exp\!\left(\Delta q_j[\mathbf e_2]_\times\right)\mathbf R_j.
$$

假定前一收敛状态为

```text
lambda_n = 0
q_n = 0
R_n = I
d_n = e3
h_n = 1 mm
material_history_n = empty
```

在目标载荷 $\lambda=1$ 下，取 Newton 初始预测 $q^{(0)}=0.2$。

### 2.3 要求

#### A. 有限转动

1. 写出 $\mathbf R_y(q)$ 的矩阵形式。
2. 在 $q^{(0)}=0.2$ 处计算 $\mathbf a$ 和 $\mathbf d$。
3. 检查 $\mathbf R^T\mathbf R$、$\det\mathbf R$、$\|\mathbf d\|$ 与 $\mathbf a\cdot\mathbf d$。
4. 在得到第一次 Newton 修正后，用左乘指数更新 director；再说明直接采用加法更新为何不合格。

#### B. 客观应变与应力度量

1. 计算 $J=\det\mathbf F$ 和 Green–Lagrange 应变 $\mathbf E$。
2. 在 $q=0.2$ 处计算 $S_{11}$。
3. 用
   $$
   \boldsymbol\sigma
   =J^{-1}\mathbf F\mathbf S\mathbf F^T
   $$
   计算 Cauchy 应力。
4. 对任意叠加刚体转动 $\mathbf Q$，令 $\mathbf F^*=\mathbf Q\mathbf F$，证明 $\mathbf E^*=\mathbf E$，并说明空间应力怎样变化。
5. 说明为什么“小应变 + 精确 director 转动”仍不自动构成客观有限应变壳。

#### C. 残量与完整切线

1. 从
   $$
   \Pi_{int}=\frac12V_0C E_{11}^2
   $$
   推导内部广义力 $f_{int}$。
2. 从随形力虚功
   $$
   \delta W_{ext}
   =\mathbf p\cdot\frac{d\mathbf x}{dq}\,\delta q
   $$
   推导 $f_{ext}$。
3. 把总切线写成 $K_{mat}$、$K_{geo}$、$K_{rot}$、$K_{stab}$ 与 $K_{load}$ 的组合，并说明本教学模型中哪些项为零：
   $$
   K_t=K_{mat}+K_{geo}+K_{rot}+K_{stab}-K_{load}.
   $$
4. 在 $q=0.2,\lambda=1$ 处计算 $f_{int},f_{ext},r$ 和全部切线项。
5. 用中心方向差分步长 $h_{fd}=10^{-3}$ 检查切线符号和数值。

#### D. Newton、控制方式与状态提交

1. 从 $q^{(0)}=0.2$ 至少完成两次 Newton 修正。
2. 求平衡方程的精确解 $q^*$，并核对最终内外力。
3. 判断本题是否需要弧长控制。
4. 写出全局收敛时的 commit 内容，以及中途失败或缩步时必须 rollback 的内容。

---

## 三、完整解答

### 3.1 有限转动

绕 $y$ 轴的指数映射为

$$
\mathbf R_y(q)=
\begin{bmatrix}
\cos q&0&\sin q\\
0&1&0\\
-\sin q&0&\cos q
\end{bmatrix}.
$$

在 $q=0.2$ 处，

$$
\cos 0.2=0.9800666,
\qquad
\sin 0.2=0.1986693,
$$

所以

$$
\mathbf R_y(0.2)=
\begin{bmatrix}
0.9800666&0&0.1986693\\
0&1&0\\
-0.1986693&0&0.9800666
\end{bmatrix},
$$

$$
\mathbf a=(0.9800666,0,-0.1986693)^T,
$$

$$
\mathbf d=(0.1986693,0,0.9800666)^T.
$$

由正弦和余弦恒等式可得

$$
\mathbf R^T\mathbf R=\mathbf I,
\qquad
\det\mathbf R=1,
$$

$$
\|\mathbf d\|=1,
\qquad
\mathbf a\cdot\mathbf d=0.
$$

后文会得到第一次 Newton 修正

$$
\Delta q^{(0)}=-0.01643836.
$$

按空间增量左乘，

$$
\mathbf R^{(1)}
=\mathbf R_y(-0.01643836)\mathbf R_y(0.2).
$$

本题中两次转动都绕同一个 $y$ 轴，因此

$$
\mathbf R^{(1)}=\mathbf R_y(0.18356164),
$$

$$
\mathbf d^{(1)}
=(\sin 0.18356164,0,\cos 0.18356164)^T
=(0.1825325,0,0.9831998)^T.
$$

若错误地采用一阶加法更新，

$$
\mathbf d_{add}
=\mathbf d+\Delta q\,\mathbf e_2\times\mathbf d.
$$

因为 $\mathbf e_2\times\mathbf d=\mathbf a$，且 $\mathbf a\perp\mathbf d$，所以

$$
\|\mathbf d_{add}\|
=\sqrt{1+(\Delta q)^2}
=1.0001351\ne1.
$$

加法式可以作为线性化方向，但不能作为有限步的最终转动状态。

> **关键警告：** 本题的所有转动均共轴，所以左乘和右乘在数值上恰好可交换。这只是本题的特殊巧合；一般三维非共轴转动中，空间左乘与材料右乘不能混用。

### 3.2 客观应变与应力度量

由 $\mathbf F=\mathbf R\mathbf U$ 及 $\mathbf R^T\mathbf R=\mathbf I$，

$$
\mathbf F^T\mathbf F
=\mathbf U^T\mathbf R^T\mathbf R\mathbf U
=\operatorname{diag}((1+q)^2,1,1).
$$

因此

$$
\mathbf E
=\frac12(\mathbf F^T\mathbf F-\mathbf I)
=\operatorname{diag}\left(q+\frac12q^2,0,0\right).
$$

在 $q=0.2$ 处，

$$
J=\det\mathbf F=\det\mathbf U=1.2,
$$

$$
E_{11}=0.2+\frac12(0.2)^2=0.22,
$$

$$
S_{11}=C E_{11}=0.22\ \mathrm{MPa}.
$$

令 $\mathbf S=S_{11}\mathbf e_1\otimes\mathbf e_1$。由于

$$
\mathbf F\mathbf e_1=(1+q)\mathbf a,
$$

Cauchy 应力为

$$
\boldsymbol\sigma
=J^{-1}\mathbf F\mathbf S\mathbf F^T
=S_{11}(1+q)\mathbf a\otimes\mathbf a.
$$

在 $q=0.2$ 处，当前切向应力幅值为

$$
S_{11}(1+q)=0.22\times1.2=0.264\ \mathrm{MPa},
$$

从而

$$
\boldsymbol\sigma=
\begin{bmatrix}
0.253580&0&-0.051403\\
0&0&0\\
-0.051403&0&0.010420
\end{bmatrix}\ \mathrm{MPa}.
$$

现在叠加任意刚体转动 $\mathbf Q$，其中 $\mathbf Q^T\mathbf Q=\mathbf I$：

$$
\mathbf F^*=\mathbf Q\mathbf F.
$$

则

$$
\mathbf E^*
=\frac12\left((\mathbf F^*)^T\mathbf F^*-\mathbf I\right)
=\frac12\left(\mathbf F^T\mathbf Q^T\mathbf Q\mathbf F-\mathbf I\right)
=\mathbf E.
$$

第二 Piola–Kirchhoff 应力仍在参考构形中保持相同分量，而空间应力正确地随坐标系转动：

$$
\boldsymbol\sigma^*=\mathbf Q\boldsymbol\sigma\mathbf Q^T.
$$

作为反例，若只有绕 $z$ 轴 $90^\circ$ 的纯刚体转动，则 Green–Lagrange 应变为零，但小应变

$$
\boldsymbol\varepsilon
=\operatorname{sym}(\mathbf Q-\mathbf I)
=\operatorname{diag}(-1,-1,0)
$$

会把纯转动误判为面内压缩。因此，只有 director 使用精确转动而膜、弯曲或剪切仍使用非客观小应变，并不能形成一致的有限应变壳。

### 3.3 内力与随形外力

内部能为

$$
\Pi_{int}=\frac12V_0C E_{11}^2.
$$

由

$$
\frac{dE_{11}}{dq}=1+q,
\qquad
\frac{d^2E_{11}}{dq^2}=1,
$$

得到内部广义力

$$
f_{int}
=\frac{d\Pi_{int}}{dq}
=V_0C E_{11}(1+q).
$$

对当前切向求导：

$$
\frac{d\mathbf a}{dq}
=\frac{d}{dq}\left(\mathbf R_y(q)\mathbf e_1\right)
=-\mathbf d.
$$

因此端点导数为

$$
\frac{d\mathbf x}{dq}
=L\left[\mathbf a-(1+q)\mathbf d\right].
$$

随形力的广义外力为

$$
f_{ext}
=\mathbf p\cdot\frac{d\mathbf x}{dq}.
$$

代入 $\mathbf p=-\lambda P\mathbf d$、$\mathbf a\cdot\mathbf d=0$ 与 $\|\mathbf d\|=1$，得

$$
f_{ext}=\lambda PL(1+q).
$$

这里“$P$ 的标量幅值恒定”不等于“外力向量恒定”；$\mathbf p$ 的方向始终随当前 director 更新。

### 3.4 材料、几何和随动力切线

对内部力求导：

$$
\frac{df_{int}}{dq}
=V_0C\left(\frac{dE_{11}}{dq}\right)^2
+V_0S_{11}\frac{d^2E_{11}}{dq^2}.
$$

据此定义

$$
K_{mat}=V_0C(1+q)^2,
$$

$$
K_{geo}=V_0S_{11}=V_0CE_{11}.
$$

随形外力切线为

$$
K_{load}=\frac{df_{ext}}{dq}=\lambda PL.
$$

在尚未代入本模型的零项前，总切线写为

$$
K_t=K_{mat}+K_{geo}+K_{rot}+K_{stab}-K_{load}.
$$

在 $q=0.2,\lambda=1$ 处：

$$
f_{int}
=1000\times1\times0.22\times1.2
=264\ \mathrm{N\,mm},
$$

$$
f_{ext}
=1\times2\times100\times1.2
=240\ \mathrm{N\,mm},
$$

$$
r=f_{ext}-f_{int}
=-24\ \mathrm{N\,mm}.
$$

各切线项为

$$
K_{mat}=1000\times1\times1.2^2
=1440\ \mathrm{N\,mm},
$$

$$
K_{geo}=1000\times0.22
=220\ \mathrm{N\,mm},
$$

$$
K_{load}=2\times100
=200\ \mathrm{N\,mm},
$$

将本教学模型下的 $K_{rot}=K_{stab}=0$ 代入后：

$$
K_t=1440+220-200
=1460\ \mathrm{N\,mm}.
$$

由于本题采用同质、均匀、共转的一模态，$\mathbf R$ 在 $\mathbf F^T\mathbf F$ 中完全消去，故本模型的内部旋转切线

$$
K_{rot}=0.
$$

本教学模型没有定义稳定化能量，因此

$$
K_{stab}=0.
$$

> **关键警告：** $K_{rot}=K_{stab}=0$ 只属于这个特制缩减模型。一般壳单元中 director、局部基、插值、锁定处理和旋转参数化会产生相应切线，不能据此省略。

### 3.5 中心方向差分检查

由残量符号 $r=f_{ext}-f_{int}$，解析切线应满足

$$
K_t
\approx
-\frac{r(q+h_{fd})-r(q-h_{fd})}{2h_{fd}}.
$$

在 $q=0.2,h_{fd}=10^{-3}$ 时：

$$
r(0.201)=-25.4618005\ \mathrm{N\,mm},
$$

$$
r(0.199)=-22.5417995\ \mathrm{N\,mm}.
$$

所以

$$
-\frac{r(0.201)-r(0.199)}{0.002}
=1460.0005\ \mathrm{N\,mm}.
$$

相对于解析值 $1460$ 的相对误差为

$$
\frac{|1460.0005-1460|}{1460}
=3.42\times10^{-7}.
$$

继续减小步长至 $h_{fd}=10^{-4}$ 时得到约 $1460.000005$，体现中心差分的二阶截断误差区；实际验证还应扫描更多 $h_{fd}$，观察舍入误差谷值。

### 3.6 Newton 迭代

Newton 方程为

$$
K_t^{(j)}\Delta q^{(j)}=r^{(j)},
\qquad
q^{(j+1)}=q^{(j)}+\Delta q^{(j)},
$$

同时用指数映射更新 trial 旋转。

迭代结果如下：

| $j$ | $q^{(j)}$ | $r^{(j)}$ / $\mathrm{N\,mm}$ | $K_t^{(j)}$ / $\mathrm{N\,mm}$ | $\Delta q^{(j)}$ |
|---:|---:|---:|---:|---:|
| 0 | 0.2000000000 | -24.000000 | 1460.000000 | -0.0164383562 |
| 1 | 0.1835616438 | -0.484174 | 1401.227247 | -0.0003455358 |
| 2 | 0.1832161080 | $-2.11946\times10^{-4}$ | 1400.000537 | $-1.51390\times10^{-7}$ |
| 3 | 0.183215956619952 | $-4.06146\times10^{-11}$ | 1400.000000 | $-2.90104\times10^{-14}$ |

第一次修正为

$$
\Delta q^{(0)}=\frac{-24}{1460}=-0.0164383562,
$$

$$
q^{(1)}=0.2-0.0164383562=0.1835616438.
$$

第二次修正为

$$
\Delta q^{(1)}
=\frac{-0.4841742135}{1401.227247}
=-0.0003455358,
$$

$$
q^{(2)}=0.1832161080.
$$

残量从 $24$ 降至 $0.484$，再降至 $2.12\times10^{-4}\ \mathrm{N\,mm}$，表现出一致切线对应的快速收敛。

### 3.7 精确平衡解与控制方式

平衡条件为

$$
\lambda PL(1+q)
=V_0C\left(q+\frac12q^2\right)(1+q).
$$

对几何有效分支 $q>-1$，可消去 $1+q$：

$$
q+\frac12q^2
=\frac{\lambda PL}{V_0C}
=0.2.
$$

因此

$$
q^*=-1+\sqrt{1.4}
=0.1832159566.
$$

最终内外力为

$$
f_{ext}=f_{int}
=200(1+q^*)
=236.6431913\ \mathrm{N\,mm}.
$$

在精确解处，

$$
K_{mat}=1400,
\qquad
K_{geo}=200,
\qquad
K_{load}=200,
$$

$$
K_t=1400\ \mathrm{N\,mm}>0.
$$

更一般地，当前正载荷分支为

$$
q(\lambda)
=-1+\sqrt{1+\frac{2\lambda PL}{V_0C}},
$$

它在 $\lambda\ge0$ 时单调，且平衡点处

$$
K_t=V_0C(1+q)^2>0.
$$

因此本题没有极限点，荷载控制的全 Newton 足够，不需要弧长。弧长能力仍须用独立极限点题验证。

### 3.8 Trial、commit 与 rollback

整个目标载荷步中，以下内容均保持为不可变 committed 基准：

```text
lambda_n = 0
q_n = 0
R_n = I
d_n = e3
h_n = 1 mm
material_history_n = empty
```

以下量在全局迭代期间只是 trial：

- $q^{(j)}$ 与 $\lambda=1$；
- $\mathbf R^{(j)}$、$\mathbf d^{(j)}$ 与当前端点；
- $E_{11}^{(j)}$、$S_{11}^{(j)}$、$\boldsymbol\sigma^{(j)}$；
- 当前残量、切线、能量和诊断缓存。

只有全局残量、修正、几何和材料诊断同时满足容差后，才一次性提交：

```text
lambda = 1
q = 0.1832159566
R = Ry(q)
d = R e3
h = 1 mm
material_history = empty
```

必须区分两级拒绝：

1. **线搜索或根选择只拒绝当前候选。** 丢弃该候选的几何、director、应力、切线和缓存，返回当前迭代基点 $q^{(j)}$，再生成较小候选；材料响应仍从同一个步首 committed state 重算。
2. **整个载荷步失败或决定缩步。** 丢弃本步全部 trial 迭代，恢复步 $n$ 的完整 committed 快照，包括节点、director、厚度和材料历史。

两种情况下都不能只恢复 $q$ 而保留被拒绝候选的 director、应力或历史变量。

---

## 四、自检

### 4.1 手算核对表

| 核对项 | 正确结果 | 错误信号 |
|---|---|---|
| 旋转群 | $\mathbf R^T\mathbf R=\mathbf I$，$\det\mathbf R=1$ | 正交误差或行列式偏离 1 |
| director | $\|\mathbf d\|=1$，$\mathbf a\cdot\mathbf d=0$ | 加法更新导致范数漂移 |
| 客观应变 | 叠加 $\mathbf Q$ 后 $\mathbf E^*=\mathbf E$ | 刚体转动产生膜应变 |
| TL 功共轭 | 使用 $(\mathbf E,\mathbf S,V_0)$ | 把 $\mathbf S$ 直接当 Cauchy 应力 |
| 当前应力 | $\boldsymbol\sigma=J^{-1}\mathbf F\mathbf S\mathbf F^T$ | 忽略 $J$ 或构形变换 |
| 残量 | $r=f_{ext}-f_{int}$ | Newton 修正方向相反 |
| 总切线 | $K_t=K_{mat}+K_{geo}+K_{rot}+K_{stab}-K_{load}$；本题 $K_{rot}=K_{stab}=0$ | 漏掉几何、旋转、稳定化或随动力项 |
| 差分符号 | $K_t\approx-[r(q+h_{fd})-r(q-h_{fd})]/(2h_{fd})$ | 用正号得到 $-K_t$ |
| Newton | $24\to0.484\to2.12\times10^{-4}\to4.06\times10^{-11}$ | 残量停滞或线性下降 |
| 最终平衡 | $f_{ext}=f_{int}=236.6431913\ \mathrm{N\,mm}$ | 内外力不相等 |
| 状态协议 | 收敛后一次 commit；失败完整 rollback | 全局迭代中污染 committed |

### 4.2 建议验收阈值

- 用精确三角函数或双精度程序检查旋转正交、director 范数和客观应变时，目标可取 $10^{-12}$ 左右；只用正文显示的 7 位小数手算时，误差达到 $10^{-7}$ 左右即可。
- 最终相对残量：
  $$
  \frac{|r|}{\max(|f_{ext}|,|f_{int}|,1\ \mathrm{N\,mm})}<10^{-8}.
  $$
- 最终修正：$|\Delta q|<10^{-8}$。
- 方向差分至少扫描 $h_{fd}=10^{-2},10^{-3},\ldots,10^{-8}$，确认存在二阶区和舍入误差谷值。
- 强制失败后，committed 快照或规范化哈希必须与步首完全相同。

### 4.3 必须停止并回退的情况

- $J=1+q\le0$；
- director 归一化或局部基正交检查失败；
- 残量、切线、应力或能量出现非有限值；
- trial 状态污染 committed；
- 减小差分步长后始终没有合理误差区；
- 省略 $K_{load}$ 后仍把切线称为“一致切线”。

---

## 五、边界

1. **教学模态边界**：$q$ 同时控制轴向伸展和有限转角，是为了把多个数学核心压缩到一个可手算变量中；它不是由某个标准 Reissner–Mindlin、MITC 或 solid-shell 单元直接推导出的自由度关系。
2. **共轴转动边界**：本题始终绕 $y$ 轴转动，左乘与右乘恰好交换。一般三维非共轴转动中必须区分空间增量和材料增量。
3. **旋转切线边界**：本题 $K_{rot}=0$ 是因为均匀共转矩阵在 $\mathbf F^T\mathbf F$ 中消去。一般壳单元的 director、局部基、插值、稳定化和旋转参数化通常产生非零切线。
4. **随动力非对称性边界**：单自由度切线只是一个标量，无法暴露一般 follower-load 矩阵的非对称性。真实多自由度、开放边界或非保守随动力问题不得强制使用对称切线或对称求解器。
5. **材料边界**：本题采用教学用单轴 St. Venant–Kirchhoff 材料，只演练应变、应力和切线链；不代表该材料适用于任意大应变工程分析。
6. **厚度与壳行为边界**：厚度固定，未演练厚度积分、$\sigma_{33}=0$ 局部 Newton、平面应力凝聚、塑性前沿、层合材料或厚度伸长。
7. **单元边界**：未覆盖弯曲/剪切插值、MITC tying、锁死、钻转、hourglass、畸变网格和稳定化参数。
8. **路径边界**：本题分支单调，无极限点或分岔；不能用来证明弧长、分支切换或后屈曲路径正确。
9. **结论边界**：本题只属于数学单元级演算，不能支持壳单元通过、系统 benchmark、GNIA/GMNIA、规范承载力或工程设计结论。

---

## 六、资料依据

### 6.1 本地资料路由

本题是依据本地数学核心包综合设计的教学算例，并非某一本参考书中的原题。主要依据如下：

| 本题内容 | 本地依据 | 行号 |
|---|---|---:|
| director 与 $SO(3)$ 指数更新 | `../4_General-Nonlinear-Shell_16-24周/01_核心算法/核心算法与实现顺序.md` | 56–81 |
| TL、UL、功共轭与客观性 | 同上 | 83–121 |
| 残量、内力与总切线 | 同上 | 123–175 |
| 中心方向差分及负号 | 同上 | 177–189 |
| trial/commit/rollback | 同上 | 223–241 |
| 随形压力与载荷刚度 | 同上 | 243–259 |
| Newton、控制与弧长边界 | 同上 | 274–301 |
| V00–V05 题目 | `../4_General-Nonlinear-Shell_16-24周/03_验证题目与答案/验证题目.md` | 9–91 |
| V00–V05 标准数值与符号 | `../4_General-Nonlinear-Shell_16-24周/03_验证题目与答案/配套答案.md` | 3–134 |
| V12 回滚与哈希验收 | 同上 | 280–295 |
| 验证顺序与阶段闸门 | `../4_General-Nonlinear-Shell_16-24周/03_验证题目与答案/验证矩阵.md` | 3–40 |
| 第 3–8、15–16 周学习位置 | `../4_General-Nonlinear-Shell_16-24周/06_学习路线/16-24周学习路线.md` | 17–30 |
| 原书主题与 PDF 页路由 | `../4_General-Nonlinear-Shell_16-24周/05_来源映射/参考资料与范围映射.md` | 21–31 |
| 规范残量、转动、状态与禁止推断 | `../4_General-Nonlinear-Shell_16-24周/AI_USAGE.md` | 18–106 |
| 转动、随动力、Newton 与状态边界 | `../4_General-Nonlinear-Shell_16-24周/02_算法局限/算法局限与适用边界.md` | 14–43、61–70、97–127 |

来源映射进一步把相关主题指向：

- Chapelle–Bathe：壳几何、一般壳单元与非线性壳分析；
- de Borst：TL/UL、应力度量、材料/几何切线、Newton 与弧长；
- Bonet：有限转动、客观性、内外虚功、压力线性化及一致切线。

### 6.2 包完整性检查

可在本文件所在目录执行：

```bash
python3 ../4_General-Nonlinear-Shell_16-24周/07_可复现脚本/validate_package.py
```

已复核输出为：

```text
Package validation: OK documents=20 verification_pairs=15
```

该脚本检查索引、V00–V14 题答配对和 manifest 完整性；其逻辑位于
`../4_General-Nonlinear-Shell_16-24周/07_可复现脚本/validate_package.py:23–73`。它不能代替本题的手算、方向差分和状态事务检查。
