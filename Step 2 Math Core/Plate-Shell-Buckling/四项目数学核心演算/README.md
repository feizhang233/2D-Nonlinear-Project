# 四项目数学核心演算

这是一套按数学依赖关系组织的四步手算练习。每一步先给题目，再给完整解答、自检和适用边界。建议先只看“题目区”，独立演算后再对照答案。

## 四步顺序

1. [`Plate-Shell-Buckling`](Step1_Plate-Shell-Buckling_演算题.md)：由板弯曲刚度、能量/Rayleigh 商走到广义特征屈曲；建议 60–90 分钟。
2. [`Shell-Instability-Research-Math-Core`](Step2_Shell-Instability-Research_演算题.md)：由平衡路径走到切线奇异、极限点/分岔分类、弧长与局部 Koiter 约化；建议 90–120 分钟。
3. [`Constitutive Nonlinearity`](Step3_Constitutive-Nonlinearity_演算题.md)：在材料点完成 J2 弹塑性预测-校正、一致切线、状态提交与回滚；建议 90–120 分钟。
4. [`General Nonlinear Shell`](Step4_General-Nonlinear-Shell_演算题.md)：把有限转动、客观应变/应力、材料与几何切线、随动力和全局 Newton 路径统一起来；建议 90–120 分钟。

机器可读路由见 [`EXERCISE_INDEX.json`](EXERCISE_INDEX.json)。

## 统一学习方法

每一步建议按以下顺序完成：

1. 抄写已知量并统一单位；
2. 先写符号公式，再代数字；
3. 每得到一个中间量，立刻检查量纲、正负号和数量级；
4. 独立算完题目区后，再打开同一文件的完整解答；
5. 最后口述“这个结果能说明什么、不能说明什么”。

## 残量符号提醒

- 第 2 步资料包采用 `R = f_int - lambda f_ref`，Newton 线性化为 `K_T dq - f_ref dlambda = -R`。
- 第 4 步资料包采用 `r = f_ext - f_int`，Newton 方程为 `K_t dq = r`。
- 两套写法都可以，但同一推导中必须整套一致，不能只把某一项换号。

## 范围

这些是教学与验证级演算题，不是设计规范验算、试验标定或生产级 GMNIA 结论。线性特征值、切线奇异点、极限点、分岔点和含缺陷极限载荷会被明确区分。

本次本地文件夹内的讲义、算法合同、验证题/答案和可复现脚本已经足以支撑四道新题，因此没有额外引入网络资料。
