"""CLI handlers for same-baseline structural candidate comparisons."""

from __future__ import annotations

import argparse
from pathlib import Path

from indoeuropop.analysis.inference import ABCRejectionOptions
from indoeuropop.analysis.structural_head_to_head import StructuredPulseCandidate
from indoeuropop.data.targets import load_target_dataset
from indoeuropop.orchestration.child_region_overrides import (
    load_child_region_overrides,
)
from indoeuropop.orchestration.structural_head_to_head import (
    StructuredHeadToHeadWorkflowResult,
    run_structured_head_to_head_workflow,
)
from indoeuropop.orchestration.structural_head_to_head_outputs import (
    StructuredHeadToHeadOutputPaths,
)
from indoeuropop.simulation.config import load_sweep_spec

STRUCTURAL_HEAD_TO_HEAD_COMMANDS = ("compare-structured-candidates",)


def add_structural_head_to_head_arguments(parser: argparse.ArgumentParser) -> None:
    """Register same-baseline structural comparison arguments."""
    parser.add_argument(
        "--structured-pulse-candidate-name",
        default="structured-broad-pulse",
        help="label for the structured broad-pulse candidate",
    )
    parser.add_argument(
        "--structured-pulse-region-prefix",
        help="region prefix that receives the structured broad-pulse candidate",
    )
    parser.add_argument(
        "--structured-pulse-start-bce",
        type=float,
        help="BCE start date for the structured broad-pulse candidate",
    )
    parser.add_argument(
        "--structured-pulse-end-bce",
        type=float,
        help="BCE end date for the structured broad-pulse candidate",
    )
    parser.add_argument(
        "--structured-pulse-annual-rate",
        type=float,
        help="annual additive migration rate for the structured broad pulse",
    )
    parser.add_argument(
        "--structured-pulse-config-out",
        type=Path,
        help="optional output path for structured-pulse candidate config",
    )
    parser.add_argument(
        "--child-candidate-config-out",
        type=Path,
        help="optional output path for child-region candidate config",
    )
    parser.add_argument(
        "--structured-pulse-posterior-predictive-csv",
        type=Path,
        help="optional output CSV for structured-pulse posterior predictive rows",
    )
    parser.add_argument(
        "--structured-pulse-posterior-predictive-report-md",
        type=Path,
        help="optional report for structured-pulse posterior predictive diagnostics",
    )
    parser.add_argument(
        "--structured-pulse-posterior-predictive-plot",
        type=Path,
        help="optional plot for structured-pulse posterior predictive diagnostics",
    )
    parser.add_argument(
        "--child-posterior-predictive-csv",
        type=Path,
        help="optional output CSV for child-candidate posterior predictive rows",
    )
    parser.add_argument(
        "--child-posterior-predictive-report-md",
        type=Path,
        help="optional report for child-candidate posterior predictive diagnostics",
    )
    parser.add_argument(
        "--child-posterior-predictive-plot",
        type=Path,
        help="optional plot for child-candidate posterior predictive diagnostics",
    )
    parser.add_argument(
        "--head-to-head-report-md",
        type=Path,
        help="optional output path for the same-baseline comparison report",
    )


def run_structural_head_to_head_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int | None:
    """Run head-to-head structural commands or return `None`."""
    if args.command != "compare-structured-candidates":
        return None
    _require_head_to_head_inputs(args, parser)
    result = run_structured_head_to_head_workflow(
        load_sweep_spec(args.config),
        load_target_dataset(args.targets),
        load_child_region_overrides(args.child_region_overrides),
        StructuredPulseCandidate(
            name=args.structured_pulse_candidate_name,
            region_prefix=args.structured_pulse_region_prefix,
            start_bce=args.structured_pulse_start_bce,
            end_bce=args.structured_pulse_end_bce,
            annual_rate=args.structured_pulse_annual_rate,
        ),
        child_candidate_name=args.child_region_candidate_name,
        options=_abc_options(args),
        paths=_output_paths(args),
        interval_probability=args.posterior_predictive_interval_probability,
        focus_observation_index=args.focus_observation_index,
        command=args.command,
        manifest_name="cli-structured-candidate-head-to-head",
    )
    _print_head_to_head_result(result)
    return 0


def _require_head_to_head_inputs(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> None:
    """Raise argparse errors for missing head-to-head inputs."""
    for argument_name in (
        "config",
        "targets",
        "child_region_overrides",
        "structured_pulse_region_prefix",
        "structured_pulse_start_bce",
        "structured_pulse_end_bce",
        "structured_pulse_annual_rate",
    ):
        if getattr(args, argument_name) is None:
            parser.error(
                "compare-structured-candidates requires "
                f"--{argument_name.replace('_', '-')}"
            )


def _abc_options(args: argparse.Namespace) -> ABCRejectionOptions:
    """Return ABC rejection options for same-baseline comparison."""
    return ABCRejectionOptions(
        fit_metric=args.fit_metric,
        acceptance_quantile=args.acceptance_quantile,
        acceptance_count=args.acceptance_count,
        acceptance_threshold=args.acceptance_threshold,
    )


def _output_paths(args: argparse.Namespace) -> StructuredHeadToHeadOutputPaths:
    """Return output paths from parsed CLI arguments."""
    return StructuredHeadToHeadOutputPaths(
        config=args.config,
        targets=args.targets,
        child_region_overrides=args.child_region_overrides,
        structured_pulse_config_toml=args.structured_pulse_config_out,
        child_candidate_config_toml=args.child_candidate_config_out,
        baseline_posterior_predictive_csv=args.posterior_predictive_csv,
        baseline_posterior_predictive_report_md=args.posterior_predictive_report_md,
        baseline_posterior_predictive_plot=args.posterior_predictive_plot,
        structured_pulse_posterior_predictive_csv=(
            args.structured_pulse_posterior_predictive_csv
        ),
        structured_pulse_posterior_predictive_report_md=(
            args.structured_pulse_posterior_predictive_report_md
        ),
        structured_pulse_posterior_predictive_plot=(
            args.structured_pulse_posterior_predictive_plot
        ),
        child_posterior_predictive_csv=args.child_posterior_predictive_csv,
        child_posterior_predictive_report_md=(
            args.child_posterior_predictive_report_md
        ),
        child_posterior_predictive_plot=args.child_posterior_predictive_plot,
        head_to_head_report_md=args.head_to_head_report_md,
        manifest_json=args.manifest_json,
    )


def _print_head_to_head_result(result: StructuredHeadToHeadWorkflowResult) -> None:
    """Print compact CLI summary lines for a same-baseline comparison."""
    baseline = result.baseline.posterior_predictive
    structured_pulse = result.structured_pulse_result.posterior_predictive
    child = result.child_result.posterior_predictive
    assert baseline is not None
    assert structured_pulse is not None
    assert child is not None
    print("structured_head_to_head=true")
    print(f"structured_pulse_candidate={result.structured_pulse_candidate.name}")
    print(
        "structured_pulse_region_prefix="
        f"{result.structured_pulse_candidate.region_prefix}"
    )
    print(f"structured_pulse_region_count={result.structured_pulse_region_count}")
    print(f"child_region_candidate={result.child_candidate.name}")
    print(f"baseline_posterior_predictive_rmse={baseline.root_mean_squared_error:.6f}")
    print(
        "structured_pulse_posterior_predictive_rmse="
        f"{structured_pulse.root_mean_squared_error:.6f}"
    )
    print(f"child_posterior_predictive_rmse={child.root_mean_squared_error:.6f}")
    print(
        "structured_pulse_rmse_delta="
        f"{result.structured_pulse_delta.root_mean_squared_error_delta:.6f}"
    )
    print(f"child_rmse_delta={result.child_delta.root_mean_squared_error_delta:.6f}")
    print(
        "child_minus_structured_pulse_rmse_delta="
        f"{result.child_minus_structured_pulse_rmse_delta:.6f}"
    )
    print(
        "structured_pulse_coverage_delta="
        f"{result.structured_pulse_delta.coverage_rate_delta:.6f}"
    )
    print(f"child_coverage_delta={result.child_delta.coverage_rate_delta:.6f}")
    print(
        "structured_pulse_focus_residual_delta="
        f"{result.structured_pulse_delta.focus_residual_delta:.6f}"
    )
    print(f"child_focus_residual_delta={result.child_delta.focus_residual_delta:.6f}")
    _print_optional_paths(result)


def _print_optional_paths(result: StructuredHeadToHeadWorkflowResult) -> None:
    """Print optional generated paths for a same-baseline comparison."""
    if result.structured_pulse_config_toml_path is not None:
        print(f"structured_pulse_config={result.structured_pulse_config_toml_path}")
    if result.child_candidate_config_toml_path is not None:
        print(f"child_candidate_config={result.child_candidate_config_toml_path}")
    if result.head_to_head_report_md_path is not None:
        print(f"head_to_head_report_md={result.head_to_head_report_md_path}")
    if result.manifest_json_path is not None:
        print(f"manifest_json={result.manifest_json_path}")
