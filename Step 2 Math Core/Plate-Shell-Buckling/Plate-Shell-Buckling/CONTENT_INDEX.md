# 内容索引

## A. 快速入口

| ID | 内容 | 文件 | 适用问题 |
|---|---|---|---|
| G00 | 范围、周次、目录和完成边界 | `README.md` | 第一次进入资料包 |
| G01 | AI 路由、符号和禁止推断 | `AI_USAGE.md` | 回答或改代码前 |
| G02 | 目录级 AI 工作规则 | `AGENTS.md` | 在本资料包内修改内容时 |
| G03 | 人类可读路由 | `CONTENT_INDEX.md` | 快速定位文件/题目/页码 |
| A01 | 核心算法与实现顺序 | `01_核心算法/核心算法与实现顺序.md` | LBA、模态缺陷、后屈曲 |
| L01 | 算法局限与升级门槛 | `02_算法局限/算法局限与适用边界.md` | 评审适用性和结果结论 |
| Q01 | 独立验证题 | `03_验证题目与答案/验证题目.md` | 编写测试或面试自测前 |
| S01 | 配套答案 | `03_验证题目与答案/配套答案.md` | 完成题目后核对 |
| V01 | 验证矩阵 | `03_验证题目与答案/验证矩阵.md` | CI、回归和阶段闸门 |
| R00 | 完整参考导航 | `04_完整参考/README.md` | 选择完整讲义 |
| R01 | 线性板壳屈曲完整讲义 | `04_完整参考/Plate_Shell_Buckling_完整數學推導與例題_繁中.pdf` | 二次变分、板壳解析值、FE 特征值 |
| R02 | 壳失稳研究完整讲义 | `04_完整参考/Shell_Instability_Research_完整數學邏輯推導與例題_繁中.pdf` | Koiter、缺陷、弧长、后屈曲 |
| M01 | 主题与来源映射 | `05_来源映射/主题与来源映射.md` | 页码级追溯和来源边界 |
| M02 | 第 10–14 周 JSONL 映射 | `05_来源映射/第10-14周主题映射.jsonl` | AI 按周次机器检索 |
| C00 | 生成脚本说明 | `06_生成脚本/README.md` | 复现或维护 PDF 时 |
| C01 | 线性屈曲 PDF 脚本 | `06_生成脚本/generate_plate_shell_buckling_pdf.py` | 讲义内容来源/重建 |
| C02 | 壳失稳研究 PDF 脚本 | `06_生成脚本/generate_shell_instability_research_pdf.py` | 后屈曲讲义内容来源/重建 |

## B. 算法章节路由

| 目标 | 核心算法章节 |
|---|---|
| 范围、周次和分析层级 | 0–1 |
| 预屈曲平衡与应力场 | 2 |
| 几何刚度来源和符号 | 3 |
| 广义特征值、排序和过滤 | 4 |
| 模态归一化、MAC 和近重根 | 5 |
| 模态/局部/组合初始缺陷 | 6 |
| 后屈曲残量、切线、弧长和分支 | 7 |
| 建议实现伪代码 | 8 |
| 结果与证据契约 | 9 |
| 阶段闸门 | 10 |

## C. 验证题与答案配对

| Test ID | 主题 | 主要层级 |
|---|---|---|
| V10 | 平衡、稳定和二次变分 | LBA 基础 |
| V11 | 预屈曲平衡与几何刚度检查 | LBA |
| V12 | 二自由度广义特征值与正号 | LBA |
| V13 | 单向压缩矩形板解析基准 | LBA/板 |
| V14 | 等双向压缩方板 | LBA/板 |
| V15 | 纯剪切板模态耦合和收敛 | LBA/板 |
| V16 | 圆柱壳经典理想基准 | LBA/壳 |
| V17 | 模态归一化、符号、MAC 和重根 | LBA/模态 |
| V18 | 模态缺陷映射 | GNIA 准备 |
| V19 | Koiter 2/3 次方缺陷折减 | GNIA |
| V20 | 浅两杆拱极限点 | GNA/路径 |
| V21 | 弧长法与分支证据 | GNA/GNIA |
| V22 | LBA/GNA/GNIA/GMNIA 结论边界 | 全层级 |

题目统一位于 `验证题目.md#vXX`，答案统一位于 `配套答案.md#vXX`。

## D. 完整讲义页码路由

### R01：Plate/Shell Buckling（19 页）

| 主题 | PDF 页 |
|---|---:|
| 使用说明、范围、符号、目录 | 1–4 |
| 稳定、二次变分、特征值来源 | 5 |
| 薄板运动学、预应力二阶作功、强式 | 5–7 |
| 简支矩形板、双向压缩、纯剪切耦合 | 8–10 |
| 圆柱壳、球壳经典线性屈曲 | 11–14 |
| FE 几何刚度、Rayleigh 商、计算流程 | 14–15 |
| 6 个完整例题 | 16–18 |
| 验证、常见错误、适用界线、来源 | 18–19 |

### R02：Shell Instability Research（30 页）

| 主题 | PDF 页 |
|---|---:|
| 稳定、极限点和分岔分类 | 5–8 |
| Koiter 高阶约化与后屈曲方向 | 9–12 |
| 初始缺陷、1/2/2/3 尺度律、局部凹陷 | 13–16 |
| 浅壳、圆柱/球壳失稳 | 17–22 |
| FE 特征值、弧长、分支切换 | 23–26 |
| 6 个完整例题 | 27–29 |
| 研究矩阵、验证关卡、来源 | 29–30 |

## E. 搜索关键词

- 线性屈曲：`eigenvalue buckling`, `linear bifurcation`, `LBA`, `Rayleigh quotient`；
- 预应力：`prestress`, `prebuckling equilibrium`, `initial stress matrix`；
- 几何刚度：`geometric stiffness`, `K_sigma`, `K_G`, `second variation`；
- 模态：`buckling mode`, `normalization`, `MAC`, `repeated eigenvalue`, `subspace`；
- 缺陷：`imperfection seed`, `mode-shaped imperfection`, `local dent`, `Koiter 2/3 law`；
- 后屈曲：`post-buckling`, `limit point`, `bifurcation`, `snap-through`, `snap-back`, `arc length`, `branch switching`；
- 验证：`Euler`, `simply supported plate`, `shear buckling`, `cylindrical shell`, `mesh convergence`。
