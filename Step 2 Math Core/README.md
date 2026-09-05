# Step 2 Math Core

本目录现在以“四个原始资料包 + 一个统一接入层”的方式组织。原资料、PDF、题目、答案、来源映射和验证证据均保留在原位置，避免移动文件后破坏相对链接、哈希清单和包内校验。

GitHub 版本包含运行源码、统一接口、测试及文本资料；参考书和生成的 PDF 仅保留在本地，不参与网站运行或接口测试。文本中的 PDF 链接及原资料包哈希清单用于完整本地资料包，在 GitHub 克隆中可能没有对应的 PDF 文件。

## 统一入口

调用方只需要依赖 `step2_math_core`，不再手动切换工作目录或设置四套不同的 `PYTHONPATH`。

```python
from step2_math_core import execute

response = execute(
    {
        "core": "plate_shell_buckling",
        "operation": "linear_buckling",
        "parameters": {
            "material_stiffness": [[12.0, -2.0], [-2.0, 6.0]],
            "geometric_stiffness": [[1.0, 0.2], [0.2, 0.5]],
        },
    }
)

if not response.ok:
    raise RuntimeError(response.error)
result = response.to_dict()["data"]
```

统一请求、响应、错误码、正号映射和各 operation 的参数见 [INTERFACE.md](INTERFACE.md)。机器路由使用 [PACKAGE_INDEX.json](PACKAGE_INDEX.json)。

在 Nonlinear Studio 网站中，点击顶部工具栏的 `Math Core` 图标即可读取同一合同、载入可执行示例并调用全部 operation。HTTP 接口为 `GET /api/v1/math-cores`、`GET /api/v1/math-cores/{core_id}` 和 `POST /api/v1/math-cores/execute`；详细状态码与限制见 `INTERFACE.md` 第 8 节。

## 四个核心

| `core_id` | 原资料包 | 可执行范围 | 验证入口 |
|---|---|---|---|
| `plate_shell_buckling` | `Plate-Shell-Buckling/Plate-Shell-Buckling/` | LBA、GNA 参考路径、GNIA 缺陷准备 | V10-V22 |
| `shell_instability` | `Shell-Instability-Research_Math-Core-Guide/.../` | 临界点分类、模态交互、Koiter、弧长参考 | V00-V10 |
| `constitutive_nonlinearity` | `Constitutive Nonlinearity/.../` | 小应变 J2、Voce、平面应力、一维组合硬化 | V00-V11 |
| `general_nonlinear_shell` | `General Nonlinear Shell/.../` | L0 壳运动学、载荷、截面、材料与状态原语 | V00-V14 |

各包中的 `四项目数学核心演算/` 是保留的资料副本，不是 Python 接入口。程序路由应使用上表的 `core_id`，不要根据文件夹名称猜测。

## 命令行

从本目录运行：

```bash
../.venv/bin/python -m step2_math_core list
../.venv/bin/python -m step2_math_core describe constitutive_nonlinearity
../.venv/bin/python -m step2_math_core verify general_nonlinear_shell
../.venv/bin/python -m step2_math_core call --file examples/constitutive_1d_request.json
```

也可以安装为可编辑包：

```bash
../.venv/bin/python -m pip install -e .
step2-math-core list
```

## 当前目录层次

```text
Step 2 Math Core/
  README.md                 人工导航
  INTERFACE.md              统一接口合同
  PACKAGE_INDEX.json        机器可读路由
  pyproject.toml            可安装统一适配包
  step2_math_core/          请求、响应、适配器和命令行
  examples/                 JSON 接入示例
  tests/                    统一入口回归测试
  Plate-Shell-Buckling/     原始资料包，保留
  Shell-Instability-.../    原始资料包，保留
  Constitutive Nonlinearity/原始资料包，保留
  General Nonlinear Shell/  原始资料包，保留
```

## 验证

```bash
../.venv/bin/python -m unittest discover -s tests -v
```

统一层的 `verify` 表示“原验证入口成功执行”，不会抹平原包的证据边界。特别是 General Nonlinear Shell 的 `PARTIAL`、`REFERENCE_ONLY`、`NOT_RUN`、`AUDIT_RESULT` 和 `FAILED` 会原样返回；`NOT_RUN` 不会被伪装为通过。
