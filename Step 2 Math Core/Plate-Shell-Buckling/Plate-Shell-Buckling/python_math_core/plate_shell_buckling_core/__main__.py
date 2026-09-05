"""Command-line entrypoint for the executable validation problems."""

from __future__ import annotations

import argparse

from .verification import run_validation_suite, validation_json, validation_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Plate-Shell Buckling V10-V22 Python calculations")
    parser.add_argument("--format", choices=("summary", "json", "markdown"), default="summary")
    args = parser.parse_args()
    records = run_validation_suite()
    if args.format == "json":
        print(validation_json(records))
    elif args.format == "markdown":
        print(validation_markdown(records))
    else:
        for record in records:
            print(f"{record.test_id}: {record.status} - {record.title}")
        print(
            f"REFERENCE CHECKS: {sum(record.passed for record in records)}/{len(records)} passed; "
            "production FE gate claimed: no"
        )
    return 0 if all(record.passed for record in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
