from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from nonlinear_core import model_input_json_schema

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "model-input-1.0.0.schema.json"
VALID_EXAMPLE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "contracts" / "valid-minimal-frame.json"


def test_checked_in_schema_is_valid_and_current() -> None:
    checked_in = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(checked_in)
    assert checked_in == model_input_json_schema()


def test_valid_example_passes_json_schema() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    document = json.loads(VALID_EXAMPLE_PATH.read_text(encoding="utf-8"))

    errors = list(Draft202012Validator(schema).iter_errors(document))
    assert errors == []
