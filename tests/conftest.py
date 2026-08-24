from __future__ import annotations

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_EXAMPLES = PROJECT_ROOT / "tests" / "fixtures" / "contracts"


def load_contract_example(name: str) -> dict[str, object]:
    return json.loads((CONTRACT_EXAMPLES / name).read_text(encoding="utf-8"))


@pytest.fixture
def valid_model_document() -> dict[str, object]:
    return load_contract_example("valid-minimal-frame.json")
