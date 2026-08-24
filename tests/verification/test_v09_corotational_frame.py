"""V09 corotational-frame path, limit-point, mesh, and Newton evidence."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from nonlinear_core import (
    AnalysisOptions,
    ArcLengthOptions,
    ControlMethod,
    DisplacementControlOptions,
    Dof,
    DofRef,
    FailureCode,
    ModelInput,
    SolveStatus,
    StepControlOptions,
    StepStatus,
    ToleranceOptions,
    get_adapter,
    solve_arc_length,
    solve_displacement_control,
    solve_load_control,
    validate_model_json,
)

ROOT = Path(__file__).resolve().parents[2]
P9 = ROOT / "tests" / "fixtures" / "p9"
APEX_UY = 4


def _example(filename: str) -> ModelInput:
    result = validate_model_json((P9 / filename).read_text(encoding="utf-8"))
    assert result.valid and result.model is not None
    return result.model


def _tolerances() -> ToleranceOptions:
    return ToleranceOptions(
        residual=1.0e-8,
        displacement=1.0e-8,
        energy=1.0e-8,
        linear_solver=1.0e-11,
    )


def _load_model(*, step: float, max_steps: int) -> ModelInput:
    analysis = AnalysisOptions(
        control_method=ControlMethod.LOAD,
        max_iterations=30,
        tolerances=_tolerances(),
        step_control=StepControlOptions(
            initial_step=step,
            min_step=min(step, 0.001),
            max_step=step,
            max_steps=max_steps,
            max_retries=6,
            growth_factor=1.0,
        ),
    )
    return _example("shallow-arch-snap-through.json").model_copy(
        update={"analysis": analysis}
    )


def _displacement_model(increment: float, *, max_steps: int = 100) -> ModelInput:
    analysis = AnalysisOptions(
        control_method=ControlMethod.DISPLACEMENT,
        displacement_control=DisplacementControlOptions(
            target=DofRef(node_id="N2", dof=Dof.UY),
            increment=increment,
        ),
        max_iterations=30,
        tolerances=_tolerances(),
        step_control=StepControlOptions(max_steps=max_steps),
    )
    return _example("shallow-arch-snap-through.json").model_copy(
        update={"analysis": analysis}
    )


def _arc_model(*, radius: float, max_steps: int) -> ModelInput:
    analysis = AnalysisOptions(
        control_method=ControlMethod.ARC_LENGTH,
        arc_length=ArcLengthOptions(
            radius=radius,
            min_radius=radius / 16.0,
            max_radius=radius,
            beta=1.0e-5,
        ),
        max_iterations=50,
        tolerances=_tolerances(),
        step_control=StepControlOptions(
            initial_step=0.1,
            min_step=0.001,
            max_step=0.2,
            max_steps=max_steps,
            max_retries=10,
            target_iterations=8,
            cutback_factor=0.5,
            growth_factor=1.0,
        ),
    )
    return _example("shallow-arch-snap-through.json").model_copy(
        update={"analysis": analysis}
    )


def test_three_controls_agree_at_the_same_stable_branch_point():
    load_model = _load_model(step=0.1, max_steps=1)
    adapter = get_adapter(load_model)
    load_solution = solve_load_control(adapter, load_model, target_load_factor=0.1)
    assert load_solution.succeeded and load_solution.committed_state is not None
    target_displacement = float(load_solution.committed_state.displacement[APEX_UY])

    displacement_solution = solve_displacement_control(
        adapter,
        _displacement_model(target_displacement),
    )
    assert displacement_solution.succeeded
    controller_force = displacement_solution.result.steps[0].response["controller_reaction"]
    displacement_load_factor = float(controller_force / -1000.0)

    beta = 1.0e-5
    radius = float(np.hypot(target_displacement, beta * 1000.0 * 0.1))
    arc_model = _arc_model(radius=radius, max_steps=1)
    arc_solution = solve_arc_length(adapter, arc_model, number_of_steps=1)
    assert arc_solution.succeeded and arc_solution.committed_state is not None

    assert target_displacement == pytest.approx(-0.01480115361358, abs=2.0e-13)
    assert displacement_load_factor == pytest.approx(0.1, rel=2.0e-12)
    assert arc_solution.committed_state.load_factor == pytest.approx(0.1, rel=2.0e-10)
    assert arc_solution.committed_state.displacement[APEX_UY] == pytest.approx(
        target_displacement, rel=2.0e-10
    )


def test_three_displacement_step_sizes_bound_the_first_limit_load():
    peaks = []
    for step_size in (0.02, 0.01, 0.005):
        number_of_steps = round(0.12 / step_size)
        solution = solve_displacement_control(
            get_adapter(_displacement_model(-step_size)),
            _displacement_model(-step_size),
            number_of_steps=number_of_steps,
        )
        assert solution.succeeded
        peaks.append(
            max(-float(step.response["controller_reaction"]) for step in solution.result.steps)
        )

    assert 295.0 < peaks[0] < 297.0
    assert max(peaks) - min(peaks) < 1.0
    assert peaks[2] == pytest.approx(296.24, abs=0.15)


def test_load_control_fails_beyond_limit_but_arc_length_crosses_descending_branch():
    load_model = _load_model(step=0.05, max_steps=20)
    load_solution = solve_load_control(
        get_adapter(load_model), load_model, target_load_factor=0.31
    )

    assert load_solution.result.status is SolveStatus.FAILED
    assert load_solution.result.failures[-1].code is FailureCode.NONCONVERGENCE
    assert load_solution.committed_state is not None
    assert load_solution.committed_state.load_factor == pytest.approx(0.25)

    arc_model = _arc_model(radius=0.01, max_steps=20)
    arc_solution = solve_arc_length(
        get_adapter(arc_model), arc_model, number_of_steps=20
    )
    accepted = [
        step for step in arc_solution.result.steps if step.status is StepStatus.ACCEPTED
    ]
    load_factors = [step.load_factor for step in accepted]

    assert arc_solution.succeeded
    assert len(accepted) == 20
    assert max(load_factors) > 0.295
    assert load_factors[-1] < 0.01
    assert any(
        right < left for left, right in zip(load_factors, load_factors[1:], strict=True)
    )
    assert accepted[-1].response["displacement"][APEX_UY] < -0.19


def test_arc_length_restart_matches_continuous_path():
    model = _arc_model(radius=0.01, max_steps=6)
    adapter = get_adapter(model)

    continuous = solve_arc_length(adapter, model, number_of_steps=6)
    first = solve_arc_length(adapter, model, number_of_steps=3)
    assert first.committed_state is not None and first.last_increment is not None
    restarted = solve_arc_length(
        adapter,
        model,
        number_of_steps=3,
        initial_state=first.committed_state,
        previous_increment=first.last_increment,
    )

    assert continuous.succeeded and restarted.succeeded
    assert continuous.committed_state is not None and restarted.committed_state is not None
    np.testing.assert_allclose(
        restarted.committed_state.displacement,
        continuous.committed_state.displacement,
        rtol=2.0e-10,
        atol=2.0e-12,
    )
    assert restarted.committed_state.load_factor == pytest.approx(
        continuous.committed_state.load_factor, rel=2.0e-10
    )


def test_imperfect_column_full_newton_regression_converges():
    model = _example("imperfect-column.json")
    solution = solve_load_control(get_adapter(model), model, target_load_factor=1.0)

    assert solution.succeeded and solution.committed_state is not None
    assert len(solution.result.steps) == 5
    assert solution.committed_state.displacement[3] > 0.008
    assert solution.committed_state.displacement[7] < -0.003
    assert all(step.response["tangent_assemblies"] >= 2 for step in solution.result.steps)


def _cantilever_model(interior_x: tuple[float, float]) -> ModelInput:
    coordinates = (0.0, *interior_x, 2.0)
    return ModelInput.model_validate(
        {
            "schema_version": "1.0.0",
            "model_id": f"p9-mesh-{interior_x}",
            "name": "P9 cantilever mesh sensitivity",
            "model_family": "frame",
            "units": {"length": "m", "force": "N", "stress": "Pa", "angle": "rad"},
            "nodes": [
                {"id": f"N{index}", "coordinates": [x, 0.0]}
                for index, x in enumerate(coordinates, start=1)
            ],
            "materials": [
                {"id": "M1", "model": "elastic", "parameters": {"E": 210.0e9}}
            ],
            "elements": [
                {
                    "id": f"E{index}",
                    "formulation": "frame2d-corotational",
                    "node_ids": [f"N{index}", f"N{index + 1}"],
                    "material_id": "M1",
                    "properties": {"A": 0.003, "I": 8.0e-6},
                }
                for index in range(1, 4)
            ],
            "loads": [
                {"id": "P", "kind": "nodal", "node_id": "N4", "components": {"UY": -1000.0}}
            ],
            "constraints": [
                {"id": "C1", "node_id": "N1", "dof": "UX"},
                {"id": "C2", "node_id": "N1", "dof": "UY"},
                {"id": "C3", "node_id": "N1", "dof": "RZ"},
            ],
            "analysis": {
                "control_method": "load",
                "max_iterations": 30,
                "tolerances": {
                    "residual": 1e-7,
                    "displacement": 1e-7,
                    "energy": 1e-7,
                    "linear_solver": 1e-11
                },
                "step_control": {
                    "initial_step": 1.0,
                    "min_step": 1.0,
                    "max_step": 1.0,
                    "max_steps": 1,
                    "growth_factor": 1.0
                }
            },
        }
    )


def test_v09_regular_and_distorted_cantilever_meshes_agree():
    regular = _cantilever_model((2.0 / 3.0, 4.0 / 3.0))
    distorted = _cantilever_model((0.3, 1.4))
    regular_solution = solve_load_control(get_adapter(regular), regular, target_load_factor=1.0)
    distorted_solution = solve_load_control(
        get_adapter(distorted), distorted, target_load_factor=1.0
    )

    assert regular_solution.succeeded and distorted_solution.succeeded
    assert regular_solution.committed_state is not None
    assert distorted_solution.committed_state is not None
    regular_tip = regular_solution.committed_state.displacement[-2:]
    distorted_tip = distorted_solution.committed_state.displacement[-2:]
    np.testing.assert_allclose(distorted_tip, regular_tip, rtol=5.0e-8, atol=2.0e-12)
