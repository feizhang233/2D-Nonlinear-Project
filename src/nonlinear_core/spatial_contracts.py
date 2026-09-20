"""Family-independent spatial data contracts; no solver or HTTP dependencies."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt

Number = Annotated[float, Field(strict=True, allow_inf_nan=False)]
Identifier = Annotated[StrictInt, Field(gt=0)]
Vector = tuple[Number, Number, Number]


class Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid", allow_inf_nan=False, json_schema_serialization_defaults_required=True
    )


class SpatialNode(Contract):
    id: Identifier
    x: Number
    y: Number
    z: Number


class EquilibriumChecks(Contract):
    passed: bool
    relative_residual: Number
    force_balance: Vector
    moment_balance: Vector
    relative_force_error: Number
    relative_moment_error: Number
    relative_energy_error: Number
    relative_recovery_energy_error: Number
