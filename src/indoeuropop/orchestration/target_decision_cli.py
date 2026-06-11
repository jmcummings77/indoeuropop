"""CLI handlers for reviewed target-decision workflows."""

from __future__ import annotations

import argparse

from indoeuropop.data.sample_metadata import load_sample_metadata
from indoeuropop.data.target_curation import load_target_curation
from indoeuropop.data.target_decisions import (
    apply_target_decisions,
    load_target_decisions,
    write_decision_filtered_target_inputs,
)

TARGET_DECISION_COMMANDS = ("apply-target-decisions",)


def run_target_decision_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int | None:
    """Run a target-decision command, returning `None` for unrelated commands."""
    if args.command == "apply-target-decisions":
        return _run_apply_target_decisions_command(args, parser)
    return None


def _run_apply_target_decisions_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    """Run the CLI target-decision filtering command."""
    for argument_name in ("sample_metadata", "target_curation", "target_decisions"):
        if getattr(args, argument_name) is None:
            parser.error(
                "apply-target-decisions requires "
                f"--{argument_name.replace('_', '-')}"
            )
    if args.sample_metadata_out is None:
        parser.error("apply-target-decisions requires --sample-metadata-out")
    if args.target_curation_out is None:
        parser.error("apply-target-decisions requires --target-curation-out")

    result = apply_target_decisions(
        load_sample_metadata(args.sample_metadata),
        load_target_curation(args.target_curation),
        load_target_decisions(args.target_decisions),
    )
    sample_path, curation_path = write_decision_filtered_target_inputs(
        result,
        sample_metadata_path=args.sample_metadata_out,
        target_curation_path=args.target_curation_out,
    )
    print(f"decision_filtered_sample_count={result.sample_metadata.sample_count}")
    print(f"decision_filtered_target_count={len(result.curation.records)}")
    print(f"decision_deferred_target_count={len(result.deferred_target_ids)}")
    print(f"decision_undecided_target_count={len(result.undecided_target_ids)}")
    print(f"sample_metadata={sample_path}")
    print(f"target_curation={curation_path}")
    for target_id in result.deferred_target_ids:
        print(f"decision_deferred_target={target_id}")
    for target_id in result.undecided_target_ids:
        print(f"decision_undecided_target={target_id}")
    return 0
