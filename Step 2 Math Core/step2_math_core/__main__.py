"""Command-line access to the unified Step 2 math-core interface."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .contracts import InterfaceError, MathCoreRequest, to_jsonable
from .registry import describe_core, execute, list_cores


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="step2-math-core")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List registered cores and operations")

    describe = subparsers.add_parser("describe", help="Describe one core")
    describe.add_argument("core")

    verify = subparsers.add_parser("verify", help="Run one core's verification entry point")
    verify.add_argument("core")

    call = subparsers.add_parser("call", help="Execute a JSON request")
    request_source = call.add_mutually_exclusive_group(required=True)
    request_source.add_argument("--request", help="Inline request JSON")
    request_source.add_argument("--file", type=Path, help="Path to a request JSON file")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "list":
            output = list_cores()
        elif arguments.command == "describe":
            output = describe_core(arguments.core)
        elif arguments.command == "verify":
            output = execute(MathCoreRequest(core=arguments.core, operation="verify"))
        else:
            request_text = arguments.request
            if request_text is None:
                request_text = arguments.file.read_text(encoding="utf-8")
            output = execute(json.loads(request_text))
    except InterfaceError as exc:
        print(
            json.dumps(
                {"status": "error", "code": exc.code, "message": exc.message},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(
            json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 2

    print(json.dumps(to_jsonable(output), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not hasattr(output, "ok") or output.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
