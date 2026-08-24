from __future__ import annotations

import nonlinear_core


def test_package_import_exposes_expected_version() -> None:
    assert nonlinear_core.__version__ == "0.1.0"
    assert nonlinear_core.SCHEMA_VERSION == "1.0.0"
    assert "ModelInput" in nonlinear_core.__all__
    assert "SolveResult" in nonlinear_core.__all__
    assert "validate_model_input" in nonlinear_core.__all__
