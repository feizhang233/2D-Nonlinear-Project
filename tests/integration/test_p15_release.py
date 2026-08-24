"""P15 version, contract, success, failure, and traceability release gates."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_p15_release_contract_and_checked_in_evidence_are_current():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_release.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    summary = json.loads(completed.stdout)

    assert summary["package_version"] == "0.1.0"
    assert summary["metadata_version"] == "0.1.0"
    assert summary["schema_version"] == "1.0.0"
    assert summary["frontend_version"] == "0.1.0"
    assert [case["status"] for case in summary["evidence"]] == ["succeeded", "failed"]
    assert all(case["iterations"] > 0 for case in summary["evidence"])
