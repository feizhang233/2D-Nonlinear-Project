# 可复现材料点算例

## 1. 运行

脚本仅依赖 NumPy，不写文件：

```bash
python3 reference_material_point.py
```

成功时首行必须为：

```text
PACKAGE_REFERENCE_CHECK: OK
```

随后输出 V00-V11 的 JSON 参考值。

整包校验使用：

```bash
python3 validate_package.py
```

成功时首行必须为：

```text
PACKAGE_VALIDATION: OK
```

该命令同时检查索引文件、V00-V11 题答配对、C01-C12 来源编号、Markdown 分隔符、所有数值断言，以及局部迭代失败是否正确向上传播且不污染 committed state。

## 2. 参考实现边界

- J2 部分使用 3x3 对称张量和 3x3x3x3 四阶张量；
- 一维部分使用线性各向同性 + 线性随动组合硬化；
- plane-stress 通过局部求解 `sigma_zz=0`，不是截断 3D 应力；
- 非线性硬化只提供 Voce + 线性项的局部 Newton 演示；
- 线性 J2 使用 `J2Parameters`，Voce J2 使用独立的 `VoceJ2Parameters`，不存在被静默忽略的 `H_iso`；
- 方向导数使用 Schur 凝聚后的真张量 plane-stress 切线；
- 脚本是独立重算基线，不是生产材料库。

## 3. 修改规则

修改脚本后必须同步核对：

1. `03_验证题目与答案/配套答案.md` 的数值；
2. `03_验证题目与答案/验证矩阵.md` 的容差；
3. `AI_CONTENT_INDEX.json` 的验证 ID 和范围；
4. V06 的多步长方向导数趋势；
5. V07 的 committed state 无副作用；
6. V08 的完整循环状态序列。
7. `validate_package.py` 输出 `PACKAGE_VALIDATION: OK`。
