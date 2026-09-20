"""CLI: python -m shell_core <model.json>"""

from __future__ import annotations

import argparse
import json
import sys

from reused_cores.shell3d_linear.post import dump_analysis_tables
from reused_cores.shell3d_linear.recover import recover_results
from reused_cores.shell3d_linear.solve import solve_linear_static
from reused_cores.shell3d_linear.types import PostOptions
from reused_cores.shell3d_linear.validate import validate_model


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a P0 ModelInput document and optionally solve or recover it."
    )
    parser.add_argument("path", help="Path to a model_input JSON file")
    parser.add_argument(
        "--solve",
        action="store_true",
        help="Run the P6 linear static solver after a successful validation.",
    )
    parser.add_argument(
        "--recover",
        action="store_true",
        help="Solve and recover Gauss-point N/M/Q, surface stress and balance.",
    )
    parser.add_argument(
        "--derived",
        action="store_true",
        help="With --recover, also emit area-weighted derived nodal resultants.",
    )
    parser.add_argument(
        "--export-tables",
        metavar="DIR",
        help="Write Gauss-point and derived CSV tables into DIR.",
    )
    args = parser.parse_args(argv)
    result = validate_model(args.path)
    payload = {
        "solvable": result.solvable,
        "model_id": result.model_id,
        "schema_version": result.schema_version,
        "error_count": len(result.errors),
        "warning_count": len(result.warnings),
        "diagnostics": [item.to_dict() for item in result.diagnostics],
    }
    if result.validated_model is not None:
        payload["model_sha256"] = result.validated_model.model_sha256
        payload["node_count"] = len(result.validated_model.nodes)
        payload["element_count"] = len(result.validated_model.elements)
    exit_code = 0 if result.solvable else 1
    if (args.solve or args.recover) and result.validated_model is not None:
        solved = solve_linear_static(result.validated_model)
        payload["solve_status"] = solved.status
        payload["diagnostics"] = [item.to_dict() for item in solved.diagnostics]
        if solved.solve_result is not None:
            payload["solve_result"] = solved.solve_result.to_dict()
            payload["strain_energy"] = solved.strain_energy
            payload["external_work"] = solved.external_work
        if solved.status != "succeeded":
            exit_code = 1
        elif args.recover:
            recovered = recover_results(
                result.validated_model,
                solved,
                PostOptions(include_derived_nodal_results=args.derived),
            )
            payload["recover_status"] = recovered.status
            payload["diagnostics"] = [item.to_dict() for item in recovered.diagnostics]
            payload["analysis_result"] = recovered.analysis_result.to_dict()
            if recovered.status != "succeeded":
                exit_code = 1
            elif args.export_tables:
                written = dump_analysis_tables(recovered.analysis_result, args.export_tables)
                payload["export_tables"] = {name: str(path) for name, path in written.items()}
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
