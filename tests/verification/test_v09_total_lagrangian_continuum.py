"""P12 Continuum V09: assembly tangent, mesh/step sensitivity, and detF gates."""

from __future__ import annotations

import numpy as np
import pytest

from nonlinear_core import (
    AnalysisOptions,
    ControlMethod,
    ModelInput,
    StepControlOptions,
    ToleranceOptions,
    get_adapter,
    solve_load_control,
)


def _tension_model(nx: int, step: float = 0.25) -> ModelInput:
    nodes = [
        {"id": f"N{i}_{j}", "coordinates": [2.0 * i / nx, float(j)]}
        for j in range(2)
        for i in range(nx + 1)
    ]
    elements = [
        {
            "id": f"E{i + 1}",
            "formulation": "Q4-total-lagrangian",
            "node_ids": [f"N{i}_0", f"N{i + 1}_0", f"N{i + 1}_1", f"N{i}_1"],
            "material_id": "M1",
            "properties": {"thickness": 0.1},
        }
        for i in range(nx)
    ]
    return ModelInput.model_validate(
        {
            "schema_version": "1.0.0",
            "model_id": f"p12-tension-{nx}-{step}",
            "name": "P12 mesh and step sensitivity",
            "model_family": "continuum",
            "units": {"length": "m", "force": "N", "stress": "Pa", "angle": "rad"},
            "nodes": nodes,
            "materials": [
                {
                    "id": "M1",
                    "model": "saint-venant-kirchhoff",
                    "parameters": {
                        "young": 10.0e6,
                        "poisson": 0.3,
                        "plane_mode": "plane_strain",
                    },
                }
            ],
            "elements": elements,
            "loads": [
                {
                    "id": "P1",
                    "kind": "nodal",
                    "node_id": f"N{nx}_0",
                    "components": {"UX": 50_000.0},
                },
                {
                    "id": "P2",
                    "kind": "nodal",
                    "node_id": f"N{nx}_1",
                    "components": {"UX": 50_000.0},
                },
            ],
            "constraints": [
                {"id": "C1", "node_id": "N0_0", "dof": "UX"},
                {"id": "C2", "node_id": "N0_0", "dof": "UY"},
                {"id": "C3", "node_id": "N0_1", "dof": "UX"},
            ],
            "analysis": AnalysisOptions(
                control_method=ControlMethod.LOAD,
                max_iterations=30,
                tolerances=ToleranceOptions(
                    residual=1.0e-9,
                    displacement=1.0e-9,
                    energy=1.0e-10,
                    linear_solver=1.0e-12,
                ),
                step_control=StepControlOptions(
                    initial_step=step,
                    min_step=step,
                    max_step=step,
                    max_steps=round(1.0 / step),
                    growth_factor=1.0,
                ),
            ).model_dump(mode="json"),
        }
    )


def _right_edge_displacement(model: ModelInput, displacement: np.ndarray) -> float:
    right_x = max(float(node.coordinates[0]) for node in model.nodes)
    indices = [
        2 * index
        for index, node in enumerate(model.nodes)
        if float(node.coordinates[0]) == right_x
    ]
    return float(np.mean(displacement[indices]))


def test_v02_assembled_two_element_directional_derivative_has_error_valley():
    model = _tension_model(2)
    adapter = get_adapter(model)
    displacement = np.asarray(
        [0.0, 0.0, 0.03, 0.01, 0.07, -0.01, 0.0, -0.02, 0.04, 0.02, 0.08, -0.03]
    )
    direction = np.asarray(
        [0.1, -0.2, 0.3, 0.2, -0.1, 0.4, -0.2, 0.1, 0.5, -0.3, 0.2, -0.4]
    )
    direction /= np.linalg.norm(direction)
    response = adapter.evaluate(model, displacement)
    target = response.tangent @ direction
    errors = []
    for step in np.logspace(-2, -8, 7):
        plus = adapter.evaluate(model, displacement + step * direction)
        minus = adapter.evaluate(model, displacement - step * direction)
        difference = (plus.internal_force - minus.internal_force) / (2.0 * step)
        errors.append(float(np.linalg.norm(difference - target) / np.linalg.norm(target)))

    best = int(np.argmin(errors))
    assert 0 < best < len(errors) - 1
    assert errors[best] < 1.0e-8
    assert errors[0] > 100.0 * errors[best]


@pytest.mark.parametrize("step", [0.5, 0.25, 0.125])
def test_v09_three_step_sizes_converge_to_the_same_path_endpoint(step: float):
    model = _tension_model(2, step)
    solution = solve_load_control(get_adapter(model), model, target_load_factor=1.0)

    assert solution.succeeded
    assert solution.committed_state is not None
    assert _right_edge_displacement(model, solution.committed_state.displacement) == pytest.approx(
        0.1618288167,
        rel=2.0e-8,
    )
    for accepted_step in solution.result.steps:
        displacement = accepted_step.response["displacement"]
        response = get_adapter(model).evaluate(
            model,
            displacement,
            load_factor=accepted_step.load_factor,
        )
        assert response.min_det_f is not None and response.min_det_f > 0.0


@pytest.mark.parametrize("nx", [1, 2, 4])
def test_v09_uniform_tension_endpoint_is_mesh_insensitive_for_regular_q4(nx: int):
    model = _tension_model(nx)
    solution = solve_load_control(get_adapter(model), model, target_load_factor=1.0)

    assert solution.succeeded
    assert solution.committed_state is not None
    assert _right_edge_displacement(model, solution.committed_state.displacement) == pytest.approx(
        0.1618288167,
        rel=2.0e-8,
    )
    assert solution.final_response is not None
    assert solution.final_response.min_det_f == pytest.approx(1.0411842464, rel=2.0e-8)


def test_nonpositive_detf_is_retained_as_a_model_failure_before_linear_solve():
    model = _tension_model(1)
    displacement = np.asarray([0.0, 0.0, -2.4, 0.0, 0.0, 0.0, -2.4, 0.0])

    response = get_adapter(model).evaluate(model, displacement)

    assert response.min_det_f is not None and response.min_det_f <= 0.0
    assert response.elements[0].metadata["failure_code"] == "CONTINUUM_NONPOSITIVE_DETF"


def test_solver_rejects_an_inverting_compression_step_with_detf_evidence():
    document = _tension_model(1).model_dump(mode="json")
    document["loads"][0]["components"]["UX"] = -1.0e6
    document["loads"][1]["components"]["UX"] = -1.0e6
    document["analysis"]["step_control"].update(
        {"initial_step": 1.0, "min_step": 1.0, "max_step": 1.0, "max_steps": 1}
    )
    model = ModelInput.model_validate(document)

    solution = solve_load_control(get_adapter(model), model, target_load_factor=1.0)

    assert not solution.succeeded
    failure = solution.result.failures[-1]
    assert failure.code.value == "MODEL_ERROR"
    assert failure.message == "current configuration has non-positive detF"
    assert failure.details["min_det_f"] <= 0.0
