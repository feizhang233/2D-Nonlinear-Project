"""Generate the deterministic checked-in P10 OpenAPI document."""

from __future__ import annotations

import json
from pathlib import Path

from nonlinear_api.main import app

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "schemas" / "openapi-1.0.0.json"


def main() -> None:
    document = json.dumps(
        app.openapi(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    OUTPUT.write_text(f"{document}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
