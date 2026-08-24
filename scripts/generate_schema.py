"""Regenerate the checked-in P1 ModelInput JSON Schema."""

from __future__ import annotations

import json
from pathlib import Path

from nonlinear_core import SCHEMA_VERSION, model_input_json_schema


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    target = project_root / "schemas" / f"model-input-{SCHEMA_VERSION}.schema.json"
    temporary = target.with_suffix(f"{target.suffix}.tmp")
    rendered = json.dumps(model_input_json_schema(), indent=2, ensure_ascii=False, sort_keys=True)
    temporary.write_text(f"{rendered}\n", encoding="utf-8")
    temporary.replace(target)
    print(target)


if __name__ == "__main__":
    main()
