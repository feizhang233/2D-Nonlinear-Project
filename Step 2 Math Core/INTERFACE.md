# Step 2 Math Core 统一接入接口

## 1. 接口目标

统一层只解决四件事：固定核心标识、统一请求/响应包络、统一 JSON 序列化、统一验证入口。它不合并四套数学模型，也不改变各包的适用范围、正号或证据结论。

当前接口版本：`1.0.0`；适配器版本：`0.1.0`。

## 2. 统一请求

```json
{
  "schema_version": "1.0.0",
  "request_id": "optional-client-id",
  "core": "constitutive_nonlinearity",
  "operation": "material_update",
  "parameters": {}
}
```

字段规则：

| 字段 | 必填 | 说明 |
|---|---:|---|
| `schema_version` | 否 | 缺省为 `1.0.0`；不兼容版本直接返回错误 |
| `request_id` | 否 | 由调用方提供，响应原样返回；接口不会隐式生成随机 ID |
| `core` | 是 | 使用本文定义的四个稳定 `core_id` |
| `operation` | 是 | 使用对应核心公开的 operation 名称 |
| `parameters` | 否 | JSON object；未知字段会报错，不会静默忽略 |

## 3. 统一响应

成功响应：

```json
{
  "schema_version": "1.0.0",
  "request_id": "optional-client-id",
  "core": "constitutive_nonlinearity",
  "operation": "material_update",
  "status": "ok",
  "data": {},
  "diagnostics": {
    "adapter_version": "0.1.0",
    "core_version": "reference-1.0",
    "residual_convention": "...",
    "state_protocol": "...",
    "verification_meaning": "...",
    "limitations": []
  },
  "error": null
}
```

失败响应使用相同包络，`status="error"`，`data=null`，并返回：

```json
{
  "error": {
    "code": "INVALID_PARAMETERS",
    "message": "具体错误",
    "details": {}
  }
}
```

稳定错误码包括：

| 错误码 | 含义 |
|---|---|
| `INVALID_REQUEST` | 请求结构错误 |
| `UNSUPPORTED_SCHEMA_VERSION` | 接口版本不兼容 |
| `UNKNOWN_CORE` | `core_id` 不存在 |
| `UNKNOWN_OPERATION` | 核心不支持该 operation |
| `MISSING_PARAMETER` | 缺少必填参数 |
| `UNKNOWN_PARAMETER` | 含未声明参数 |
| `INVALID_PARAMETER` / `INVALID_PARAMETERS` | 参数值、形状、单位或模型名错误 |
| `CORE_IMPORT_FAILED` | 原核心无法载入 |
| `NUMERICAL_FAILURE` | 线性代数求解失败 |
| `CORE_EXECUTION_FAILED` | 局部迭代或原验证入口执行失败 |

## 4. 正号与状态边界

| 核心 | 规范残量/切线 | 接入要求 |
|---|---|---|
| `plate_shell_buckling` | `R=f_int-lambda*f_ref`；`K_M phi=lambda K_G phi`，`K_G=-K_sigma_ref` | 压缩膜力为正；不得对负特征值取绝对值 |
| `shell_instability` | `R=f_int-lambda*f_ref`；`K_T dq-f_ref dlambda=-R` | 非对称切线分类必须提供左零向量 |
| `constitutive_nonlinearity` | 材料点局部残量；真张量或标量 convention 写入 diagnostics | 每次从同一 committed state 重算；只返回 trial state |
| `general_nonlinear_shell` | `r=f_ext-f_int`；`K_t=d(f_int)/dq-d(f_ext)/dq`；`K_t dq=r` | 从前两包接入时必须显式使用 `R=-r`；收敛后才 commit |

统一包络不会强行把 `R` 和 `r` 改成同一个变量。全局求解器接入时建议在边界做一次显式映射，并在日志中保留原始 convention。

## 5. 公共元操作

Python API：

```python
from step2_math_core import describe_core, execute, list_core_ids, list_cores
```

- `list_core_ids()`：返回稳定核心 ID；
- `list_cores()`：返回全部元数据和 operation 规格；
- `describe_core(core_id)`：返回一个核心的范围、正号、验证与局限；
- `execute(request)`：执行请求，始终返回 `MathCoreResponse`。

`list_cores()` 返回的每个 operation 还包含 `example_parameters`。这些示例由统一层维护，必须是可直接执行的 JSON object；网站用它初始化参数编辑器，而不是在前端复制另一套默认值。

所有核心都支持 `operation="verify"`，且 `parameters={}`。该操作运行原包验证入口，而不是统一层自行重写参考值。

## 6. 各核心 operation

### 6.1 `plate_shell_buckling`

| operation | 必填参数 | 可选参数 |
|---|---|---|
| `verify` | — | — |
| `analysis_level` | `question_kind` | — |
| `linear_buckling` | `material_stiffness`, `geometric_stiffness` | `spectral_tolerance` |
| `uniaxial_plate` | `a_mm`, `b_mm`, `thickness_mm`, `young_mpa`, `poisson` | `max_m`, `max_n` |
| `imperfection_from_mode` | `normal_mode`, `amplitude_mm`, `sign` | `fixed_mask` |

`analysis_level.question_kind` 支持：`ideal_critical_mode`、`perfect_postbuckling_path`、`imperfect_geometric_limit_load`、`imperfect_plastic_residual_stress_limit_load`。

### 6.2 `shell_instability`

| operation | 必填参数 | 可选参数 |
|---|---|---|
| `verify` | — | — |
| `linear_buckling` | `material_stiffness`, `geometric_stiffness` | `positive_only`, `zero_tolerance` |
| `classify_critical_point` | `tangent`, `reference_load`, `right_null_vector` | `left_null_vector` 和三项容差 |
| `koiter_imperfection_law` | `imperfection_magnitudes` | `coefficient` |
| `classical_cylinder` | `elastic_modulus_mpa`, `poisson_ratio`, `radius_mm`, `thickness_mm`, `length_mm` | — |

这里的 `linear_buckling` 是低维稠密参考，要求 `geometric_stiffness` 对称正定；真实稀疏/不定壳问题不能直接套用。

### 6.3 `constitutive_nonlinearity`

唯一计算 operation 为 `material_update`：

```text
material_update(model, total_strain, committed_state, material, options)
  -> stress
  -> algorithmic_tangent
  -> trial_state
  -> diagnostics
  -> commit_required=true
```

支持模型：

| `model` | `total_strain` | `committed_state` | `material` |
|---|---|---|---|
| `linear_j2` | 对称 `3x3` 真应变张量 | `plastic_strain: 3x3`, `alpha` | `E`, `nu`, `sigma_y0`, `H_iso` |
| `voce_j2` | 对称 `3x3` 真应变张量 | 同上 | `E`, `nu`, `sigma_y0`, `Q`, `b`, `H_linear` |
| `plane_stress_j2` | 对称 `2x2` 面内真应变张量 | 同上 | 与 `linear_j2` 相同 |
| `combined_1d` | 标量总应变 | `plastic_strain`, `alpha`, `backstress` | `E`, `sigma_y0`, `H_iso`, `H_kin` |

返回的 `trial_state` 不能在全局 Newton 未收敛时写回 committed state。

### 6.4 `general_nonlinear_shell`

| operation | 必填参数 | 可选参数 |
|---|---|---|
| `verify` | — | — |
| `rotation_update` | `current_rotation: 3x3`, `increment: 3` | `increment_type=spatial|material` |
| `material_update` | `total_strain`, `committed_state`, `material` | — |
| `follower_line_load` | `x1`, `x2`, `pressure` | — |
| `plane_stress_condensation` | 四个切线分块 | — |
| `arc_length_step` | `q_n`, `load_factor_n`, `arc_length` | `beta`, `reference_load`, `direction`, `tolerance`, `max_iterations` |

该包是 L0 验证原语，不是完整一般非线性曲壳单元。

## 7. 材料点示例

```python
from step2_math_core import execute

response = execute(
    {
        "core": "constitutive_nonlinearity",
        "operation": "material_update",
        "parameters": {
            "model": "combined_1d",
            "total_strain": 0.002,
            "committed_state": {
                "plastic_strain": 0.0,
                "alpha": 0.0,
                "backstress": 0.0
            },
            "material": {
                "E": 210000.0,
                "sigma_y0": 250.0,
                "H_iso": 1000.0,
                "H_kin": 0.0
            }
        }
    }
)
```

完整 JSON 位于 `examples/constitutive_1d_request.json`。

## 8. 网站 HTTP 接口

Nonlinear Studio 将同一统一层暴露在版本化 HTTP 路径下。浏览器入口位于顶部工具栏的 `Math Core` 按钮；该工具与 Model/Results、四工作区、Apply/Cancel 和 Run analysis 状态隔离，不会读取后再改写当前模型。

| Method | Path | 响应 | 用途 |
|---|---|---|---|
| `GET` | `/api/v1/math-cores` | `MathCoreCatalog` | 列出四个核心、operation、必填/可选参数、可执行示例和 HTTP 限制 |
| `GET` | `/api/v1/math-cores/{core_id}` | `MathCoreMetadata` | 读取单个核心合同；未知核心返回 HTTP `404` |
| `POST` | `/api/v1/math-cores/execute` | `MathCoreResponse` | 用本文第 2 节的请求执行 operation，并保留第 3 节的统一响应包络 |

示例：

```bash
curl -s http://127.0.0.1:8000/api/v1/math-cores/execute \
  -H 'Content-Type: application/json' \
  --data @examples/plate_buckling_request.json
```

operation 自身的参数、核心或数值错误使用 HTTP `200` 返回 `status="error"`，调用方应读取 `error.code`，不能只判断 HTTP 状态。HTTP/服务边界错误继续使用标准 `ApiErrorResponse`：

| HTTP | 稳定错误码 | 含义 |
|---:|---|---|
| `413` | `REQUEST_TOO_LARGE` | 整个 HTTP 请求超过 API 字节上限 |
| `413` | `MATH_CORE_INPUT_LIMIT_EXCEEDED` | `parameters` 超过 10,000 个值或 12 层嵌套 |
| `422` | `REQUEST_VALIDATION_FAILED` | HTTP 请求不符合 Pydantic/OpenAPI 合同 |
| `503` | `MATH_CORE_UNAVAILABLE` | 服务器部署缺少 Step 2 运行包或无法载入 |

HTTP 层保留 1 MiB 全局请求上限，并额外限制参数值数量和嵌套深度。它仍然是低维参考接口，不是无界稠密矩阵计算服务。

## 9. 版本与兼容性

- `schema_version` 只在请求/响应字段或含义发生不兼容变化时升级；
- 新增 operation 或新增可选字段属于向后兼容变化；
- 原数学包版本单独记录在 `diagnostics.core_version`；
- `PACKAGE_INDEX.json` 是路径和验证入口的机器可读权威清单；
- 原包内部文件移动后，必须先更新清单与适配路径，再运行全部统一接口测试。
