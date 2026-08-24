"""Exercise the built frontend proxy and live FastAPI service over real HTTP."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

FAMILY_CASES = {
    "frame": ("tests/fixtures/p9/shallow-arch-snap-through.json", 0.1, 9),
    "continuum": ("tests/fixtures/p12/q4-plane-strain-tension.json", 1.0, 8),
    "plate": ("tests/fixtures/p13/von-karman-mitc4-plate.json", 1.0, 20),
    "shell": ("tests/fixtures/p14/corotational-flat-shell.json", 1.0, 24),
}

FAMILY_RECOVERY_KEYS = {
    "frame": ("local_end_forces",),
    "continuum": ("gauss_points",),
    "plate": ("gauss_points",),
    "shell": ("gauss_points",),
}

FAMILY_GAUSS_KEYS = {
    "continuum": ("cauchy",),
    "plate": ("membrane_resultant", "bending_moment", "shear_force"),
    "shell": ("membrane_resultant", "bending_resultant", "shear_resultant"),
}


def _request(url: str, *, method: str = "GET", document: object | None = None) -> Any:
    body = None if document is None else json.dumps(document).encode()
    request = Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=5) as response:  # noqa: S310 - caller supplies local URL
        content = response.read()
        if "application/json" in response.headers.get("Content-Type", ""):
            return json.loads(content)
        return content.decode()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--frontend-url", required=True)
    parser.add_argument(
        "--families",
        nargs="+",
        choices=tuple(FAMILY_CASES),
        default=tuple(FAMILY_CASES),
    )
    args = parser.parse_args()
    base = args.frontend_url.rstrip("/")

    deadline = time.monotonic() + 20.0
    while True:
        try:
            health = _request(f"{base}/health")
            break
        except URLError:
            if time.monotonic() >= deadline:
                raise SystemExit("frontend/API stack did not become ready") from None
            time.sleep(0.1)
    if health["status"] != "ok":
        raise SystemExit("health request did not traverse the frontend proxy")
    index = _request(base)
    if "Nonlinear Studio" not in index:
        raise SystemExit("frontend index was not served")

    summaries = []
    for family in args.families:
        example, target, expected_dofs = FAMILY_CASES[family]
        model = json.loads((args.project_root / example).read_text())
        validation = _request(
            f"{base}/api/v1/models/validate", method="POST", document=model
        )
        if not validation["execution_eligible"] or validation["dof_count"] != expected_dofs:
            raise SystemExit(f"live {family} model validation failed")
        record = _request(
            f"{base}/api/v1/analyses",
            method="POST",
            document={
                "model": model,
                "target_load_factor": target,
                "execution_mode": "asynchronous",
            },
        )
        analysis_id = record["analysis_id"]
        analysis_deadline = time.monotonic() + 60.0
        while record["status"] in {"queued", "running"}:
            if time.monotonic() >= analysis_deadline:
                raise SystemExit(f"live {family} analysis did not finish")
            time.sleep(0.05)
            record = _request(f"{base}/api/v1/analyses/{analysis_id}")
        if record["status"] != "succeeded" or record["progress"]["accepted_steps"] < 1:
            raise SystemExit(f"live {family} asynchronous analysis did not succeed")
        fields = {
            field["name"]: field
            for field in record["result"]["post_result"]["raw_fields"]
        }
        element_records = fields["element_response"]["records"]
        if not element_records or any(
            key not in element_records[0] for key in FAMILY_RECOVERY_KEYS[family]
        ):
            raise SystemExit(f"live {family} recovery field is incomplete")
        if family in FAMILY_GAUSS_KEYS:
            points = element_records[0]["gauss_points"]
            if not points or any(key not in points[0] for key in FAMILY_GAUSS_KEYS[family]):
                raise SystemExit(f"live {family} Gauss recovery field is incomplete")
        summaries.append(
            {
                "family": family,
                "analysis_id": analysis_id,
                "status": record["status"],
                "dof_count": record["dof_count"],
                "accepted_steps": record["progress"]["accepted_steps"],
            }
        )

    print(
        json.dumps(
            {
                "frontend_url": base,
                "analyses": summaries,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
