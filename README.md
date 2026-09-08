# Nonlinear Studio

基于 React、FastAPI 和 Python 的有限元工作台，提供 Frame、Continuum、Plate、Shell 建模、准静态非线性分析与结果查看，并集成独立的数学参考工具。

[在线应用](https://nonlinear.feizhang233.com) · [详细文档](docs/README.md) · [模型示例](examples/README.md)

## 快速启动

需要 Python 3.11+、Node.js 22+ 和 npm。在仓库根目录执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
npm --prefix frontend ci
nonlinear-api
```

另开终端运行 `npm --prefix frontend run dev`，访问 [工作台](http://127.0.0.1:5173)；[API 文档](http://127.0.0.1:8000/docs)提供完整请求与响应定义。Windows 激活命令为 `.venv\Scripts\Activate.ps1`。

## 应用模块与使用

| 模块 | 用途与操作 |
| --- | --- |
| 建模 | 切换四类工作区，通过画布、模型树和属性表编辑；Frame 支持截面分配、杆件拆分，面模型支持轮廓与孔洞 |
| 材料与边界 | 设置材料、截面或厚度、约束，以及当前模型支持的节点／杆件／边界／面荷载 |
| 网格 | Frame 使用显式杆件；Continuum、Plate、Shell 通过 Gmsh 生成 Q4 网格，几何修改后重新划分 |
| 分析 | 设置控制方式、步长和容差，运行分析并查看进度；支持取消与从已提交状态续算 |
| Results | 查看变形、反力、内力／应力、荷载—位移曲线、收敛记录及失败原因 |
| 项目 | 导入／导出 JSON，可保存当前模型及结果；登录后使用私人服务端历史记录 |
| Math Core | 选择数学核心与 operation，载入示例参数、执行计算并查看诊断信息 |

典型流程：**选择模型 → 编辑几何／材料／边界 → 划分网格 → Apply → Run → Results → 保存**。编辑先进入草稿，Apply 提交、Cancel 撤销；提交修改后旧结果失效。四类工作区各自保留模型与分析状态，基础建模和计算无需登录。

## 数学结构与使用边界

主分析链为 `ModelInput → ModelAdapter → 非线性求解器 → SolveResult`。适配器负责单元组装、内外力、切线和响应恢复；统一求解器负责迭代、步长调整及状态提交。

| 模型 | 数学形式 | 节点自由度 | 适用边界 |
| --- | --- | --- | --- |
| Frame | 两节点共回转 Euler–Bernoulli 梁 | UX、UY、RZ | 大刚体转动、小应变，不含剪切变形 |
| Continuum | Total Lagrangian Q4 + Saint-Venant–Kirchhoff 弹性 | UX、UY | 平面应变 |
| Plate | von Kármán Q4 + MITC4 横向剪切 | UX、UY、UZ、RX、RY | 中等转动、小应变 |
| Shell | 共回转平面 Q4 + Reissner–Mindlin/QLLL、钻转稳定化 | UX、UY、UZ、RX、RY、RZ | 初始平面壳、小局部应变 |

全局平衡采用：

$$
\mathbf r=\mathbf f_{ext}-\mathbf f_{int},\qquad
\mathbf K_t=\frac{\partial\mathbf f_{int}}{\partial\mathbf u}-\frac{\partial\mathbf f_{ext}}{\partial\mathbf u},\qquad
\mathbf K_t\Delta\mathbf u=\mathbf r.
$$

常规增载使用荷载控制；指定节点位移使用位移控制；追踪极限点附近路径可使用球形弧长法。支持完整／修正 Newton、线搜索、自适应增量与失败缩步。每次迭代从已提交状态计算 trial，全局收敛后 commit，失败则 rollback。

**Step 2 Math Core** 提供四组独立参考计算：

| 核心 ID | 用途 |
| --- | --- |
| `plate_shell_buckling` | 线性屈曲、板临界荷载、初始缺陷构造 |
| `shell_instability` | 临界点分类、屈曲参考与 Koiter 缺陷关系 |
| `constitutive_nonlinearity` | 材料点更新、算法切线与试算状态 |
| `general_nonlinear_shell` | 壳运动学、截面、载荷与状态基础运算 |

在工具栏打开 **Math Core** 即可使用；程序入口为 `GET /api/v1/math-cores` 和 `POST /api/v1/math-cores/execute`，请求结构为 `{core, operation, parameters}`。执行后检查 `status`、`error` 和 `diagnostics`，不能只依据 HTTP 状态码判断成功。Python／CLI 示例见 [统一接口](Step%202%20Math%20Core/INTERFACE.md)。

这些参考运算保留各自的符号和验证范围，不修改当前模型，也不自动成为主求解器的材料或壳单元能力。主分析目前不含接触、动力学、生产级塑性或通用曲壳；数学推导与验证入口见 [数学核心指南](2D-Nonlinear-Project_Math-Core-Guide) 和 [计算审计](docs/MATH_CORE_CALCULATION_AUDIT.md)。

## 数据结构

公开模型合同版本为 `1.0.0`，由 Python Pydantic 定义，前端使用对应 TypeScript 类型。

| 结构 | 主要字段与关系 |
| --- | --- |
| `ModelInput` | `schema_version`、`model_id`、`name`、`model_family`、`units`，以及下列实体和 `analysis`、`extensions` |
| 节点／单元／材料 | `nodes: {id, coordinates}`；`elements: {id, formulation, node_ids, material_id, properties}`；`materials: {id, model, parameters}` |
| 荷载／约束 | `loads` 通过 `node_id` 或 `element_id` 定位，包含 `kind`、`components`；`constraints` 使用 `{id, node_id, dof, value}` |
| `analysis` | 控制方法、Newton 方法、容差、步长、线搜索及位移／弧长控制参数 |
| `extensions` | CAD 几何、截面库等扩展信息；几何轮廓与生成的有限元节点／单元分开保存 |
| `SolveResult` | 模型哈希、求解器版本、状态、`steps`、`failures`、`post_result`；每步包含迭代记录与响应 |
| `AnalysisRecord` | API 任务 ID、状态、进度，以及 `result` 或 `error` |
| 重启数据 | `committed_state` 保存已收敛位移、荷载因子、历史及身份信息；弧长续算另含增量方向 |
| `ProjectDocument` | `{studio_project_version, model, workspace}`；`workspace` 保存运行选项、可选分析记录和结果视图 |

实体通过 ID 关联；重复 ID、无效引用和不兼容自由度会在执行前报错。全局自由度按“节点顺序 → 模型自由度顺序”排列。单位标签不自动换算，输入数值需使用自洽单位制。

前端状态为 `StudioState.workspaces[ModelFamily] → WorkspaceState`，包含正式模型、草稿、`modelRevision` 和分析记录；版本检查防止旧异步结果覆盖新模型。项目 JSON 保存当前工作区，服务端账户与历史使用 SQLite，异步任务保存在单个 API 进程内。

字段详情见 [模型定义](src/nonlinear_core/model.py)、[结果定义](src/nonlinear_core/result.py)、[API／项目定义](src/nonlinear_api/schemas.py) 和 [JSON Schema](schemas/model-input-1.0.0.schema.json)。

## 代码导航与验证

```text
frontend/src/             工作台、画布、编辑状态与结果展示
src/nonlinear_api/        HTTP 接口、网格、任务服务与账户存储
src/nonlinear_core/       数据合同、适配器、单元、求解器及状态事务
src/reused_cores/         带来源记录的线性 Frame 基础代码
Step 2 Math Core/        四组参考核心、统一接口与验证入口
examples/ · tests/        输入示例、单元／集成／数值验证
schemas/ · docs/          公开合同与详细说明
```

```bash
python -m pytest
python scripts/run_math_core_audit.py --check
npm --prefix frontend test
npm --prefix frontend run build
```
