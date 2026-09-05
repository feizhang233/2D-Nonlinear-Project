"""Analysis-level and sign-convention contracts."""

from __future__ import annotations

from enum import StrEnum


class AnalysisLevel(StrEnum):
    """The four analysis levels used by the source package."""

    LBA = "LBA"
    GNA = "GNA"
    GNIA = "GNIA"
    GMNIA = "GMNIA"


_ROUTES: dict[str, AnalysisLevel] = {
    "ideal_critical_mode": AnalysisLevel.LBA,
    "perfect_postbuckling_path": AnalysisLevel.GNA,
    "imperfect_geometric_limit_load": AnalysisLevel.GNIA,
    "imperfect_plastic_residual_stress_limit_load": AnalysisLevel.GMNIA,
}


def analysis_level_for(question_kind: str) -> AnalysisLevel:
    """Return the minimum sufficient analysis level for a supported question.

    This is a conclusion-boundary router, not proof that the corresponding
    numerical model contains all required physics.
    """

    try:
        return _ROUTES[question_kind]
    except KeyError as exc:
        supported = ", ".join(sorted(_ROUTES))
        raise ValueError(f"unsupported question kind {question_kind!r}; choose one of: {supported}") from exc


SIGN_CONVENTION = {
    "equilibrium": "r(q, lambda) = f_int(q) - lambda * f_ref = 0",
    "initial_stress": "(K_M + lambda * K_sigma_ref) phi = 0",
    "positive_weakening": "K_M phi = lambda K_G phi",
    "mapping": "K_G = -K_sigma_ref",
    "compression_membrane_force": "positive",
}

