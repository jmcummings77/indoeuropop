"""CLI handlers for target review and audit reports."""

from __future__ import annotations

import argparse

from indoeuropop.reporting.target_audit import load_target_curation_audit
from indoeuropop.reporting.target_audit_report import (
    target_curation_audit_markdown,
    write_target_curation_audit_markdown,
)
from indoeuropop.reporting.target_review import (
    load_target_residual_review,
    target_residual_review_markdown,
    write_target_residual_review_markdown,
)

REPORT_COMMANDS = ("audit-target-curation", "review-target-residuals")


def run_report_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int | None:
    """Run a reporting command, returning `None` for unrelated commands."""
    if args.command == "audit-target-curation":
        return _run_audit_target_curation_command(args, parser)
    if args.command == "review-target-residuals":
        return _run_review_target_residuals_command(args, parser)
    return None


def _run_review_target_residuals_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI target-residual review command."""
    if args.target_residuals is None:
        parser.error("review-target-residuals requires --target-residuals")
    review = load_target_residual_review(
        args.target_residuals,
        diagnostics_path=args.target_diagnostics_json,
        outlier_z_threshold=args.outlier_z_threshold,
    )
    if args.target_review_md is None:
        print(target_residual_review_markdown(review), end="")
    else:
        output_path = write_target_residual_review_markdown(
            review, args.target_review_md
        )
        print(f"target_review={output_path}")

    top_row = review.ranked_rows[0]
    print(f"residual_count={len(review.rows)}")
    print(f"outlier_count={len(review.outliers)}")
    print(
        "top_residual="
        f"{top_row.region},"
        f"{top_row.requested_group_id or 'unknown'},"
        f"z={top_row.z_score:.6f},"
        f"residual={top_row.residual:.6f}"
    )
    print(f"recommendation={review.recommendation}")
    return 0


def _run_audit_target_curation_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI target curation audit command."""
    for argument_name in (
        "target_residuals",
        "target_curation",
        "sample_metadata",
        "ancestry_estimates",
    ):
        if getattr(args, argument_name) is None:
            parser.error(
                "audit-target-curation requires " f"--{argument_name.replace('_', '-')}"
            )
    audit = load_target_curation_audit(
        residuals_path=args.target_residuals,
        curation_path=args.target_curation,
        sample_metadata_path=args.sample_metadata,
        ancestry_estimates_path=args.ancestry_estimates,
        target_id=args.target_id,
        requested_group_id=args.requested_group_id,
        outlier_z_threshold=args.outlier_z_threshold,
    )
    if args.target_audit_md is None:
        print(target_curation_audit_markdown(audit), end="")
    else:
        output_path = write_target_curation_audit_markdown(audit, args.target_audit_md)
        print(f"target_audit={output_path}")

    print(f"target_id={audit.target_id}")
    print(f"requested_group_id={audit.requested_group_id or 'unknown'}")
    print(f"sample_count={len(audit.samples)}")
    print(f"missing_metadata_count={len(audit.missing_metadata_ids)}")
    print(f"missing_estimate_count={len(audit.missing_estimate_ids)}")
    print(f"recommendation={audit.recommendation}")
    return 0
