"""Generate deterministic P15 success and expected-failure API evidence."""

from __future__ import annotations

import argparse
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from nonlinear_api import create_app
from nonlinear_core import SCHEMA_VERSION, __version__

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "tests" / "fixtures" / "p15"
SUCCESS_SOURCE = ROOT / "tests" / "fixtures" / "p9" / "imperfect-column.json"
FAILURE_SOURCE = ROOT / "tests" / "fixtures" / "p9" / "shallow-arch-snap-through.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _failure_model() -> dict[str, Any]:
    document = deepcopy(_load(FAILURE_SOURCE))
    document["analysis"] = {
        "control_method": "load",
        "newton_method": "full",
        "max_iterations": 30,
        "tolerances": {
            "residual": 1.0e-8,
            "displacement": 1.0e-8,
            "energy": 1.0e-8,
            "linear_solver": 1.0e-11,
        },
        "step_control": {
            "initial_step": 0.05,
            "min_step": 0.001,
            "max_step": 0.05,
            "max_steps": 20,
            "max_retries": 0,
            "growth_factor": 1.0,
        },
    }
    return document


def _normalized_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(record)
    for key in ("analysis_id", "created_at", "started_at", "completed_at"):
        normalized.pop(key, None)
    return normalized


def _run_case(
    *,
    source: Path,
    model: dict[str, Any],
    target_load_factor: float,
    expected_status: str,
) -> dict[str, Any]:
    request = {"model": model, "target_load_factor": target_load_factor}
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/analyses", json=request)
    record = _normalized_record(response.json())
    if response.status_code != 201 or record.get("status") != expected_status:
        raise RuntimeError(
            f"release case {source.name} expected HTTP 201/{expected_status}; "
            f"got {response.status_code}/{record.get('status')}"
        )
    return {
        "artifact_schema_version": SCHEMA_VERSION,
        "package_version": __version__,
        "source_input": str(source.relative_to(ROOT)),
        "expected_status": expected_status,
        "request": request,
        "response": {
            "http_status": response.status_code,
            "analysis_record": record,
        },
    }


def build_documents() -> dict[Path, dict[str, Any]]:
    return {
        OUTPUT_DIR / "release-success.json": _run_case(
            source=SUCCESS_SOURCE,
            model=_load(SUCCESS_SOURCE),
            target_load_factor=1.0,
            expected_status="succeeded",
        ),
        OUTPUT_DIR / "release-expected-failure.json": _run_case(
            source=FAILURE_SOURCE,
            model=_failure_model(),
            target_load_factor=0.31,
            expected_status="failed",
        ),
    }


def render(document: dict[str, Any]) -> str:
    return f"{json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)}\n"


def _first_difference(checked: Any, fresh: Any, *, path: str = "$") -> str | None:
    """Locate semantic drift without requiring cross-platform bit identity."""

    key = path.rsplit(".", maxsplit=1)[-1]
    if key == "state_id":
        same_optional_shape = checked is None and fresh is None
        same_string_shape = isinstance(checked, str) and isinstance(fresh, str)
        return None if same_optional_shape or same_string_shape else path
    if isinstance(checked, bool) or isinstance(fresh, bool):
        return None if checked is fresh else path
    if isinstance(checked, (int, float)) and isinstance(fresh, (int, float)):
        return (
            None
            if math.isclose(float(checked), float(fresh), rel_tol=5.0e-11, abs_tol=1.0e-12)
            else path
        )
    if isinstance(checked, dict) and isinstance(fresh, dict):
        if checked.keys() != fresh.keys():
            return path
        for name in checked:
            difference = _first_difference(checked[name], fresh[name], path=f"{path}.{name}")
            if difference is not None:
                return difference
        return None
    if isinstance(checked, list) and isinstance(fresh, list):
        if len(checked) != len(fresh):
            return path
        for index, (left, right) in enumerate(zip(checked, fresh, strict=True)):
            difference = _first_difference(left, right, path=f"{path}[{index}]")
            if difference is not None:
                return difference
        return None
    return None if checked == fresh else path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if checked-in evidence differs from a fresh API execution",
    )
    args = parser.parse_args()
    documents = build_documents()
    if args.check:
        stale: list[tuple[Path, str]] = []
        for path, document in documents.items():
            if not path.exists():
                stale.append((path, "$"))
                continue
            difference = _first_difference(
                json.loads(path.read_text(encoding="utf-8")),
                document,
            )
            if difference is not None:
                stale.append((path, difference))
        if stale:
            names = ", ".join(
                f"{path.relative_to(ROOT)} at {difference}" for path, difference in stale
            )
            raise SystemExit(f"stale P15 release evidence: {names}")
        print("P15 release evidence: current")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path, document in documents.items():
        path.write_text(render(document), encoding="utf-8")
        print(path)


if __name__ == "__main__":
    main()
