"""Smoke-test an installed wheel against selected public nonlinear families."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import nonlinear_core
from nonlinear_core import get_adapter, solve_adaptive_load_control, validate_model_json

CASES = {
    "frame": ("tests/fixtures/p9/imperfect-column.json", 1.0),
    "continuum": ("tests/fixtures/p12/q4-plane-strain-tension.json", 0.25),
    "plate": ("tests/fixtures/p13/von-karman-mitc4-plate.json", 1.0),
    "shell": ("tests/fixtures/p14/corotational-flat-shell.json", 1.0),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--expected-prefix", type=Path)
    parser.add_argument("--expected-version", default="0.1.0")
    parser.add_argument("--families", choices=tuple(CASES), nargs="+", default=tuple(CASES))
    args = parser.parse_args()

    imported_from = Path(nonlinear_core.__file__).resolve()
    if args.expected_prefix is not None and not imported_from.is_relative_to(
        args.expected_prefix.resolve()
    ):
        raise SystemExit(
            f"nonlinear_core imported from {imported_from}, not installed wheel prefix"
        )
    if nonlinear_core.__version__ != args.expected_version:
        raise SystemExit(
            f"runtime version {nonlinear_core.__version__!r} != {args.expected_version!r}"
        )

    results = []
    for family in args.families:
        relative_source, target = CASES[family]
        source = args.project_root / relative_source
        validation = validate_model_json(source.read_text(encoding="utf-8"))
        if not validation.valid or validation.model is None:
            raise SystemExit(f"{family} release example failed ModelInput validation")
        solution = solve_adaptive_load_control(
            get_adapter(validation.model),
            validation.model,
            target_load_factor=target,
        )
        if not solution.succeeded or solution.committed_state is None:
            raise SystemExit(f"{family} example failed in the installed wheel environment")
        if solution.result.solver_version != nonlinear_core.__version__:
            raise SystemExit("SolveResult solver_version does not match the installed runtime")
        if not solution.result.steps or not all(step.iterations for step in solution.result.steps):
            raise SystemExit(f"{family} example did not retain step/iteration history")
        results.append(
            {
                "family": family,
                "model_id": solution.result.model_id,
                "status": solution.result.status.value,
                "accepted_steps": len(solution.result.steps),
                "final_load_factor": solution.committed_state.load_factor,
            }
        )

    print(
        json.dumps(
            {
                "imported_from": str(imported_from),
                "version": nonlinear_core.__version__,
                "families": results,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
