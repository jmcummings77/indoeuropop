"""CLI handlers for target review and audit reports."""

from __future__ import annotations

import argparse
from pathlib import Path

from indoeuropop.orchestration.override_delta import (
    OverrideDeltaOutputPaths,
    run_override_delta_workflow,
)
from indoeuropop.reporting.override_delta import override_delta_markdown
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

REPORT_COMMANDS = (
    "audit-target-curation",
    "review-override-deltas",
    "review-target-residuals",
)


def add_report_arguments(parser: argparse.ArgumentParser) -> None:
    """Add reporting command arguments to the shared CLI parser."""
    parser.add_argument(
        "--target-residuals",
        type=Path,
        help="target residual CSV input for review reporting",
    )
    parser.add_argument(
        "--target-review-md",
        type=Path,
        help="optional output path for target residual review Markdown",
    )
    parser.add_argument(
        "--target-audit-md",
        type=Path,
        help="optional output path for target curation audit Markdown",
    )
    parser.add_argument(
        "--target-id",
        help="target identifier to audit; defaults to the largest residual",
    )
    parser.add_argument(
        "--requested-group-id",
        help="requested AADR group identifier to audit",
    )
    parser.add_argument(
        "--outlier-z-threshold",
        type=float,
        default=2.0,
        help="absolute z-score threshold for target residual review outliers",
    )
    parser.add_argument(
        "--baseline-validation-fit-csv",
        type=Path,
        help="baseline validation fit CSV for override-delta review",
    )
    parser.add_argument(
        "--override-validation-fit-csv",
        type=Path,
        help="override validation fit CSV for override-delta review",
    )
    parser.add_argument(
        "--override-delta-csv",
        type=Path,
        help="optional output path for override validation delta CSV rows",
    )
    parser.add_argument(
        "--override-delta-report-md",
        type=Path,
        help="optional output path for override validation delta Markdown",
    )


def run_report_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int | None:
    """Run a reporting command, returning `None` for unrelated commands."""
    if args.command == "audit-target-curation":
        return _run_audit_target_curation_command(args, parser)
    if args.command == "review-override-deltas":
        return _run_review_override_deltas_command(args, parser)
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


def _run_review_override_deltas_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI override-delta review command."""
    if args.baseline_validation_fit_csv is None:
        parser.error("review-override-deltas requires --baseline-validation-fit-csv")
    if args.override_validation_fit_csv is None:
        parser.error("review-override-deltas requires --override-validation-fit-csv")
    result = run_override_delta_workflow(
        args.baseline_validation_fit_csv,
        args.override_validation_fit_csv,
        metric=args.fit_metric,
        priority_values=args.priority_validation_value or (),
        protected_values=args.protected_validation_value or (),
        tolerance=args.refinement_tolerance,
        paths=OverrideDeltaOutputPaths(
            baseline_validation_fit_csv=args.baseline_validation_fit_csv,
            override_validation_fit_csv=args.override_validation_fit_csv,
            override_delta_csv=args.override_delta_csv,
            override_delta_report_md=args.override_delta_report_md,
            manifest_json=args.manifest_json,
        ),
        command=args.command,
        manifest_name="cli-override-validation-delta",
        manifest_description="CLI override validation delta manifest",
    )
    if result.override_delta_report_md_path is None:
        print(override_delta_markdown(result.report), end="")
    else:
        print(f"override_delta_report={result.override_delta_report_md_path}")
    if result.override_delta_csv_path is not None:
        print(f"override_delta_csv={result.override_delta_csv_path}")
    if result.manifest_json_path is not None:
        print(f"manifest_json={result.manifest_json_path}")
    print(f"override_delta_fold_count={len(result.report.rows)}")
    print(f"mean_validation_delta={result.report.mean_validation_delta:.6f}")
    print(f"priority_mean_delta={result.report.priority_mean_delta:.6f}")
    print(f"protected_max_delta={result.report.protected_max_delta:.6f}")
    print(f"protected_degraded={str(result.report.protected_degraded).lower()}")
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
