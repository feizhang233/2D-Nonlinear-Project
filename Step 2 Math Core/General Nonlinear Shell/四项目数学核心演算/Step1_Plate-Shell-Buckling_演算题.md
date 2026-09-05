# 步骤 1：Plate-Shell-Buckling 演算题

## 1. 本步要打通的数学链

$$
E,\nu,h
\rightarrow D
\rightarrow \text{容许屈曲模态}
\rightarrow N_{x,cr}
\rightarrow \sigma_{cr},P_{cr}
\rightarrow (\mathbf K_M-\lambda\mathbf K_G)\boldsymbol\phi=\mathbf0.
$$

本题只讨论完美几何、线弹性、四边简支、均匀单向面内压缩下的线性分岔屈曲。

---

## 2. 题目区：矩形钢板的解析屈曲与二自由度离散复核

一块四边简支矩形钢板满足：

| 量 | 数值 |
|---|---:|
| 长度 | $a=1500\ \mathrm{mm}$ |
| 宽度 | $b=600\ \mathrm{mm}$ |
| 厚度 | $h=8\ \mathrm{mm}$ |
| 弹性模量 | $E=200000\ \mathrm{MPa}$ |
| 泊松比 | $\nu=0.30$ |

沿 $x$ 方向施加均匀压缩膜力 $N_x>0$，$N_y=N_{xy}=0$。取第一横向半波 $n=1$。

### A. 弯曲刚度

计算板弯曲刚度

$$
D=\frac{Eh^3}{12(1-\nu^2)},
$$

并写出它的单位。

### B. 整数半波选择

令长宽比 $r=a/b$。对 $m=1,2,3,4$ 分别计算

$$
k_m=\left(\frac{m}{r}+\frac{r}{m}\right)^2.
$$

找出最危险的整数 $m$，并说明为什么不能直接取连续最优值 $m=r$。

### C. 解析临界载荷

用

$$
N_{x,cr}(m)=k_m\frac{\pi^2D}{b^2}
$$

计算：

1. 第一临界膜力 $N_{x,cr}$，单位为 $\mathrm{N/mm}$；
2. 临界应力 $\sigma_{cr}=N_{x,cr}/h$；
3. 受压边总临界力 $P_{cr}=N_{x,cr}b$；
4. $x$ 方向每个半波的长度 $a/m$。

### D. Rayleigh 商试算

为练习广义特征值流程，另给一个独立的、归一化的教学用二自由度模型：

$$
\mathbf K_M=
\begin{bmatrix}10&-2\\-2&5\end{bmatrix},\qquad
\mathbf K_G=
\begin{bmatrix}1&0.1\\0.1&0.4\end{bmatrix}.
$$

矩阵已用一致基准归一化，故 $\lambda$ 为无量纲载荷倍率。题目没有给出这组矩阵与上述矩形板之间的单元组装映射，因此它不能被当成该钢板的有限元离散证据。用试向量

$$
\boldsymbol\phi_t=(1,1)^T
$$

计算 Rayleigh 商

$$
\lambda_R=
\frac{\boldsymbol\phi_t^T\mathbf K_M\boldsymbol\phi_t}
{\boldsymbol\phi_t^T\mathbf K_G\boldsymbol\phi_t}.
$$

### E. 广义特征值手算

1. 展开 $\det(\mathbf K_M-\lambda\mathbf K_G)=0$；
2. 求两个正特征值；
3. 将各特征向量第一分量归一成 1；
4. 用 $\|\mathbf K_M\phi-\lambda\mathbf K_G\phi\|_2$ 检查第一模态残差。

若参考载荷为 $P_{ref}=100\ \mathrm{kN}$，求两个离散临界载荷。

### F. 数值尺度比较与不可推断边界

把 C 的解析临界总边力换成参考载荷倍率

$$
\lambda_{ana}=\frac{P_{cr}}{P_{ref}},
$$

再计算二自由度第一特征值相对解析值的数值差异。为什么不能仅凭这个百分比把它称为上述钢板的“有限元离散误差”？若要做真正的解析-有限元误差研究，还缺少什么证据？

### G. 结论边界

列出至少四项本次线性特征屈曲演算不能直接回答的问题。

---

## 3. 完整解答

### A. 弯曲刚度

注意 $1\ \mathrm{MPa}=1\ \mathrm{N/mm^2}$：

$$
\begin{aligned}
D
&=\frac{200000\times8^3}{12(1-0.30^2)}\\
&=\frac{102400000}{10.92}\\
&=9.377289\times10^6\ \mathrm{N\,mm}.
\end{aligned}
$$

量纲核对：$(\mathrm{N/mm^2})(\mathrm{mm^3})=\mathrm{N\,mm}$。

### B. 整数半波选择

$$
r=\frac{1500}{600}=2.5.
$$

| $m$ | $k_m=(m/r+r/m)^2$ | 相对危险性 |
|---:|---:|---|
| 1 | 8.410000 | 很高 |
| 2 | 4.202500 | 候选 |
| 3 | 4.134444 | 最小 |
| 4 | 4.950625 | 回升 |

所以第一模态取 $(m,n)=(3,1)$。

连续最小化给 $m=r=2.5$，但有限板的简支 Navier 模态要求 $m$ 为正整数；$2.5$ 只告诉我们应重点比较相邻的 $m=2$ 与 $m=3$。

### C. 解析临界载荷

先计算公共因子：

$$
\frac{\pi^2D}{b^2}
=\frac{\pi^2(9.377289\times10^6)}{600^2}
=257.083713\ \mathrm{N/mm}.
$$

采用 $m=3$：

$$
\begin{aligned}
N_{x,cr}
&=4.134444\times257.083713\\
&=1062.898\ \mathrm{N/mm},\\[4pt]
\sigma_{cr}
&=\frac{1062.898}{8}
=132.862\ \mathrm{MPa},\\[4pt]
P_{cr}
&=1062.898\times600\\
&=637738.996\ \mathrm N
=637.739\ \mathrm{kN}.
\end{aligned}
$$

每个 $x$ 向半波长度为

$$
\frac{a}{m}=\frac{1500}{3}=500\ \mathrm{mm}.
$$

一个有用的近模态检查是：$m=2$ 时 $P_{cr}=648.237\ \mathrm{kN}$，只比 $m=3$ 高约 $1.65\%$。因此离散模型若太粗，可能交换这两个近邻模态的排序。

### D. Rayleigh 商

分子为

$$
\boldsymbol\phi_t^T\mathbf K_M\boldsymbol\phi_t
=(1,1)
\begin{bmatrix}8\\3\end{bmatrix}
=11.
$$

分母为

$$
\boldsymbol\phi_t^T\mathbf K_G\boldsymbol\phi_t
=(1,1)
\begin{bmatrix}1.1\\0.5\end{bmatrix}
=1.6.
$$

故

$$
\boxed{\lambda_R=\frac{11}{1.6}=6.875}.
$$

它已很接近真实第一离散特征值，但仍高于最小值，因为试向量不是精确特征向量。

### E. 广义特征值

$$
\mathbf K_M-\lambda\mathbf K_G=
\begin{bmatrix}
10-\lambda&-2-0.1\lambda\\
-2-0.1\lambda&5-0.4\lambda
\end{bmatrix}.
$$

因此

$$
\begin{aligned}
0
&=(10-\lambda)(5-0.4\lambda)-(-2-0.1\lambda)^2\\
&=0.39\lambda^2-9.4\lambda+46.
\end{aligned}
$$

$$
\lambda_{1,2}
=\frac{9.4\mp\sqrt{9.4^2-4(0.39)(46)}}{2(0.39)},
$$

得到

$$
\boxed{\lambda_1=6.827808},\qquad
\boxed{\lambda_2=17.274756}.
$$

把第一分量取为 1，由第一行方程

$$
(10-\lambda)+(-2-0.1\lambda)y=0
$$

可得

$$
\boldsymbol\phi_1\propto(1,1.182427)^T,
\qquad
\boldsymbol\phi_2\propto(1,-1.951658)^T.
$$

使用未截断的

$$
\lambda_1=6.827808003214523,
\qquad
\boldsymbol\phi_1=(1,1.182426829804874)^T
$$

代回：

$$
\mathbf K_M\boldsymbol\phi_1
-\lambda_1\mathbf K_G\boldsymbol\phi_1
\approx(-8.9\times10^{-16},-4.4\times10^{-16})^T,
$$

所以二范数约为 $9.9\times10^{-16}$，处于舍入误差级。

对应离散临界载荷为

$$
P_{cr,1}=6.827808\times100=682.781\ \mathrm{kN},
$$

$$
P_{cr,2}=17.274756\times100=1727.476\ \mathrm{kN}.
$$

### F. 数值尺度比较与解释边界

$$
\lambda_{ana}=\frac{637.739}{100}=6.377390.
$$

教学二自由度模型的第一值相对数值差异为

$$
\frac{6.827808-6.377390}{6.377390}\times100\%
=\boxed{+7.063\%}.
$$

这个 $+7.063\%$ 只是两组题设数字的尺度比较，**不能直接称为上述钢板的有限元离散误差**。原因是题目没有说明 $\mathbf K_M$、$\mathbf K_G$ 如何由该钢板的几何、材料、边界、参考载荷和预应力场组装而来。

若要开展真正的解析-有限元误差研究，至少还要：

1. 用同一块钢板、同一边界和同一参考载荷求已平衡的屈曲前应力；
2. 由该应力一致组装材料刚度与几何刚度；
3. 记录自由度、单元、积分、约束和归一化映射；
4. 做网格加密并检查临界值、半波数和临界子空间收敛。

只有在这些映射与收敛证据齐全后，差异才可合理归因于离散子空间、网格或单元误差。

### G. 这一步不能直接回答什么

本次结果不能直接给出：

1. 含初始几何缺陷时的第一极限载荷；
2. 材料屈服、残余应力或厚度偏差后的承载力；
3. 分岔后的路径斜率、稳定性和实际可达分支；
4. 边界柔度、载荷引入、接触或随动力的影响；
5. 规范设计值或统计可靠度下限。

线性特征值只是完美基本路径附近的局部中性条件和模态信息。

---

## 4. 最终自检

- $D$ 的单位是 $\mathrm{N\,mm}$，不是 $\mathrm{N/mm}$。
- $N_x$ 是膜力合力，单位为 $\mathrm{N/mm}$；只有除以厚度后才是应力。
- 有限尺寸板必须搜索整数半波数。
- 几何刚度必须来自已平衡的屈曲前应力状态。
- 只接受正的候选载荷倍率，并检查特征残差。
- 接近或重合的特征值应按临界子空间处理，不应迷信单个模态编号。
- 独立教学矩阵与解析板数值接近，不等于已经建立有限元模型映射。

## 5. 资料依据

- `../Shell-Instability-Research_Math-Core-Guide/04_完整参考/Plate_Shell_Buckling_完整數學推導與例題_繁中.pdf`：第 8-10 页的矩形板解析式，第 14-18 页的几何刚度、Rayleigh 商、广义特征值和验证边界。
- `../Shell-Instability-Research_Math-Core-Guide/01_核心算法/核心算法与实现顺序.md`：线性特征屈曲的预应力、矩阵和残差检查流程。
- `../Shell-Instability-Research_Math-Core-Guide/02_算法局限/算法局限与适用边界.md`：线性特征值的结论边界。
