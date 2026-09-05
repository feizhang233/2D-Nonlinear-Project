#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "AI_CONTENT_INDEX.json"
MANIFEST = ROOT / "FILE_MANIFEST.sha256"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    document_ids = {document["id"] for document in data["documents"]}
    if len(document_ids) != len(data["documents"]):
        raise AssertionError("duplicate document IDs")

    missing = []
    for document in data["documents"]:
        path = ROOT / document["path"]
        if not path.is_file():
            missing.append(document["path"])
    if missing:
        raise AssertionError(f"missing indexed files: {missing}")

    questions = (ROOT / "03_验证题目与答案/验证题目.md").read_text(encoding="utf-8")
    solutions = (ROOT / "03_验证题目与答案/配套答案.md").read_text(encoding="utf-8")
    matrix = (ROOT / "03_验证题目与答案/验证矩阵.md").read_text(encoding="utf-8")
    expected = {f"V{number:02d}" for number in range(15)}
    for label, text in (("questions", questions), ("solutions", solutions), ("matrix", matrix)):
        found = set(re.findall(r"\bV\d{2}\b", text))
        if not expected.issubset(found):
            raise AssertionError(f"{label} missing IDs: {sorted(expected - found)}")

    pair_ids = {pair["test_id"] for pair in data["verification_pairs"]}
    if pair_ids != expected:
        raise AssertionError(f"verification_pairs mismatch: {sorted(pair_ids ^ expected)}")
    for pair in data["verification_pairs"]:
        if pair["question_document"] not in document_ids or pair["solution_document"] not in document_ids:
            raise AssertionError(f"bad verification document reference: {pair}")

    for route in data["routing"]:
        unknown = set(route["read"]) - document_ids
        if unknown:
            raise AssertionError(f"routing references unknown IDs: {sorted(unknown)}")

    executable_results = json.loads(
        (ROOT / "08_Python数学核心/artifacts/V00-V14_演算结果.json").read_text(encoding="utf-8")
    )
    result_ids = {record["test_id"] for record in executable_results["records"]}
    if result_ids != expected:
        raise AssertionError(f"executable result IDs mismatch: {sorted(result_ids ^ expected)}")
    allowed_statuses = {
        "VERIFIED",
        "PARTIAL",
        "REFERENCE_ONLY",
        "NOT_RUN",
        "AUDIT_RESULT",
        "FAILED",
    }
    unknown_statuses = {
        record["status"] for record in executable_results["records"]
    } - allowed_statuses
    if unknown_statuses:
        raise AssertionError(f"unknown executable result statuses: {sorted(unknown_statuses)}")
    failed_results = [
        record["test_id"] for record in executable_results["records"] if record["status"] == "FAILED"
    ]
    if failed_results:
        raise AssertionError(f"executable verification failures: {failed_results}")
    if executable_results.get("schema_version") != "1.1":
        raise AssertionError("executable result schema must be 1.1")
    stage_gates = executable_results.get("summary", {}).get("stage_gates", {})
    if set(stage_gates) != {f"G{number}" for number in range(8)}:
        raise AssertionError("executable results must report G0 through G7")

    if MANIFEST.is_file():
        for line in MANIFEST.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            expected_hash, relative = line.split("  ", 1)
            path = ROOT / relative
            if not path.is_file():
                raise AssertionError(f"manifest missing file: {relative}")
            actual_hash = sha256(path)
            if actual_hash != expected_hash:
                raise AssertionError(f"manifest hash mismatch: {relative}")

    print(
        "Package validation: OK "
        f"documents={len(data['documents'])} verification_pairs={len(data['verification_pairs'])}"
    )


if __name__ == "__main__":
    main()
