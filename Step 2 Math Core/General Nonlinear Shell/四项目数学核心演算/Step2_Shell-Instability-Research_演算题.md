# Step 2　Shell Instability Research 数学核心演算

## 学习目标

本步用一条连贯的教学算例，区分并联系以下对象：

1. 完美基本路径的线性特征屈曲值；
2. 切线刚度失去满秩的奇异点；
3. 经左零向量投影分类的分岔点；
4. 同一次级平衡分支上的普通极限点；
5. 临界点附近的单模态 Koiter 近似；
6. 用一步球形弧长法跨过极限点。

> **使用方法**：先独立完成“题目区”，并保留所有中间步骤、单位和对象名称；完成后再打开“完整答案”核对。建议纸笔时间为 90–120 分钟。

---

## 1. 统一模型、符号与单位

### 1.1 线性屈曲基线

某完美薄壳在已经平衡的参考载荷

$$
P_{\mathrm{ref}}=10\ \mathrm{kN}
$$

下，得到线性特征屈曲矩阵

$$
\mathbf K_M=
\begin{bmatrix}
12&-2\\
-2&6
\end{bmatrix},
\qquad
\mathbf K_G=
\begin{bmatrix}
1&0.2\\
0.2&0.5
\end{bmatrix}.
$$

其中，$\lambda$ 是无量纲载荷倍数，

$$
P=\lambda P_{\mathrm{ref}}.
$$

$\mathbf K_M$ 与 $\mathbf K_G$ 已使用相容的广义刚度单位。特征向量只表示方向，它的符号和尺度必须由明确的归一化来固定。

### 1.2 教学用后屈曲正规形

得到第一线性临界载荷 $P_{\mathrm{cr},1}$ 后，定义

$$
p=\frac{P}{P_{\mathrm{cr},1}}.
$$

用 $a$ 表示第一临界模态的无量纲幅值，用 $u$ 表示加载方向的无量纲广义位移。本题定义无量纲势能

$$
\widehat\Pi(u,a,p)
=\frac12u^2+\frac12(1-u)a^2+\frac1{24}a^6-pu.
$$

> **重要边界**：这个正规形、其中的非线性系数以及六次项 $a^6/24$ 都是为了连贯演算而新建的**教学构造**。它们不能从上述两个线性矩阵中唯一推导，也不能冒充真实壳体的 Koiter 系数、有限元后屈曲路径或工程承载力。

本题全程采用残量约定

$$
\mathbf R(\mathbf q,p)
=\mathbf f_{\mathrm{int}}(\mathbf q)-p\mathbf f_{\mathrm{ref}}
=\mathbf0,
\qquad
\mathbf q=(u,a)^T.
$$

---

# 题目区

## 2. A 题：线性特征屈曲

1. 展开特征方程

   $$
   \det(\mathbf K_M-\lambda\mathbf K_G)=0.
   $$

2. 求两个正特征值及对应的模态方向。
3. 使用 $P_{\mathrm{ref}}=10\ \mathrm{kN}$ 计算两个临界载荷。
4. 对所求模态检查

   $$
   \left\|\mathbf K_M\boldsymbol\phi
   -\lambda\mathbf K_G\boldsymbol\phi\right\|.
   $$

5. 说明此处计算的“临界值”属于哪一类失稳对象，以及它不能直接回答的问题。

## 3. B 题：基本路径、切线奇异与分岔

1. 由 $\widehat\Pi$ 推导

   $$
   \mathbf R=\frac{\partial\widehat\Pi}{\partial\mathbf q},
   \qquad
   \mathbf K_T=\frac{\partial\mathbf R}{\partial\mathbf q}.
   $$

2. 求 $a=0$ 时的完美基本路径。
3. 求基本路径上第一个 $\mathbf K_T$ 奇异点，并给出左、右零向量。
4. 计算无量纲投影

   $$
   \frac{\boldsymbol\psi^T\mathbf f_{\mathrm{ref}}}
   {\|\boldsymbol\psi\|\,\|\mathbf f_{\mathrm{ref}}\|},
   $$

   并把该点分类为普通极限点或分岔候选点。
5. 不只依赖 $\det\mathbf K_T=0$：继续求 $a\neq0$ 的精确平衡分支，用它验证临界点附近是否确实存在另一条平衡分支。

## 4. C 题：次级分支上的普通极限点

1. 在 $a\neq0$ 时，由 $\mathbf R=\mathbf0$ 求 $u(a)$ 和 $p(a)$。
2. 求除 $a=0$ 以外满足 $dp/da=0$ 的点。
3. 在正幅值分支的该点计算：
   - $\mathbf R$；
   - $\mathbf K_T$；
   - $\mathbf K_T$ 的特征值和零向量；
   - $\boldsymbol\psi^T\mathbf f_{\mathrm{ref}}$。
4. 判断它是普通极限点还是分岔点，并说明它是载荷参数的局部最大值还是局部最小值。
5. 把 $u(a)$ 代回 $\mathbf K_T$，用行列式和矩阵惯性判断次级分支在极限点前后的局部稳定性。
6. 对比 B 题与 C 题：为什么两点都满足 $\det\mathbf K_T=0$，却必须得到不同的物理分类？

## 5. D 题：简化 Koiter 演算

1. 由第一条平衡方程消去 $u$，并将势能化为只关于 $a,p$ 的约化势能。
2. 将与 $a$ 无关的常数项删去，再把势能乘以适当的正常数，写成

   $$
   \overline F(a,p)
   =(1-p)a^2+A_3a^3+A_4a^4+O(a^6).
   $$

3. 识别 $A_3,A_4$，判断局部分岔属于对称超临界还是对称次临界。
4. 求非零分支上的幅值 Hessian，分别在 $a=0.5$ 和 $a=1.2$ 处检查其符号。
5. 解释：为什么仅保留四次 Koiter 项时，不能预测本题远离分岔点的再稳定现象？

## 6. E 题（可选进阶）：球形弧长法跨过极限点

在正次级分支上，对 $a\neq0$ 的平衡方程除以 $a$，得

$$
h(a,p)=1-p-\frac12a^2+\frac14a^4=0.
$$

取已收敛点

$$
(a_n,p_n)=(0.9,0.759025),
$$

以及

$$
\Delta s=0.12,
\qquad
\beta=1,
\qquad
f_{\mathrm{ref}}=1.
$$

1. 验证起点满足 $h=0$。
2. 求标量切线 $K_h=\partial h/\partial a$ 和切向量 $a_t$。
3. 选择能使 $a$ 继续增大的预测符号，计算

   $$
   \Delta p_p
   =\pm\frac{\Delta s}{\sqrt{a_t^2+1}},
   \qquad
   \Delta a_p=a_t\Delta p_p.
   $$

4. 写出增广 Newton 系统，并从预测点迭代到同时满足

   $$
   h=0,
   \qquad
   (a-a_n)^2+(p-p_n)^2-\Delta s^2=0
   $$

   的交点。
5. 根据收敛点的 $a,p$ 判断该步是否跨过了理论极限点。

---

# 完整答案

## 7. A 题答案：线性特征屈曲

特征方程为

$$
\begin{aligned}
\det(\mathbf K_M-\lambda\mathbf K_G)
&=(12-\lambda)(6-0.5\lambda)-(-2-0.2\lambda)^2\\
&=0.46\lambda^2-12.8\lambda+68=0.
\end{aligned}
$$

判别式为

$$
12.8^2-4(0.46)(68)=38.72.
$$

两个正特征值为

$$
\lambda_1=7.149413397,
\qquad
\lambda_2=20.676673559.
$$

对应模态方向可取

$$
\boldsymbol\phi_1\propto
\begin{bmatrix}1\\ \sqrt2\end{bmatrix},
\qquad
\boldsymbol\phi_2\propto
\begin{bmatrix}1\\ -\sqrt2\end{bmatrix}.
$$

若使用 $\boldsymbol\phi_i^T\mathbf K_G\boldsymbol\phi_i=1$ 归一化，则

$$
\boldsymbol\phi_1=
\begin{bmatrix}
0.624307\\
0.882904
\end{bmatrix}.
$$

两个临界载荷为

$$
P_{\mathrm{cr},1}
=\lambda_1P_{\mathrm{ref}}
=7.149413397(10)
=71.4941\ \mathrm{kN},
$$

$$
P_{\mathrm{cr},2}
=\lambda_2P_{\mathrm{ref}}
=20.676673559(10)
=206.7667\ \mathrm{kN}.
$$

使用上述显示精度回代，两个未归一化模态的残差范数约为

$$
5.4\times10^{-10},
\qquad
1.5\times10^{-10}.
$$

$\lambda_1,\lambda_2$ 是**完美基本路径的线性特征屈曲值**。它们不能单独给出含缺陷极限载荷、后屈曲分支稳定性或考虑材料、接触和实际边界后的工程失效载荷。

本题中

$$
\frac{\lambda_2}{\lambda_1}\approx2.892,
$$

所以使用第一模态做局部教学约化比较清楚；但该比值不能替代真实壳模型的模态簇和子空间检查。

## 8. B 题答案：基本路径与分岔

对势能求一阶导数：

$$
\mathbf R=
\begin{bmatrix}
u-\tfrac12a^2-p\\
(1-u)a+\tfrac14a^5
\end{bmatrix}.
$$

因此

$$
\mathbf f_{\mathrm{int}}=
\begin{bmatrix}
u-\tfrac12a^2\\
(1-u)a+\tfrac14a^5
\end{bmatrix},
\qquad
\mathbf f_{\mathrm{ref}}=
\begin{bmatrix}1\\0\end{bmatrix}.
$$

一致切线为

$$
\mathbf K_T=
\begin{bmatrix}
1&-a\\
-a&1-u+\tfrac54a^4
\end{bmatrix}.
$$

当 $a=0$ 时，第一条平衡方程给出

$$
u=p,
$$

所以完美基本路径为

$$
\mathbf q_0(p)=
\begin{bmatrix}p\\0\end{bmatrix},
\qquad
\mathbf K_T^{(0)}=
\begin{bmatrix}
1&0\\
0&1-p
\end{bmatrix}.
$$

在

$$
B:(u,a,p)=(1,0,1)
$$

处，

$$
\mathbf R_B=\mathbf0,
\qquad
\mathbf K_B=
\begin{bmatrix}
1&0\\
0&0
\end{bmatrix}.
$$

本题是保守对称系统，因此左、右零向量可取为同一向量：

$$
\boldsymbol\phi_B
=\boldsymbol\psi_B
=\begin{bmatrix}0\\1\end{bmatrix}.
$$

归一化投影为

$$
\frac{\boldsymbol\psi_B^T\mathbf f_{\mathrm{ref}}}
{\|\boldsymbol\psi_B\|\,\|\mathbf f_{\mathrm{ref}}\|}
=0.
$$

因此，仅根据左零向量相容条件，$B$ 应先称为**分岔候选点**，而不是普通极限点。

下面直接求另一条平衡分支。对 $a\neq0$，第二条平衡方程给出

$$
1-u+\frac14a^4=0.
$$

因此

$$
u=1+\frac14a^4,
\qquad
p=1-\frac12a^2+\frac14a^4.
$$

当 $a\rightarrow0$ 时，该非零分支趋向 $(u,a,p)=(1,0,1)$。对这个明确的代数正规形，因而可以在模型内确认 $B$ 是对称分岔点；真实全阶壳模型仍需要临界点精确定位、零空间解析、受控种子与全阶平衡校正。

## 9. C 题答案：普通极限点

次级分支为

$$
u(a)=1+\frac14a^4,
\qquad
p(a)=1-\frac12a^2+\frac14a^4.
$$

对载荷参数求导：

$$
\frac{dp}{da}=-a+a^3=a(a^2-1).
$$

除 $a=0$ 的分岔点外，正幅值分支的转折点为

$$
a_L=1,
\qquad
u_L=1+\frac14=1.25,
\qquad
p_L=1-\frac12+\frac14=0.75.
$$

对应物理载荷为

$$
P_L=p_LP_{\mathrm{cr},1}
=0.75(71.4941)
=53.6206\ \mathrm{kN}.
$$

平衡残量回代为

$$
R_u=1.25-\frac12-0.75=0,
$$

$$
R_a=(1-1.25)(1)+\frac14(1)^5=0.
$$

切线为

$$
\mathbf K_L=
\begin{bmatrix}
1&-1\\
-1&1
\end{bmatrix}.
$$

其特征值为 $0,2$，左、右零向量可取

$$
\boldsymbol\phi_L
=\boldsymbol\psi_L
=\frac1{\sqrt2}
\begin{bmatrix}1\\1\end{bmatrix}.
$$

此时

$$
\boldsymbol\psi_L^T\mathbf f_{\mathrm{ref}}
=\frac1{\sqrt2}\neq0.
$$

增量相容条件因而迫使 $dp=0$，所以 $L$ 是**普通极限点**。又因为

$$
\frac{d^2p}{da^2}\bigg|_{a=1}
=-1+3a^2
=2>0,
$$

该点是次级分支上载荷参数的局部最小值。

将 $u=1+a^4/4$ 代回切线：

$$
\mathbf K_T=
\begin{bmatrix}
1&-a\\
-a&a^4
\end{bmatrix},
\qquad
\det\mathbf K_T=a^2(a^2-1).
$$

因此：

- $0<|a|<1$：$\det\mathbf K_T<0$，有一个负特征值，次级分支局部不稳定；
- $|a|=1$：出现零特征值；
- $|a|>1$：$K_{11}>0$ 且 $\det\mathbf K_T>0$，切线正定，次级分支局部稳定。

### 两个切线奇异点的分类对照

| 点 | 平衡坐标 $(u,a,p)$ | $\mathbf K_T$ 特征值 | $\boldsymbol\psi^T\mathbf f_{\mathrm{ref}}$ | 分类 |
|---|---|---:|---:|---|
| $B$ | $(1,0,1)$ | $1,0$ | $0$ | 分岔候选；本正规形的显式次级分支将其确认为分岔点 |
| $L$ | $(1.25,1,0.75)$ | $2,0$ | $1/\sqrt2$ | 普通极限点 |

两点都有 $\det\mathbf K_T=0$，但载荷导数在左零空间上的投影不同。因此，“切线奇异点”是检测结果，不是已经完成的物理分类。

## 10. D 题答案：Koiter 局部约化

由 $R_u=0$ 得

$$
u=p+\frac12a^2.
$$

将它代回势能：

$$
\widehat\Pi
=-\frac12p^2
+\frac12(1-p)a^2
-\frac18a^4
+\frac1{24}a^6.
$$

删去与 $a$ 无关的 $-p^2/2$，再乘以正数 2。正数缩放不改变驻值位置和 Hessian 的符号，所以可定义

$$
\overline F(a,p)
=(1-p)a^2-\frac14a^4+\frac1{12}a^6.
$$

在 $a=0$ 附近，

$$
A_3=0,
\qquad
A_4=-\frac14<0.
$$

因此该局部分岔是**对称次临界分岔**。

幅值驻值条件为

$$
\overline F_{,a}
=2(1-p)a-a^3+\frac12a^5=0.
$$

对 $a\neq0$ 除以 $2a$，再次得到

$$
p=1-\frac12a^2+\frac14a^4.
$$

幅值 Hessian 为

$$
\overline F_{,aa}
=2(1-p)-3a^2+\frac52a^4.
$$

代入非零分支后，

$$
\overline F_{,aa}=2a^2(a^2-1).
$$

所以

$$
a=0.5:
\qquad
\overline F_{,aa}
=2(0.5)^2\bigl((0.5)^2-1\bigr)
=-0.375<0,
$$

$$
a=1.2:
\qquad
\overline F_{,aa}
=2(1.2)^2\bigl((1.2)^2-1\bigr)
=1.2672>0.
$$

负四次系数描述的是临界邻域中的次临界趋势。如果把本题人为加入的六次项删去，约化分支为 $p=1-a^2/2$，不会出现 $a=1$ 处的再稳定转折。因此，远离临界点的极限点不能由局部四次 Koiter 展开盲目外推。

> 再次强调：$A_4=-1/4$ 和 $a^6/12$ 是本题正规形经缩放后的**教学系数**，不是任何真实壳几何、材料、边界或网格的已验证 Koiter 系数。

## 11. E 题答案：球形弧长一步

首先验证起点：

$$
\begin{aligned}
h(0.9,0.759025)
&=1-0.759025-\frac12(0.9)^2+\frac14(0.9)^4\\
&=1-0.759025-0.405+0.164025\\
&=0.
\end{aligned}
$$

标量切线和切向量为

$$
K_h=\frac{\partial h}{\partial a}
=-a+a^3
=-0.9+(0.9)^3
=-0.171,
$$

$$
a_t=\frac1{K_h}=-5.847953.
$$

为了让 $a$ 继续增大，由于 $a_t<0$，应取负的 $\Delta p_p$：

$$
\Delta p_p
=-\frac{0.12}{\sqrt{(-5.847953)^2+1}}
=-0.02022641,
$$

$$
\Delta a_p
=a_t\Delta p_p
=0.11828310.
$$

预测点为

$$
(a_p,p_p)
=(1.01828310,0.73879859).
$$

预测点满足弧长约束，但不满足平衡：

$$
h(a_p,p_p)\approx0.01154182.
$$

定义

$$
g=(a-a_n)^2+(p-p_n)^2-(0.12)^2.
$$

增广 Newton 系统为

$$
\begin{bmatrix}
-a+a^3&-1\\
2(a-a_n)&2(p-p_n)
\end{bmatrix}
\begin{bmatrix}
\delta a\\
\delta p
\end{bmatrix}
=-
\begin{bmatrix}
h\\
g
\end{bmatrix}.
$$

从预测点开始校正，得

| 状态 | $a$ | $p$ | 本次校正 $(\delta a,\delta p)$ |
|---|---:|---:|---:|
| predictor | 1.018283102 | 0.738798589 | $(+0.001986415,+0.011616462)$ |
| corrector 1 | 1.020269517 | 0.750415051 | $(-0.000578836,-0.000020011)$ |
| corrector 2 | 1.019690681 | 0.750395040 | $(-0.000001380,+0.000000299)$ |
| converged | 1.019689302 | 0.750395339 | — |

表格只显示到 9 位小数。再做一次未显示的微小校正，约为

$$
(\delta a,\delta p)\approx(-8.21\times10^{-12},1.68\times10^{-12}),
$$

并以未截断值

$$
(a,p)=(1.019689301747216,0.7503953390991376)
$$

进行最终验收；若只把表中打印值代回，不能声称达到机器精度残量。

收敛点同时满足

$$
|h|<1.2\times10^{-16},
\qquad
|g|<2.1\times10^{-17}.
$$

理论极限点为

$$
(a_L,p_L)=(1,0.75).
$$

收敛点有 $a>1$，并且已经位于载荷参数重新上升的分支上，因此该弧长步已跨过极限点。对应的教学模型载荷为

使用计算内部保留精度的 $p$ 和第一临界载荷 $P_{cr,1}=71.4941339734607\ \mathrm{kN}$：

$$
P=0.7503953390991376(71.4941339734607)
=53.6488649066\ \mathrm{kN}
\approx53.6489\ \mathrm{kN}.
$$

弧长法只证明找到了一个满足增广方程的平衡点，不自动证明该路径稳定、唯一或能在动力试验中准静态实现。

---

## 12. 五类对象最终对照

| 对象 | 本题是否得到 | 本题中的结果 |
|---|---|---|
| 线性特征屈曲值 | 是 | $\lambda_1=7.149413397$，$P_{\mathrm{cr},1}=71.4941\ \mathrm{kN}$ |
| 切线奇异点 | 是 | $B$ 与 $L$ 均有 $\det\mathbf K_T=0$ |
| 分岔点 | 是，仅限教学正规形 | $B=(1,0,1)$，$\boldsymbol\psi^T\mathbf f_{\mathrm{ref}}=0$，并存在显式次级分支 |
| 完美模型的普通极限点 | 是，仅限教学正规形 | $L=(1.25,1,0.75)$，$P_L=53.6206\ \mathrm{kN}$ |
| 含缺陷壳的极限载荷 | **否** | 本题没有缺陷场、缺陷幅值或缺陷方向扫描 |

---

## 13. 纸笔自检清单

- [ ] 残量始终采用 $\mathbf R=\mathbf f_{\mathrm{int}}-p\mathbf f_{\mathrm{ref}}$，没有与 $\mathbf r=\mathbf f_{\mathrm{ext}}-\mathbf f_{\mathrm{int}}$ 局部混用。
- [ ] 特征屈曲前的 $\mathbf K_G$ 被解释为来自已平衡的参考预应力状态。
- [ ] 模态残差 $\|\mathbf K_M\phi-\lambda\mathbf K_G\phi\|$ 接近舍入误差级。
- [ ] 在 $B$ 和 $L$ 处都明确回代了 $\mathbf R=\mathbf0$。
- [ ] 没有把 $\det\mathbf K_T=0$ 直接等同于“分岔”。
- [ ] 使用了左零向量投影进行分类；只因本题对称保守，才令 $\boldsymbol\psi=\boldsymbol\phi$。
- [ ] 对分岔点不只有特征向量图，还显式得到了非零平衡分支。
- [ ] Koiter 判断使用了 $A_3=0,A_4<0$，并用 Hessian 符号检查局部稳定性。
- [ ] 弧长收敛点同时满足平衡残量与弧长约束。
- [ ] 已把“线性特征值”、“切线奇异点”、“分岔点”、“极限点”和“含缺陷极限载荷”分开命名。
- [ ] 没有把本题的 $P_L$ 称为真实壳体承载力或设计值。

---

## 14. 适用边界与未覆盖内容

1. **模型边界**：这是保守、对称、低自由度教学正规形，不是生产壳单元或完整 GMNIA 模型。
2. **系数边界**：非线性项、$A_4=-1/4$ 和六次项均为教学构造；真实系数需从全阶能量或内力的高阶方向导数求得并验证。
3. **模态边界**：本题使用单一孤立模态。重根或近重根时必须使用临界子空间、主夹角和含交叉项的多模态约化。
4. **非保守边界**：follower load、摩擦或非对称切线下，右零向量不能代替左零向量，势能正定性也不一定适用。
5. **Koiter 边界**：单模态 Koiter 是临界点邻域的小幅值渐近结果，不能盲目外推到远场、有限缺陷、接触或塑性主导状态。
6. **弧长边界**：弧长法解决路径参数化，不自动选出唯一、稳定或实验可实现的物理分支。
7. **数值边界**：本题的弧长步长、容差和无量纲化只服务于该算例，不是所有壳模型的通用阈值。
8. **工程边界**：本题没有几何缺陷、材料屈服或损伤、残余应力、接触、边界柔度、网格收敛、实验标定或规范折减系数。

---

## 15. 资料依据与新编内容说明

### 15.1 直接采用的包内规则和数值

| 用途 | 来源文件与行号 |
|---|---|
| 残量、Newton 符号与五类不可混用的对象 | `Shell-Instability-Research_Math-Core-Guide/AI_USAGE.md:17-42` |
| 稳定判据、最小特征值、惯性、奇异值和临界子空间 | `Shell-Instability-Research_Math-Core-Guide/01_核心算法/核心算法与实现顺序.md:29-90` |
| 左零向量的极限点/分岔点分类 | `Shell-Instability-Research_Math-Core-Guide/01_核心算法/核心算法与实现顺序.md:92-113` |
| 线性特征屈曲算法及解释边界 | `Shell-Instability-Research_Math-Core-Guide/01_核心算法/核心算法与实现顺序.md:115-146` |
| 球形弧长预测—校正及双残量验收 | `Shell-Instability-Research_Math-Core-Guide/01_核心算法/核心算法与实现顺序.md:148-195` |
| 单模态 Koiter 势能形式和 $A_4$ 符号解释 | `Shell-Instability-Research_Math-Core-Guide/01_核心算法/核心算法与实现顺序.md:197-233` |
| V01 左零向量分类的最小验证 | `Shell-Instability-Research_Math-Core-Guide/03_验证题目与答案/验证题目.md:25-42`；`Shell-Instability-Research_Math-Core-Guide/03_验证题目与答案/配套答案.md:31-38` |
| V02 二自由度矩阵、特征值、模态和临界载荷 | `Shell-Instability-Research_Math-Core-Guide/03_验证题目与答案/验证题目.md:44-59`；`Shell-Instability-Research_Math-Core-Guide/03_验证题目与答案/配套答案.md:40-71` |
| V03 超/次临界与 Hessian 符号检查 | `Shell-Instability-Research_Math-Core-Guide/03_验证题目与答案/配套答案.md:73-90` |
| V06 弧长增广方程和跨越极限点的验收方式 | `Shell-Instability-Research_Math-Core-Guide/03_验证题目与答案/配套答案.md:137-192` |
| 验证的固定顺序和最低门槛 | `Shell-Instability-Research_Math-Core-Guide/03_验证题目与答案/验证矩阵.md:3-28` |
| 线性屈曲、临界点分类、弧长与 Koiter 的学习顺序 | `Shell-Instability-Research_Math-Core-Guide/07_学习路线/8-12周研究路线.md:7-18` |
| 线性屈曲、分类、弧长、Koiter 和结论分级的适用边界 | `Shell-Instability-Research_Math-Core-Guide/02_算法局限/算法局限与适用边界.md:3-49,127-135` |

### 15.2 本题新编的教学内容

- 将 V02 线性屈曲基线与一个无量纲二坐标后屈曲正规形串联；
- 势能 $\widehat\Pi(u,a,p)$ 及其非线性系数；
- 用六次项构造“次临界分岔 $\rightarrow$ 极限点 $\rightarrow$ 再稳定”的完整教学路径；
- 从 $(a_n,p_n)=(0.9,0.759025)$ 出发的弧长步数值；
- 所有由该正规形得到的 $p_L$、$P_L$、Koiter 系数和稳定性结果。

这些新编内容仅用于手算训练和概念分类，不构成任何真实壳算例的实现证据。
