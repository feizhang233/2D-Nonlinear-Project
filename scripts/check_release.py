"""Run non-mutating P15 version, contract, and evidence checks."""

from __future__ import annotations

import json
import tomllib
from importlib.metadata import version as distribution_version
from pathlib import Path
from typing import Any

from nonlinear_api import create_app
from nonlinear_core import (
    SCHEMA_VERSION,
    SolveResult,
    StepStatus,
    __version__,
    model_input_json_schema,
    model_sha256,
    validate_model_input,
)

ROOT = Path(__file__).resolve().parents[1]


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _check_evidence(path: Path, expected_status: str) -> dict[str, Any]:
    artifact = _json(path)
    assert artifact["artifact_schema_version"] == SCHEMA_VERSION
    assert artifact["package_version"] == __version__
    assert artifact["expected_status"] == expected_status
    assert artifact["response"]["http_status"] == 201

    validation = validate_model_input(artifact["request"]["model"])
    assert validation.valid and validation.model is not None
    record = artifact["response"]["analysis_record"]
    assert record["model_id"] == validation.model.model_id
    assert record["model_sha256"] == model_sha256(validation.model)
    assert record["status"] == expected_status
    result = SolveResult.model_validate(record["result"])
    assert result.solver_version == __version__
    assert result.model_sha256 == record["model_sha256"]
    assert any(step.iterations for step in result.steps)

    if expected_status == "succeeded":
        assert result.post_result is not None
        assert result.failures == ()
        assert all(step.status is StepStatus.ACCEPTED for step in result.steps)
    else:
        rejected = [step for step in result.steps if step.status is StepStatus.REJECTED]
        accepted = [step for step in result.steps if step.status is StepStatus.ACCEPTED]
        assert rejected and accepted and result.failures
        assert rejected[-1].failure == result.failures[-1]
        assert rejected[-1].iterations[-1].status.value == "rejected"
        assert record["error"]["code"] == result.failures[-1].code.value
        assert accepted[-1].load_factor < artifact["request"]["target_load_factor"]

    return {
        "file": str(path.relative_to(ROOT)),
        "status": expected_status,
        "steps": len(result.steps),
        "iterations": sum(len(step.iterations) for step in result.steps),
    }


def check_release() -> dict[str, Any]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    frontend = _json(ROOT / "frontend" / "package.json")
    assert project["project"]["version"] == __version__
    assert distribution_version("nonlinear-core") == __version__
    assert frontend["version"] == __version__

    checked_schema = _json(ROOT / "schemas" / f"model-input-{SCHEMA_VERSION}.schema.json")
    assert checked_schema == model_input_json_schema()
    checked_openapi = _json(ROOT / "schemas" / f"openapi-{SCHEMA_VERSION}.json")
    runtime_openapi = create_app().openapi()
    assert checked_openapi == runtime_openapi
    assert runtime_openapi["info"]["version"] == SCHEMA_VERSION

    evidence = [
        _check_evidence(
            ROOT / "tests" / "fixtures" / "p15" / "release-success.json", "succeeded"
        ),
        _check_evidence(
            ROOT / "tests" / "fixtures" / "p15" / "release-expected-failure.json",
            "failed",
        ),
    ]
    return {
        "package_version": __version__,
        "metadata_version": distribution_version("nonlinear-core"),
        "schema_version": SCHEMA_VERSION,
        "frontend_version": frontend["version"],
        "evidence": evidence,
    }


def main() -> None:
    print(json.dumps(check_release(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
