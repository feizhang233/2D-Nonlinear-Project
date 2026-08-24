"""P9 adapter assembly, recovery, path extraction, and failure integration."""

from __future__ import annotations

import numpy as np
import pytest

from nonlinear_core import (
    AnalysisOptions,
    ControlMethod,
    CorotationalFrameAdapter,
    ModelInput,
    StepControlOptions,
    ToleranceOptions,
    get_adapter,
    recover_frame_path,
    solve_load_control,
)


def _arch_model(*, formulation: str = "frame2d-corotational") -> ModelInput:
    return ModelInput.model_validate(
        {
            "schema_version": "1.0.0",
            "model_id": "p9-shallow-arch",
            "name": "P9 symmetric shallow two-bar arch",
            "model_family": "frame",
            "units": {"length": "m", "force": "N", "stress": "Pa", "angle": "rad"},
            "nodes": [
                {"id": "N1", "coordinates": [-1.0, 0.0]},
                {"id": "N2", "coordinates": [0.0, 0.2]},
                {"id": "N3", "coordinates": [1.0, 0.0]},
            ],
            "materials": [{"id": "M1", "model": "linear-elastic", "parameters": {"young": 1.0e7}}],
            "elements": [
                {
                    "id": "E1",
                    "formulation": formulation,
                    "node_ids": ["N1", "N2"],
                    "material_id": "M1",
                    "properties": {"area": 0.01, "second_moment": 1.0e-8},
                },
                {
                    "id": "E2",
                    "formulation": formulation,
                    "node_ids": ["N2", "N3"],
                    "material_id": "M1",
                    "properties": {"area": 0.01, "second_moment": 1.0e-8},
                },
            ],
            "loads": [{"id": "P", "kind": "nodal", "node_id": "N2", "components": {"UY": -1000.0}}],
            "constraints": [
                {"id": f"C{index}", "node_id": node_id, "dof": dof}
                for index, (node_id, dof) in enumerate(
                    (
                        ("N1", "UX"),
                        ("N1", "UY"),
                        ("N1", "RZ"),
                        ("N2", "UX"),
                        ("N2", "RZ"),
                        ("N3", "UX"),
                        ("N3", "UY"),
                        ("N3", "RZ"),
                    ),
                    start=1,
                )
            ],
            "analysis": {"control_method": "load"},
        }
    )


def _one_step_load_analysis(step: float) -> AnalysisOptions:
    return AnalysisOptions(
        control_method=ControlMethod.LOAD,
        max_iterations=30,
        tolerances=ToleranceOptions(
            residual=1.0e-8,
            displacement=1.0e-8,
            energy=1.0e-8,
            linear_solver=1.0e-12,
        ),
        step_control=StepControlOptions(
            initial_step=step,
            min_step=step,
            max_step=step,
            max_steps=1,
            growth_factor=1.0,
        ),
    )


def test_registry_selects_corotational_adapter_and_recovers_frame_results():
    model = _arch_model()
    adapter = get_adapter(model)
    displacement = np.zeros(9)
    displacement[4] = -0.08

    response = adapter.evaluate(model, displacement, load_factor=0.2)
    recovery = adapter.recover(model, displacement, load_factor=0.2)

    assert isinstance(adapter, CorotationalFrameAdapter)
    assert adapter.validate(model).valid
    assert len(response.elements) == 2
    assert response.external_force[4] == pytest.approx(-200.0)
    assert recovery.reactions[4] == pytest.approx(
        response.internal_force[4] - response.external_force[4]
    )
    assert recovery.strain_energy > 0.0
    for element in recovery.element_data:
        assert element["formulation"] == "corotational-euler-bernoulli"
        assert len(element["local_end_forces"]) == 6
        assert set(element["reference_configuration"]) == {"length", "angle"}
        assert set(element["current_configuration"]) == {
            "length",
            "angle",
            "chord_rotation",
        }


def test_assembled_directional_derivative_has_expected_error_valley():
    model = _arch_model()
    adapter = get_adapter(model)
    displacement = np.array([0.0, 0.0, 0.0, 0.003, -0.06, 0.01, 0.0, 0.0, 0.0])
    direction = np.array([0.2, -0.1, 0.3, -0.4, 0.8, -0.2, 0.1, -0.3, 0.2])
    direction /= np.linalg.norm(direction)
    response = adapter.evaluate(model, displacement)
    target = response.tangent @ direction
    errors = []
    for step_size in np.logspace(-2, -8, 7):
        plus = adapter.evaluate(model, displacement + step_size * direction)
        minus = adapter.evaluate(model, displacement - step_size * direction)
        difference = (plus.internal_force - minus.internal_force) / (2.0 * step_size)
        errors.append(float(np.linalg.norm(difference - target) / np.linalg.norm(target)))

    best_index = int(np.argmin(errors))
    assert 0 < best_index < len(errors) - 1
    assert errors[best_index] < 1.0e-8
    assert errors[0] > 100.0 * errors[best_index]


def test_small_load_solution_converges_to_installed_linear_frame_reference():
    nonlinear = _arch_model().model_copy(update={"analysis": _one_step_load_analysis(1.0e-6)})
    linear = _arch_model(formulation="frame2d-linear")

    nonlinear_solution = solve_load_control(
        get_adapter(nonlinear), nonlinear, target_load_factor=1.0e-6
    )
    linear_reference = get_adapter(linear).native_reference(linear)

    assert nonlinear_solution.succeeded
    assert nonlinear_solution.committed_state is not None
    np.testing.assert_allclose(
        nonlinear_solution.committed_state.displacement,
        1.0e-6 * linear_reference.displacement,
        rtol=2.0e-5,
        atol=2.0e-14,
    )


def test_accepted_steps_form_a_recoverable_load_displacement_curve():
    model = _arch_model().model_copy(update={"analysis": _one_step_load_analysis(0.1)})
    solution = solve_load_control(get_adapter(model), model, target_load_factor=0.1)

    path = recover_frame_path(solution.result, dof_index=4)

    assert solution.succeeded
    assert len(path) == 1
    assert path[0].load_factor == pytest.approx(0.1)
    assert path[0].displacement == pytest.approx(-0.01480115361358, abs=2.0e-13)
    assert path[0].control_method == "load"


def test_collapsed_element_failure_is_typed_and_not_duplicated_at_model_level():
    model = _arch_model()
    displacement = np.zeros(9)
    displacement[3] = -1.0
    displacement[4] = -0.2

    response = get_adapter(model).evaluate(model, displacement)

    assert response.local_failures == ()
    assert len(response.elements[0].local_failures) == 1
    failure = response.elements[0].local_failures[0]
    assert failure.code == "FRAME_CURRENT_LENGTH_COLLAPSED"
    assert failure.element_id == "E1"


@pytest.mark.parametrize(
    "load_update",
    (
        {"coordinate_system": "local"},
        {"extensions": {"follower": True}},
    ),
)
def test_adapter_rejects_non_global_or_configuration_dependent_loading(load_update):
    model = _arch_model()
    load = model.loads[0].model_copy(update=load_update)
    changed = model.model_copy(update={"loads": (load,)})

    validation = get_adapter(changed).validate(changed)

    assert not validation.valid
    assert "fixed reference loads only" in validation.errors[0].message or (
        "nodal load" in validation.errors[0].message
    )
