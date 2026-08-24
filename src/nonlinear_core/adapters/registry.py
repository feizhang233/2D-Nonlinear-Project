"""Central adapter selection; nonlinear solvers receive only ``ModelAdapter``."""

from __future__ import annotations

from nonlinear_core.adapters.base import ModelAdapter
from nonlinear_core.adapters.continuum import ContinuumAdapter
from nonlinear_core.adapters.continuum_nonlinear import TotalLagrangianContinuumAdapter
from nonlinear_core.adapters.frame import FrameAdapter
from nonlinear_core.adapters.frame_nonlinear import CorotationalFrameAdapter
from nonlinear_core.adapters.plate import PlateAdapter
from nonlinear_core.adapters.plate_nonlinear import VonKarmanPlateAdapter
from nonlinear_core.adapters.shell import ShellAdapter
from nonlinear_core.adapters.shell_nonlinear import CorotationalShellAdapter
from nonlinear_core.model import ModelFamily, ModelInput

_ADAPTERS: dict[ModelFamily, ModelAdapter] = {
    ModelFamily.CONTINUUM: ContinuumAdapter(),
    ModelFamily.FRAME: FrameAdapter(),
    ModelFamily.PLATE: PlateAdapter(),
    ModelFamily.SHELL: ShellAdapter(),
}
_COROTATIONAL_FRAME_ADAPTER = CorotationalFrameAdapter()
_TOTAL_LAGRANGIAN_CONTINUUM_ADAPTER = TotalLagrangianContinuumAdapter()
_VON_KARMAN_PLATE_ADAPTER = VonKarmanPlateAdapter()
_COROTATIONAL_SHELL_ADAPTER = CorotationalShellAdapter()


def get_adapter(model_or_family: ModelInput | ModelFamily | str) -> ModelAdapter:
    """Return one protocol implementation without exposing element-type branches."""

    if isinstance(model_or_family, ModelInput):
        family = model_or_family.model_family
        if family is ModelFamily.CONTINUUM and any(
            "total-lagrangian" in element.formulation.strip().lower().replace("_", "-")
            for element in model_or_family.elements
        ):
            return _TOTAL_LAGRANGIAN_CONTINUUM_ADAPTER
        if family is ModelFamily.FRAME and any(
            "corotational" in element.formulation.strip().lower()
            for element in model_or_family.elements
        ):
            return _COROTATIONAL_FRAME_ADAPTER
        if family is ModelFamily.PLATE and any(
            "von-karman" in element.formulation.strip().lower().replace("_", "-")
            for element in model_or_family.elements
        ):
            return _VON_KARMAN_PLATE_ADAPTER
        if family is ModelFamily.SHELL and any(
            "corotational" in element.formulation.strip().lower()
            for element in model_or_family.elements
        ):
            return _COROTATIONAL_SHELL_ADAPTER
    else:
        family = ModelFamily(model_or_family)
    return _ADAPTERS[family]


def registered_adapters() -> tuple[ModelAdapter, ...]:
    return tuple(_ADAPTERS[family] for family in ModelFamily)


__all__ = ["get_adapter", "registered_adapters"]
