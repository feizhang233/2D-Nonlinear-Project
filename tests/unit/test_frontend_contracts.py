"""Backend publication and generated frontend types must change together."""

import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = runpy.run_path(str(ROOT / "scripts/generate_frontend_contracts.py"))


def test_generated_frontend_contracts_are_current():
    document = json.loads((ROOT / "schemas/openapi-1.0.0.json").read_text())
    assert (ROOT / "frontend/src/generated/api.ts").read_text() == GENERATOR["render"](document)


@pytest.mark.parametrize(
    "schema,expected",
    [
        (
            {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
            '{ "name": string }',
        ),
        (
            {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "additionalProperties": False,
            },
            '{ "name"?: string }',
        ),
        ({"anyOf": [{"type": "number"}, {"type": "null"}]}, "(number) | (null)"),
        (
            {
                "type": "array",
                "prefixItems": [{"type": "number"}] * 3,
                "minItems": 3,
                "maxItems": 3,
            },
            "[number, number, number]",
        ),
        ({"enum": ["w", "theta_x", "theta_y"]}, '"w" | "theta_x" | "theta_y"'),
    ],
)
def test_generator_preserves_required_nullable_tuple_and_literal_contracts(schema, expected):
    assert GENERATOR["ts_type"](schema) == expected


def test_unsupported_schema_does_not_silently_weaken_types():
    with pytest.raises(ValueError, match="Unsupported schema"):
        GENERATOR["ts_type"]({"not": {"type": "string"}})
    with pytest.raises(ValueError, match="fixed-length"):
        GENERATOR["ts_type"]({"type": "array", "prefixItems": [{"type": "number"}]})
