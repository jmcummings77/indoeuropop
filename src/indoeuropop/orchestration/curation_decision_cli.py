"""CLI handlers for curation-decision metadata validation."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path

from indoeuropop.data.curation_decisions import validate_curation_decision_files

CURATION_DECISION_COMMANDS = ("validate-curation-decisions",)


def add_curation_decision_arguments(parser: argparse.ArgumentParser) -> None:
    """Register curation-decision validation arguments."""
    parser.add_argument(
        "--curation-decision-file",
        action="append",
        type=Path,
        help="curation TOML file with a [review] metadata table; repeatable",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="project root used to resolve curation metadata paths",
    )
    parser.add_argument(
        "--require-artifacts",
        action="store_true",
        help="require linked generated validation artifacts and fresh checksums",
    )


def run_curation_decision_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int | None:
    """Run a curation-decision command, returning `None` when unrelated."""
    if args.command == "validate-curation-decisions":
        return _run_validate_curation_decisions_command(args, parser)
    return None


def _run_validate_curation_decisions_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    """Run the CLI curation-decision metadata validator."""
    if not args.curation_decision_file:
        parser.error("validate-curation-decisions requires --curation-decision-file")
    report = validate_curation_decision_files(
        args.curation_decision_file,
        project_root=args.project_root,
        require_artifacts=args.require_artifacts,
    )

    print(f"curation_decision_valid={str(report.valid).lower()}")
    print(f"curation_decision_record_count={len(report.records)}")
    print(f"curation_decision_issue_count={len(report.issues)}")
    for record in report.records:
        print(
            "curation_decision_record="
            f"{record.relative_path},"
            f"status={_status_text(record.review)}"
        )
    for issue in report.issues:
        print(f"curation_decision_issue={issue}")
    return 0 if report.valid else 1


def _status_text(review: Mapping[str, object]) -> str:
    """Return a printable status label for possibly malformed metadata."""
    value = review.get("status")
    if not isinstance(value, str) or not value.strip():
        return "invalid"
    return value.strip()
