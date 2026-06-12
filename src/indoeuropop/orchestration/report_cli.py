"""CLI handlers for target review and audit reports."""

from __future__ import annotations

import argparse
from pathlib import Path

from indoeuropop.orchestration.override_delta import (
    OverrideDeltaOutputPaths,
    run_override_delta_workflow,
)
from indoeuropop.reporting.disagreement_target_audit import (
    load_disagreement_target_curation_audit,
    write_disagreement_target_audit_samples_csv,
)
from indoeuropop.reporting.disagreement_target_audit_report import (
    disagreement_target_audit_markdown,
    write_disagreement_target_audit_markdown,
)
from indoeuropop.reporting.override_delta import override_delta_markdown
from indoeuropop.reporting.readiness import (
    load_real_pipeline_readiness,
    real_pipeline_readiness_markdown,
    write_real_pipeline_readiness_markdown,
)
from indoeuropop.reporting.readiness_models import DEFAULT_DATA_SOURCE_CATALOG
from indoeuropop.reporting.structural_smc_disagreements import (
    load_structural_smc_disagreement_report,
    structural_smc_disagreement_markdown,
    write_structural_smc_disagreement_csv,
    write_structural_smc_disagreement_markdown,
)
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
    "audit-structured-smc-disagreement-targets",
    "review-pipeline-readiness",
    "review-override-deltas",
    "review-structured-smc-disagreements",
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
    parser.add_argument(
        "--readiness-report-md",
        type=Path,
        help="optional output path for real-pipeline readiness Markdown",
    )
    parser.add_argument(
        "--smc-validation-summary-csv",
        type=Path,
        help="structural SMC validation summary CSV for disagreement review",
    )
    parser.add_argument(
        "--smc-disagreement-csv",
        type=Path,
        help="optional output path for joined disagreement diagnostic rows",
    )
    parser.add_argument(
        "--smc-disagreement-report-md",
        type=Path,
        help="optional output path for disagreement diagnostic Markdown",
    )
    parser.add_argument(
        "--disagreement-target-audit-csv",
        type=Path,
        help="optional output path for sample-level disagreement target audit rows",
    )
    parser.add_argument(
        "--disagreement-target-audit-md",
        type=Path,
        help="optional output path for disagreement target audit Markdown",
    )


def run_report_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int | None:
    """Run a reporting command, returning `None` for unrelated commands."""
    if args.command == "audit-target-curation":
        return _run_audit_target_curation_command(args, parser)
    if args.command == "audit-structured-smc-disagreement-targets":
        return _run_audit_structural_smc_disagreement_targets_command(args, parser)
    if args.command == "review-pipeline-readiness":
        return _run_review_pipeline_readiness_command(args)
    if args.command == "review-override-deltas":
        return _run_review_override_deltas_command(args, parser)
    if args.command == "review-structured-smc-disagreements":
        return _run_review_structural_smc_disagreements_command(args, parser)
    if args.command == "review-target-residuals":
        return _run_review_target_residuals_command(args, parser)
    return None


def _run_review_pipeline_readiness_command(args: argparse.Namespace) -> int:
    """Run the CLI real-pipeline readiness review command."""
    report = load_real_pipeline_readiness(
        project_root=args.project_root,
        curation_decision_files=args.curation_decision_file,
        data_source_catalog=(
            DEFAULT_DATA_SOURCE_CATALOG
            if args.data_sources is None
            else args.data_sources
        ),
    )
    if args.readiness_report_md is None:
        print(real_pipeline_readiness_markdown(report), end="")
    else:
        output_path = write_real_pipeline_readiness_markdown(
            report,
            args.readiness_report_md,
        )
        print(f"readiness_report={output_path}")
    print(f"pipeline_ready={str(report.ready).lower()}")
    print(f"readiness_issue_count={len(report.issues)}")
    print(f"readiness_artifact_count={len(report.artifacts)}")
    print(f"readiness_metric_count={len(report.metrics)}")
    for metric in report.metrics:
        print(f"readiness_metric={metric.name},value={metric.value}")
    for issue in report.issues:
        print(f"readiness_issue={issue}")
    return 0 if report.ready else 1


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


def _run_review_structural_smc_disagreements_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI structural SMC disagreement review command."""
    if args.smc_validation_summary_csv is None:
        parser.error(
            "review-structured-smc-disagreements requires "
            "--smc-validation-summary-csv"
        )
    if args.smc_validation_output_dir is None:
        parser.error(
            "review-structured-smc-disagreements requires "
            "--smc-validation-output-dir"
        )
    report = load_structural_smc_disagreement_report(
        args.smc_validation_summary_csv,
        args.smc_validation_output_dir,
    )
    if args.smc_disagreement_csv is not None:
        output_path = write_structural_smc_disagreement_csv(
            report,
            args.smc_disagreement_csv,
        )
        print(f"smc_disagreement_csv={output_path}")
    if args.smc_disagreement_report_md is None:
        print(structural_smc_disagreement_markdown(report), end="")
    else:
        output_path = write_structural_smc_disagreement_markdown(
            report,
            args.smc_disagreement_report_md,
        )
        print(f"smc_disagreement_report={output_path}")
    print(f"smc_disagreement_fold_count={report.disagreement_fold_count}")
    print(f"smc_disagreement_target_count={report.target_count}")
    print(
        "smc_disagreement_structured_pulse_target_count="
        f"{report.structured_pulse_target_count}"
    )
    print(
        "smc_disagreement_child_override_target_count="
        f"{report.child_override_target_count}"
    )
    return 0


def _run_audit_structural_smc_disagreement_targets_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI disagreement-target batch curation audit command."""
    for argument_name in (
        "smc_disagreement_csv",
        "target_curation",
        "sample_metadata",
        "ancestry_estimates",
    ):
        if getattr(args, argument_name) is None:
            parser.error(
                "audit-structured-smc-disagreement-targets requires "
                f"--{argument_name.replace('_', '-')}"
            )
    report = load_disagreement_target_curation_audit(
        disagreement_csv=args.smc_disagreement_csv,
        curation_path=args.target_curation,
        sample_metadata_path=args.sample_metadata,
        ancestry_estimates_path=args.ancestry_estimates,
    )
    if args.disagreement_target_audit_csv is not None:
        output_path = write_disagreement_target_audit_samples_csv(
            report, args.disagreement_target_audit_csv
        )
        print(f"disagreement_target_audit_csv={output_path}")
    if args.disagreement_target_audit_md is None:
        print(disagreement_target_audit_markdown(report), end="")
    else:
        output_path = write_disagreement_target_audit_markdown(
            report, args.disagreement_target_audit_md
        )
        print(f"disagreement_target_audit_report={output_path}")
    print(f"disagreement_target_count={report.target_count}")
    print(f"disagreement_target_sample_count={report.sample_count}")
    print(f"disagreement_target_issue_count={report.issue_target_count}")
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
