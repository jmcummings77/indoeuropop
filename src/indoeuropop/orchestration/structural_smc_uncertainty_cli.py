"""CLI handler for uncertainty-aware structural SMC disagreement review."""

from __future__ import annotations

import argparse
from pathlib import Path

from indoeuropop.reporting.structural_smc_uncertainty import (
    DEFAULT_MATERIAL_CHI_SQUARE_DELTA,
    load_structural_smc_uncertainty_report,
    structural_smc_uncertainty_markdown,
    write_structural_smc_uncertainty_csv,
    write_structural_smc_uncertainty_markdown,
)

STRUCTURAL_SMC_UNCERTAINTY_REPORT_COMMANDS = ("review-structured-smc-uncertainty",)


def add_structural_smc_uncertainty_report_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    """Add uncertainty-aware structural SMC review arguments."""
    parser.add_argument(
        "--smc-uncertainty-csv",
        type=Path,
        help="optional output path for uncertainty-aware SMC disagreement rows",
    )
    parser.add_argument(
        "--smc-uncertainty-report-md",
        type=Path,
        help="optional output path for uncertainty-aware SMC Markdown",
    )
    parser.add_argument(
        "--smc-material-chi-square-delta",
        type=float,
        default=DEFAULT_MATERIAL_CHI_SQUARE_DELTA,
        help="minimum child-minus-pulse chi-square delta treated as material",
    )


def run_structural_smc_uncertainty_report_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int | None:
    """Run uncertainty-aware structural SMC review or return `None`."""
    if args.command != "review-structured-smc-uncertainty":
        return None
    if args.smc_validation_summary_csv is None:
        parser.error(
            "review-structured-smc-uncertainty requires " "--smc-validation-summary-csv"
        )
    if args.smc_validation_output_dir is None:
        parser.error(
            "review-structured-smc-uncertainty requires " "--smc-validation-output-dir"
        )
    report = load_structural_smc_uncertainty_report(
        args.smc_validation_summary_csv,
        args.smc_validation_output_dir,
        material_chi_square_delta=args.smc_material_chi_square_delta,
    )
    if args.smc_uncertainty_csv is not None:
        output_path = write_structural_smc_uncertainty_csv(
            report,
            args.smc_uncertainty_csv,
        )
        print(f"smc_uncertainty_csv={output_path}")
    if args.smc_uncertainty_report_md is None:
        print(structural_smc_uncertainty_markdown(report), end="")
    else:
        output_path = write_structural_smc_uncertainty_markdown(
            report,
            args.smc_uncertainty_report_md,
        )
        print(f"smc_uncertainty_report={output_path}")
    print(f"smc_uncertainty_fold_count={report.fold_count}")
    print(f"smc_uncertainty_target_count={report.target_count}")
    print(
        "smc_uncertainty_structured_pulse_target_count="
        f"{report.structured_pulse_target_count}"
    )
    print(
        "smc_uncertainty_child_override_target_count="
        f"{report.child_override_target_count}"
    )
    print(f"smc_uncertainty_tie_target_count={report.uncertainty_tie_target_count}")
    return 0
