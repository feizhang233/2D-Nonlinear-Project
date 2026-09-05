#!/usr/bin/env python3
"""Validate the guide structure, source routing, and V00-V11 calculations."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import numpy as np

from reference_material_point import (
    J2Parameters,
    VoceJ2Parameters,
    j2_voce_update,
    plane_stress_update,
    run_reference_checks,
    virgin_j2_state,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TEST_IDS = [f"V{number:02d}" for number in range(12)]
EXPECTED_MAP_IDS = [f"C{number:02d}" for number in range(1, 13)]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _heading_ids(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return re.findall(r"^## (V\d{2})\b", text, flags=re.MULTILINE)


def validate_index() -> dict[str, int]:
    index_path = PACKAGE_ROOT / "AI_CONTENT_INDEX.json"
    index = _load_json(index_path)
    documents = index["documents"]
    document_ids = [item["id"] for item in documents]
    _require(len(document_ids) == len(set(document_ids)), "Duplicate document IDs")
    for item in documents:
        path = PACKAGE_ROOT / item["path"]
        _require(path.is_file(), f"Indexed document does not exist: {item['path']}")

    pair_ids = [item["test_id"] for item in index["verification_pairs"]]
    _require(pair_ids == EXPECTED_TEST_IDS, f"Verification pair IDs: {pair_ids}")
    for pair in index["verification_pairs"]:
        _require((PACKAGE_ROOT / pair["question_path"]).is_file(), f"Missing question: {pair}")
        _require((PACKAGE_ROOT / pair["answer_path"]).is_file(), f"Missing answer: {pair}")
    return {"documents": len(documents), "verification_pairs": len(pair_ids)}


def validate_question_answer_pairs() -> dict[str, int]:
    validation_root = PACKAGE_ROOT / "03_验证题目与答案"
    question_ids = _heading_ids(validation_root / "验证题目.md")
    answer_ids = _heading_ids(validation_root / "配套答案.md")
    matrix_text = (validation_root / "验证矩阵.md").read_text(encoding="utf-8")
    matrix_ids = sorted(set(re.findall(r"^\| (V\d{2}) \|", matrix_text, re.MULTILINE)))
    _require(question_ids == EXPECTED_TEST_IDS, f"Question IDs: {question_ids}")
    _require(answer_ids == EXPECTED_TEST_IDS, f"Answer IDs: {answer_ids}")
    _require(matrix_ids == EXPECTED_TEST_IDS, f"Matrix IDs: {matrix_ids}")
    return {
        "questions": len(question_ids),
        "answers": len(answer_ids),
        "matrix_rows": len(matrix_ids),
    }


def validate_source_routes() -> dict[str, int]:
    map_path = PACKAGE_ROOT / "06_来源映射/source_map.jsonl"
    routes: list[dict[str, Any]] = []
    for line_number, line in enumerate(map_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            route = json.loads(line)
        except json.JSONDecodeError as error:
            raise AssertionError(f"Invalid JSONL at line {line_number}: {error}") from error
        routes.append(route)

    route_ids = [route["map_id"] for route in routes]
    _require(route_ids == EXPECTED_MAP_IDS, f"Machine source-map IDs: {route_ids}")
    for route in routes:
        _require(
            (PACKAGE_ROOT / route["canonical_path"]).is_file(),
            f"Missing canonical source-map target: {route['canonical_path']}",
        )
        _require(
            (PACKAGE_ROOT / route["source_document"]).is_file(),
            f"Missing source PDF: {route['source_document']}",
        )

    human_text = (PACKAGE_ROOT / "06_来源映射/公式与页码映射.md").read_text(
        encoding="utf-8"
    )
    human_ids = re.findall(r"^\| (C\d{2}) \|", human_text, re.MULTILINE)
    _require(human_ids == EXPECTED_MAP_IDS, f"Human source-map IDs: {human_ids}")
    return {"machine_routes": len(route_ids), "human_routes": len(human_ids)}


def validate_markdown_delimiters() -> dict[str, int]:
    markdown_files = sorted(PACKAGE_ROOT.rglob("*.md"))
    for path in markdown_files:
        text = path.read_text(encoding="utf-8")
        _require(text.count("$$") % 2 == 0, f"Unpaired display-math delimiter: {path}")
        _require(text.count("```") % 2 == 0, f"Unpaired code fence: {path}")
    return {"markdown_files": len(markdown_files)}


def validate_failure_modes() -> dict[str, str]:
    parameters = J2Parameters(210000.0, 0.3, 250.0, 1000.0)
    voce_parameters = VoceJ2Parameters(
        E=210000.0,
        nu=0.3,
        sigma_y0=250.0,
        Q=100.0,
        b=15.0,
        H_linear=500.0,
    )
    committed = virgin_j2_state()
    committed_snapshot = committed.plastic_strain.copy(), committed.alpha

    try:
        j2_voce_update(
            np.diag([0.003, 0.0, 0.0]),
            committed,
            voce_parameters,
            max_iterations=1,
        )
    except RuntimeError:
        voce_status = "failure_propagated"
    else:
        raise AssertionError("Voce update silently accepted an unconverged local solve")

    try:
        plane_stress_update(
            np.array([[0.002, 0.0], [0.0, 0.0]]),
            committed,
            parameters,
            max_iterations=1,
        )
    except RuntimeError:
        plane_stress_status = "failure_propagated"
    else:
        raise AssertionError("Plane-stress update silently accepted an unconverged local solve")

    _require(
        np.array_equal(committed.plastic_strain, committed_snapshot[0])
        and committed.alpha == committed_snapshot[1],
        "Failed local solves modified the committed state",
    )
    return {
        "voce_iteration_limit": voce_status,
        "plane_stress_iteration_limit": plane_stress_status,
        "committed_state": "unchanged",
    }


def main() -> None:
    summary: dict[str, Any] = {
        "index": validate_index(),
        "question_answer_pairs": validate_question_answer_pairs(),
        "source_routes": validate_source_routes(),
        "markdown": validate_markdown_delimiters(),
        "failure_modes": validate_failure_modes(),
    }
    reference_results = run_reference_checks()
    _require(list(reference_results) == EXPECTED_TEST_IDS, "Reference result IDs are incomplete")
    summary["reference_calculations"] = {
        "tests": len(reference_results),
        "first": next(iter(reference_results)),
        "last": next(reversed(reference_results)),
    }
    print("PACKAGE_VALIDATION: OK")
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
