"""P13 Plate V09: assembly tangent plus step, mesh, and locking gates."""

from __future__ import annotations

import numpy as np
import pytest

from nonlinear_core import ModelInput, get_adapter, solve_load_control


def _plate_model(divisions: int, step: float = 0.25) -> ModelInput:
    nodes = [
        {"id": f"N{i}_{j}", "coordinates": [i / divisions, j / divisions]}
        for j in range(divisions + 1)
        for i in range(divisions + 1)
    ]
    elements = []
    loads = []
    for j in range(divisions):
        for i in range(divisions):
            element_id = f"E{i}_{j}"
            elements.append(
                {
                    "id": element_id,
                    "formulation": "Q4-von-karman-MITC4",
                    "node_ids": [
                        f"N{i}_{j}",
                        f"N{i + 1}_{j}",
                        f"N{i + 1}_{j + 1}",
                        f"N{i}_{j + 1}",
                    ],
                    "material_id": "M1",
                    "properties": {"thickness": 0.05},
                }
            )
            loads.append(
                {
                    "id": f"P{i}_{j}",
                    "kind": "surface",
                    "element_id": element_id,
                    "components": {"UZ": -200.0},
                }
            )
    constraints = []
    for node in nodes:
        for dof in ("UX", "UY"):
            constraints.append(
                {"id": f"C_{node['id']}_{dof}", "node_id": node["id"], "dof": dof}
            )
        if node["coordinates"][0] == 0.0:
            for dof in ("UZ", "RX", "RY"):
                constraints.append(
                    {"id": f"C_{node['id']}_{dof}", "node_id": node["id"], "dof": dof}
                )
    return ModelInput.model_validate(
        {
            "schema_version": "1.0.0",
            "model_id": f"p13-plate-{divisions}-{step}",
            "name": "P13 plate mesh and step sensitivity",
            "model_family": "plate",
            "units": {"length": "m", "force": "N", "stress": "Pa", "angle": "rad"},
            "nodes": nodes,
            "materials": [
                {
                    "id": "M1",
                    "model": "linear-elastic",
                    "parameters": {"young": 21.0e6, "poisson": 0.3},
                }
            ],
            "elements": elements,
            "loads": loads,
            "constraints": constraints,
            "analysis": {
                "control_method": "load",
                "newton_method": "full",
                "max_iterations": 40,
                "tolerances": {
                    "residual": 1.0e-8,
                    "displacement": 1.0e-8,
                    "energy": 1.0e-10,
                    "linear_solver": 1.0e-12,
                    "force_floor": 1.0e-12,
                    "displacement_floor": 1.0e-12,
                    "energy_floor": 1.0e-16,
                },
                "step_control": {
                    "initial_step": step,
                    "min_step": step / 16.0,
                    "max_step": step,
                    "max_steps": 100,
                    "max_retries": 8,
                    "target_iterations": 6,
                    "cutback_factor": 0.5,
                    "growth_factor": 1.0,
                },
                "line_search": {
                    "enabled": True,
                    "method": "backtracking",
                    "max_iterations": 10,
                    "min_alpha": 0.001,
                    "reduction_factor": 0.5,
                },
            },
        }
    )


def _free_edge_displacement(model: ModelInput, displacement: np.ndarray) -> float:
    indices = [
        5 * index + 2
        for index, node in enumerate(model.nodes)
        if float(node.coordinates[0]) == 1.0
    ]
    return float(np.mean(displacement[indices]))


def test_v02_assembled_four_element_directional_derivative_has_error_valley():
    model = _plate_model(2)
    adapter = get_adapter(model)
    displacement = 0.015 * np.sin(np.arange(45, dtype=float))
    direction = np.cos(0.7 * np.arange(45, dtype=float))
    direction /= np.linalg.norm(direction)
    response = adapter.evaluate(model, displacement)
    target = response.tangent @ direction
    errors = []
    for step in np.logspace(-2, -7, 6):
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
    model = _plate_model(2, step)
    solution = solve_load_control(get_adapter(model), model, target_load_factor=1.0)

    assert solution.succeeded
    assert solution.committed_state is not None
    assert _free_edge_displacement(model, solution.committed_state.displacement) == pytest.approx(
        -0.03811696908,
        rel=2.0e-8,
    )


def test_v09_regular_mesh_refinement_stabilizes_the_free_edge_response():
    displacements = []
    for divisions in (1, 2, 4):
        model = _plate_model(divisions)
        solution = solve_load_control(get_adapter(model), model, target_load_factor=1.0)
        assert solution.succeeded
        assert solution.committed_state is not None
        displacements.append(_free_edge_displacement(model, solution.committed_state.displacement))

    assert abs(displacements[2] - displacements[1]) < abs(displacements[1] - displacements[0])
    assert displacements[2] == pytest.approx(displacements[1], rel=0.03)
