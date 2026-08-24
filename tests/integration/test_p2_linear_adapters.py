"""P2 acceptance: four public cores produce one adapter response contract."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from nonlinear_core import (
    ModelAdapter,
    ModelFamily,
    ModelResponse,
    UnitMetadata,
    get_adapter,
    registered_adapters,
    validate_model_json,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples" / "adapters"
REFERENCE = json.loads((EXAMPLES / "reference-results.json").read_text(encoding="utf-8"))

CASES = (
    ("continuum-linear.json", ("UX", "UY")),
    ("frame-linear.json", ("UX", "UY", "RZ")),
    ("plate-linear.json", ("UZ", "RX", "RY")),
    ("shell-linear.json", ("UX", "UY", "UZ", "RX", "RY", "RZ")),
)


def _load_model(filename: str):
    result = validate_model_json((EXAMPLES / filename).read_text(encoding="utf-8"))
    assert result.valid, result.errors
    assert result.model is not None
    return result.model


@pytest.mark.parametrize(("filename", "node_dofs"), CASES)
def test_all_four_cores_implement_unified_response(filename: str, node_dofs: tuple[str, ...]):
    model = _load_model(filename)
    adapter = get_adapter(model)

    assert isinstance(adapter, ModelAdapter)
    assert adapter.validate(model).valid
    assert tuple(reference.dof.value for reference in adapter.dof_map(model)) == node_dofs * len(
        model.nodes
    )

    size = len(adapter.dof_map(model))
    response = adapter.evaluate(model, np.zeros(size), load_factor=0.25)
    assert isinstance(response, ModelResponse)
    assert response.tangent.shape == (size, size)
    assert response.internal_force.shape == (size,)
    assert response.external_force.shape == (size,)
    assert response.external_tangent is None
    assert len(response.elements) == len(model.elements)
    assert response.trial_state.core_version == adapter.core_version
    assert response.trial_state.history["load_factor"] == 0.25
    assert not response.tangent.flags.writeable
    assert not response.external_force.flags.writeable
    if model.model_family is ModelFamily.FRAME:
        assert response.min_det_j is None
    else:
        assert response.min_det_j is not None and response.min_det_j > 0.0


@pytest.mark.parametrize(("filename", "_node_dofs"), CASES)
def test_element_contributions_scatter_to_model_response(
    filename: str, _node_dofs: tuple[str, ...]
):
    model = _load_model(filename)
    adapter = get_adapter(model)
    size = len(adapter.dof_map(model))
    trial = np.linspace(-1.0e-6, 1.0e-6, size)
    response = adapter.evaluate(model, trial)

    internal = np.zeros(size)
    external = np.zeros(size)
    for element in response.elements:
        dofs = np.asarray(element.dof_indices, dtype=np.intp)
        internal[dofs] += element.internal_force
        external[dofs] += element.external_force
    np.testing.assert_allclose(internal, response.internal_force, rtol=2.0e-12, atol=1.0e-8)
    np.testing.assert_allclose(external, response.external_force, rtol=2.0e-12, atol=1.0e-12)


@pytest.mark.parametrize(("filename", "_node_dofs"), CASES)
def test_adapter_matches_original_core_and_saved_reference(
    filename: str, _node_dofs: tuple[str, ...]
):
    model = _load_model(filename)
    adapter = get_adapter(model)
    original = adapter.native_reference(model)
    recovered = adapter.recover(model, original.displacement)
    expected = REFERENCE[model.model_family.value]

    assert expected["core_package"] == adapter.core_package
    assert expected["core_version"] == adapter.core_version
    assert expected["dof_order"] == [
        f"{reference.node_id}/{reference.dof.value}" for reference in adapter.dof_map(model)
    ]
    np.testing.assert_allclose(
        original.displacement, expected["displacement"], rtol=2e-12, atol=1e-14
    )
    np.testing.assert_allclose(original.reactions, expected["reactions"], rtol=2e-10, atol=2e-8)
    assert original.strain_energy == pytest.approx(expected["strain_energy"], rel=2e-12)

    np.testing.assert_allclose(recovered.displacement, original.displacement, rtol=0.0, atol=0.0)
    np.testing.assert_allclose(recovered.reactions, original.reactions, rtol=2e-10, atol=2e-8)
    assert recovered.strain_energy == pytest.approx(original.strain_energy, rel=2e-12)


def test_registry_is_the_only_family_dispatch_needed_by_a_solver():
    def residual(adapter: ModelAdapter, model, displacement):
        response = adapter.evaluate(model, displacement)
        return response.external_force - response.internal_force

    adapters = registered_adapters()
    assert len(adapters) == 4
    assert {adapter.family for adapter in adapters} == set(ModelFamily)
    for filename, _ in CASES:
        model = _load_model(filename)
        adapter = get_adapter(model)
        result = residual(adapter, model, np.zeros(len(adapter.dof_map(model))))
        assert result.shape == (len(adapter.dof_map(model)),)


def test_family_mismatch_returns_structured_validation_error():
    model = _load_model("frame-linear.json")
    continuum = get_adapter(ModelFamily.CONTINUUM)
    result = continuum.validate(model)

    assert not result.valid
    assert result.errors[0].code == "ADAPTER_MODEL_INVALID"
    assert "requires family 'continuum'" in result.errors[0].message


def test_shell_rejects_non_si_labels_instead_of_silently_reinterpreting_values():
    model = _load_model("shell-linear.json")
    non_si = model.model_copy(
        update={
            "units": UnitMetadata(
                length="mm",
                force="kN",
                stress="MPa",
                angle="rad",
                system_label="engineering",
            )
        }
    )
    result = get_adapter(non_si).validate(non_si)

    assert not result.valid
    assert result.errors[0].code == "ADAPTER_MODEL_INVALID"
    assert "requires SI unit labels" in result.errors[0].message
