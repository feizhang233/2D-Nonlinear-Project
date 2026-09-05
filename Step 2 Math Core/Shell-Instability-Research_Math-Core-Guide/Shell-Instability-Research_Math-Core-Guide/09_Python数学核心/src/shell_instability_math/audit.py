"""V10 端到端研究证据门槛。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


EVIDENCE_REQUIREMENTS: dict[str, dict[str, str]] = {
    "residual_tangent": {
        "residual_convention": "残量符号与载荷参数化",
        "directional_tangent_check": "一致切线方向差分",
        "step_residuals_and_rollback": "每步平衡/弧长/线性残差与失败回滚",
    },
    "critical_classification": {
        "spectrum_and_inertia": "最低特征值/奇异值与惯性",
        "left_right_null_spaces": "左右零空间及 psi.T@f_ref",
        "critical_point_type": "极限点或分岔候选分类",
    },
    "mode_interaction": {
        "neighboring_eigenpairs": "邻近特征值与临界子空间",
        "cluster_tracking": "模态簇/子空间相关性",
        "multi_mode_directions": "双模态或多模态方向检查",
    },
    "imperfection": {
        "normalization_and_application": "0.1h 的归一化、符号和几何施加方式",
        "imperfection_scan": "缺陷幅值、方向、位置和类型扫描",
        "measured_field_scope": "实测场或未覆盖范围说明",
    },
    "path_following": {
        "arc_length_control": "弧长定义、beta、步长和根选择",
        "step_and_branch_convergence": "步长收敛与分支身份",
        "stability_indicators": "稳定性指标",
    },
    "mesh_boundary": {
        "half_wave_and_element": "半波解析、元素和积分方案",
        "mesh_convergence": "网格/畸变收敛",
        "boundary_sensitivity": "端部、转动及载荷引入敏感性",
    },
    "material_state": {
        "material_and_initial_state": "材料、残余应力和厚度偏差",
        "algorithmic_tangent": "一致算法切线",
        "state_contract_and_level": "trial/commit/rollback 与分析层级",
    },
    "reproducibility_scope": {
        "artifacts_and_versions": "模型、版本、输入、日志和脚本",
        "conclusion_level": "L1-L4 结论分级",
        "claim_boundary": "非设计值/非统计下限的结论边界",
    },
}


@dataclass(frozen=True)
class EvidenceRecord:
    """一个可追溯证据项及其已执行验收。"""

    artifact: str
    acceptance_criterion: str
    observed: str
    accepted: bool

    def __post_init__(self) -> None:
        for name in ("artifact", "acceptance_criterion", "observed"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"EvidenceRecord.{name} 必须是非空字符串")
        if not isinstance(self.accepted, bool):
            raise TypeError("EvidenceRecord.accepted 必须是 bool")


@dataclass(frozen=True)
class AuditResult:
    complete: bool
    present_categories: tuple[str, ...]
    missing_categories: tuple[str, ...]
    accepted_requirements: tuple[str, ...]
    missing_requirements: tuple[str, ...]
    rejected_requirements: tuple[str, ...]


def audit_research_evidence(
    evidence: Mapping[str, Mapping[str, EvidenceRecord]],
) -> AuditResult:
    """逐项检查 V10 证据、验收准则、观测值和通过状态。

    仅提供类别布尔值不再被接受。每个最低要求都必须关联一个非空证据
    定位、明确验收准则、实际观测结果以及 ``accepted`` 判断。
    """

    unknown = sorted(set(evidence) - set(EVIDENCE_REQUIREMENTS))
    if unknown:
        raise ValueError(f"未知证据类别: {', '.join(unknown)}")

    accepted: list[str] = []
    missing_requirements: list[str] = []
    rejected: list[str] = []
    present_categories: list[str] = []
    missing_categories: list[str] = []
    for category, requirements in EVIDENCE_REQUIREMENTS.items():
        category_evidence = evidence.get(category, {})
        if not isinstance(category_evidence, Mapping):
            raise TypeError(f"{category} 必须映射到逐项 EvidenceRecord")
        unknown_requirements = sorted(set(category_evidence) - set(requirements))
        if unknown_requirements:
            raise ValueError(
                f"{category} 包含未知证据项: {', '.join(unknown_requirements)}"
            )

        category_complete = True
        for requirement_id in requirements:
            full_id = f"{category}.{requirement_id}"
            record = category_evidence.get(requirement_id)
            if record is None:
                missing_requirements.append(full_id)
                category_complete = False
                continue
            if not isinstance(record, EvidenceRecord):
                raise TypeError(f"{full_id} 必须是 EvidenceRecord")
            if record.accepted:
                accepted.append(full_id)
            else:
                rejected.append(full_id)
                category_complete = False
        if category_complete:
            present_categories.append(category)
        else:
            missing_categories.append(category)

    return AuditResult(
        complete=not missing_requirements and not rejected,
        present_categories=tuple(present_categories),
        missing_categories=tuple(missing_categories),
        accepted_requirements=tuple(accepted),
        missing_requirements=tuple(missing_requirements),
        rejected_requirements=tuple(rejected),
    )
