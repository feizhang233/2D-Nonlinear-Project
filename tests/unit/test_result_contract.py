from __future__ import annotations

import pytest
from pydantic import ValidationError

from nonlinear_core.constants import SCHEMA_VERSION
from nonlinear_core.model import ControlMethod
from nonlinear_core.result import (
    FailureCode,
    FailureRecord,
    IterationRecord,
    IterationStatus,
    PostResult,
    ResultField,
    ResultLocation,
    SolveResult,
    SolveStatus,
    StepResult,
    StepStatus,
)


def test_solve_result_carries_schema_and_traceability() -> None:
    iteration = IterationRecord(
        step_index=0,
        iteration_index=0,
        load_factor=0.1,
        residual_norm=1.0e-9,
        displacement_correction_norm=1.0e-10,
        energy_norm=1.0e-12,
        linear_residual_norm=1.0e-13,
        tangent_reassembled=True,
        status=IterationStatus.CONVERGED,
    )
    step = StepResult(
        step_index=0,
        status=StepStatus.ACCEPTED,
        control_method=ControlMethod.LOAD,
        load_factor=0.1,
        requested_step_size=0.1,
        accepted_step_size=0.1,
        state_id="state-0001",
        iterations=(iteration,),
    )
    raw = ResultField(
        name="element-resultants",
        location=ResultLocation.GAUSS_POINT,
        basis="element-local",
        records=({"element_id": "E1", "value": 1.0},),
    )
    derived = ResultField(
        name="nodal-resultants",
        location=ResultLocation.NODE,
        records=({"node_id": "N1", "value": 1.0},),
        is_derived=True,
        source="extrapolated and averaged from element Gauss points",
    )
    solve = SolveResult(
        model_id="frame-minimal",
        model_sha256="0" * 64,
        solver_version="0.1.0",
        status=SolveStatus.SUCCEEDED,
        steps=(step,),
        post_result=PostResult(raw_fields=(raw,), derived_fields=(derived,)),
    )

    payload = solve.model_dump(mode="json")
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["post_result"]["raw_fields"][0]["is_derived"] is False
    assert payload["post_result"]["derived_fields"][0]["is_derived"] is True


def test_failed_solve_requires_failure_evidence() -> None:
    with pytest.raises(ValidationError):
        SolveResult(
            model_id="frame-minimal",
            model_sha256="0" * 64,
            solver_version="0.1.0",
            status=SolveStatus.FAILED,
        )

    failure = FailureRecord(
        code=FailureCode.NONCONVERGENCE,
        message="maximum iterations reached",
        step_index=3,
        iteration_index=30,
    )
    solve = SolveResult(
        model_id="frame-minimal",
        model_sha256="0" * 64,
        solver_version="0.1.0",
        status=SolveStatus.FAILED,
        failures=(failure,),
    )
    assert solve.failures == (failure,)


def test_derived_result_requires_source_label() -> None:
    with pytest.raises(ValidationError):
        ResultField(
            name="derived",
            location=ResultLocation.NODE,
            records=(),
            is_derived=True,
        )
