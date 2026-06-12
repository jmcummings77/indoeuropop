"""CLI handlers for bounded target-parameter inference workflows."""

from __future__ import annotations

import argparse
from pathlib import Path

from indoeuropop.analysis.abc_smc import ABCSMCOptions
from indoeuropop.analysis.inference import ABCRejectionOptions
from indoeuropop.data.targets import load_target_dataset
from indoeuropop.orchestration.abc_smc import (
    ABCSMCOutputPaths,
    ABCSMCWorkflowResult,
    run_abc_smc_workflow,
)
from indoeuropop.orchestration.inference import (
    ABCRejectionOutputPaths,
    run_abc_rejection_workflow,
)
from indoeuropop.simulation.config import load_sweep_spec

INFERENCE_COMMANDS = ("infer-target-parameters", "infer-target-parameters-smc")


def add_inference_arguments(parser: argparse.ArgumentParser) -> None:
    """Register inference command arguments on the shared CLI parser."""
    parser.add_argument(
        "--acceptance-quantile",
        type=float,
        default=0.25,
        help="accepted fraction for ABC rejection when count/threshold are omitted",
    )
    parser.add_argument(
        "--acceptance-count",
        type=int,
        help="exact number of best target-fit samples to accept",
    )
    parser.add_argument(
        "--acceptance-threshold",
        type=float,
        help="maximum fit metric value accepted by ABC rejection",
    )
    parser.add_argument(
        "--posterior-samples-csv",
        type=Path,
        help="optional output path for accepted inference sample rows",
    )
    parser.add_argument(
        "--posterior-summary-csv",
        type=Path,
        help="optional output path for posterior parameter summary rows",
    )
    parser.add_argument(
        "--inference-report-md",
        type=Path,
        help="optional output path for ABC rejection Markdown report",
    )
    parser.add_argument(
        "--posterior-predictive-interval-probability",
        type=float,
        default=0.9,
        help="central predictive interval probability for diagnostics",
    )
    parser.add_argument(
        "--posterior-predictive-csv",
        type=Path,
        help="optional output path for calibration posterior predictive rows",
    )
    parser.add_argument(
        "--posterior-predictive-report-md",
        type=Path,
        help="optional output path for calibration posterior predictive report",
    )
    parser.add_argument(
        "--posterior-predictive-plot",
        type=Path,
        help="optional output path for calibration posterior predictive plot",
    )
    parser.add_argument(
        "--holdout-targets",
        type=Path,
        help="optional target CSV used only for holdout posterior predictive checks",
    )
    parser.add_argument(
        "--holdout-posterior-predictive-csv",
        type=Path,
        help="optional output path for holdout posterior predictive rows",
    )
    parser.add_argument(
        "--holdout-posterior-predictive-report-md",
        type=Path,
        help="optional output path for holdout posterior predictive report",
    )
    parser.add_argument(
        "--holdout-posterior-predictive-plot",
        type=Path,
        help="optional output path for holdout posterior predictive plot",
    )
    parser.add_argument(
        "--smc-generations",
        type=int,
        default=3,
        help="number of sequential ABC-SMC-style calibration generations",
    )
    parser.add_argument(
        "--smc-sample-count",
        type=int,
        help="sample count per SMC generation; defaults to the config sweep count",
    )
    parser.add_argument(
        "--smc-seed-stride",
        type=int,
        default=1009,
        help="deterministic seed offset between SMC generations",
    )
    parser.add_argument(
        "--smc-range-quantile-low",
        type=float,
        default=0.05,
        help="accepted-sample lower quantile used to narrow proposal ranges",
    )
    parser.add_argument(
        "--smc-range-quantile-high",
        type=float,
        default=0.95,
        help="accepted-sample upper quantile used to narrow proposal ranges",
    )
    parser.add_argument(
        "--smc-range-padding-fraction",
        type=float,
        default=0.1,
        help="fractional padding added around narrowed SMC proposal ranges",
    )
    parser.add_argument(
        "--smc-generations-csv",
        type=Path,
        help="optional output path for SMC generation diagnostics",
    )


def run_inference_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int | None:
    """Run inference commands or return `None` for unrelated commands."""
    if args.command == "infer-target-parameters":
        return _run_infer_target_parameters_command(args, parser)
    if args.command == "infer-target-parameters-smc":
        return _run_infer_target_parameters_smc_command(args, parser)
    return None


def _run_infer_target_parameters_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI ABC-style target-parameter inference workflow."""
    if args.config is None:
        parser.error("infer-target-parameters requires --config")
    if args.targets is None:
        parser.error("infer-target-parameters requires --targets")
    if args.holdout_targets is None and _has_holdout_outputs(args):
        parser.error("holdout posterior predictive outputs require --holdout-targets")
    holdout_targets = (
        load_target_dataset(args.holdout_targets)
        if args.holdout_targets is not None
        else None
    )
    result = run_abc_rejection_workflow(
        load_sweep_spec(args.config),
        load_target_dataset(args.targets),
        options=ABCRejectionOptions(
            fit_metric=args.fit_metric,
            acceptance_quantile=args.acceptance_quantile,
            acceptance_count=args.acceptance_count,
            acceptance_threshold=args.acceptance_threshold,
        ),
        paths=ABCRejectionOutputPaths(
            config=args.config,
            targets=args.targets,
            accepted_samples_csv=args.posterior_samples_csv,
            posterior_summary_csv=args.posterior_summary_csv,
            inference_report_md=args.inference_report_md,
            posterior_predictive_csv=args.posterior_predictive_csv,
            posterior_predictive_report_md=args.posterior_predictive_report_md,
            posterior_predictive_plot=args.posterior_predictive_plot,
            holdout_targets=args.holdout_targets,
            holdout_posterior_predictive_csv=args.holdout_posterior_predictive_csv,
            holdout_posterior_predictive_report_md=(
                args.holdout_posterior_predictive_report_md
            ),
            holdout_posterior_predictive_plot=args.holdout_posterior_predictive_plot,
            manifest_json=args.manifest_json,
        ),
        command=args.command,
        manifest_name="cli-abc-rejection-inference",
        manifest_description="CLI ABC rejection target-parameter inference manifest",
        interval_probability=args.posterior_predictive_interval_probability,
        holdout_targets=holdout_targets,
    )
    inference = result.inference
    print(f"inference_candidate_count={inference.candidate_count}")
    print(f"inference_accepted_count={inference.accepted_count}")
    print(f"inference_acceptance_rate={inference.acceptance_rate:.6f}")
    print(f"inference_fit_metric={inference.options.fit_metric}")
    print(f"inference_acceptance_criterion={inference.options.criterion}")
    print(f"inference_acceptance_threshold={inference.acceptance_threshold:.6f}")
    print(f"inference_best_run_index={inference.best_run.run.index}")
    if result.posterior_predictive is not None:
        diagnostics = result.posterior_predictive
        print(
            "posterior_predictive="
            f"coverage_rate={diagnostics.coverage_rate:.6f},"
            f"rmse={diagnostics.root_mean_squared_error:.6f},"
            f"max_abs_z={diagnostics.max_abs_z_score:.6f}"
        )
    if result.holdout_posterior_predictive is not None:
        diagnostics = result.holdout_posterior_predictive
        print(
            "holdout_posterior_predictive="
            f"coverage_rate={diagnostics.coverage_rate:.6f},"
            f"rmse={diagnostics.root_mean_squared_error:.6f},"
            f"max_abs_z={diagnostics.max_abs_z_score:.6f}"
        )
    if result.accepted_samples_csv_path is not None:
        print(f"posterior_samples_csv={result.accepted_samples_csv_path}")
    if result.posterior_summary_csv_path is not None:
        print(f"posterior_summary_csv={result.posterior_summary_csv_path}")
    if result.inference_report_md_path is not None:
        print(f"inference_report_md={result.inference_report_md_path}")
    if result.posterior_predictive_csv_path is not None:
        print(f"posterior_predictive_csv={result.posterior_predictive_csv_path}")
    if result.posterior_predictive_report_md_path is not None:
        print(
            "posterior_predictive_report_md="
            f"{result.posterior_predictive_report_md_path}"
        )
    if result.posterior_predictive_plot_path is not None:
        print(f"posterior_predictive_plot={result.posterior_predictive_plot_path}")
    if result.holdout_posterior_predictive_csv_path is not None:
        print(
            "holdout_posterior_predictive_csv="
            f"{result.holdout_posterior_predictive_csv_path}"
        )
    if result.holdout_posterior_predictive_report_md_path is not None:
        print(
            "holdout_posterior_predictive_report_md="
            f"{result.holdout_posterior_predictive_report_md_path}"
        )
    if result.holdout_posterior_predictive_plot_path is not None:
        print(
            "holdout_posterior_predictive_plot="
            f"{result.holdout_posterior_predictive_plot_path}"
        )
    if result.manifest_json_path is not None:
        print(f"manifest_json={result.manifest_json_path}")
    return 0


def _run_infer_target_parameters_smc_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI sequential ABC-style target-parameter calibration workflow."""
    if args.config is None:
        parser.error("infer-target-parameters-smc requires --config")
    if args.targets is None:
        parser.error("infer-target-parameters-smc requires --targets")
    if args.holdout_targets is None and _has_holdout_outputs(args):
        parser.error("holdout posterior predictive outputs require --holdout-targets")
    holdout_targets = (
        load_target_dataset(args.holdout_targets)
        if args.holdout_targets is not None
        else None
    )
    result = run_abc_smc_workflow(
        load_sweep_spec(args.config),
        load_target_dataset(args.targets),
        options=ABCSMCOptions(
            fit_metric=args.fit_metric,
            generation_count=args.smc_generations,
            sample_count=args.smc_sample_count,
            acceptance_quantile=args.acceptance_quantile,
            acceptance_count=args.acceptance_count,
            seed_stride=args.smc_seed_stride,
            range_quantile_low=args.smc_range_quantile_low,
            range_quantile_high=args.smc_range_quantile_high,
            range_padding_fraction=args.smc_range_padding_fraction,
        ),
        paths=ABCSMCOutputPaths(
            config=args.config,
            targets=args.targets,
            generations_csv=args.smc_generations_csv,
            final_samples_csv=args.posterior_samples_csv,
            final_summary_csv=args.posterior_summary_csv,
            inference_report_md=args.inference_report_md,
            posterior_predictive_csv=args.posterior_predictive_csv,
            posterior_predictive_report_md=args.posterior_predictive_report_md,
            posterior_predictive_plot=args.posterior_predictive_plot,
            holdout_targets=args.holdout_targets,
            holdout_posterior_predictive_csv=args.holdout_posterior_predictive_csv,
            holdout_posterior_predictive_report_md=(
                args.holdout_posterior_predictive_report_md
            ),
            holdout_posterior_predictive_plot=args.holdout_posterior_predictive_plot,
            manifest_json=args.manifest_json,
        ),
        command=args.command,
        manifest_name="cli-abc-smc-calibration",
        manifest_description="CLI ABC-SMC-style target calibration manifest",
        interval_probability=args.posterior_predictive_interval_probability,
        holdout_targets=holdout_targets,
    )
    _print_smc_result(result)
    return 0


def _print_smc_result(result: ABCSMCWorkflowResult) -> None:
    """Print compact machine-readable SMC calibration summary lines."""
    inference = result.inference
    diagnostics = result.posterior_predictive
    print(f"smc_generation_count={len(inference.generations)}")
    print(f"smc_total_candidate_count={inference.total_candidate_count}")
    print(f"smc_final_accepted_count={inference.final_inference.accepted_count}")
    print(f"smc_fit_metric={inference.options.fit_metric}")
    print(
        "smc_threshold_schedule="
        + ",".join(f"{threshold:.6f}" for threshold in inference.threshold_schedule)
    )
    print(
        "smc_final_acceptance_threshold="
        f"{inference.final_inference.acceptance_threshold:.6f}"
    )
    print(f"smc_final_best_run_index={inference.final_inference.best_run.run.index}")
    if diagnostics is not None:
        print(
            "posterior_predictive="
            f"coverage_rate={diagnostics.coverage_rate:.6f},"
            f"rmse={diagnostics.root_mean_squared_error:.6f},"
            f"max_abs_z={diagnostics.max_abs_z_score:.6f}"
        )
    if result.holdout_posterior_predictive is not None:
        holdout_diagnostics = result.holdout_posterior_predictive
        print(
            "holdout_posterior_predictive="
            f"coverage_rate={holdout_diagnostics.coverage_rate:.6f},"
            f"rmse={holdout_diagnostics.root_mean_squared_error:.6f},"
            f"max_abs_z={holdout_diagnostics.max_abs_z_score:.6f}"
        )
    _print_smc_paths(result)


def _print_smc_paths(result: ABCSMCWorkflowResult) -> None:
    """Print optional SMC output paths that were requested."""
    path_labels = (
        ("smc_generations_csv", "generations_csv_path"),
        ("posterior_samples_csv", "final_samples_csv_path"),
        ("posterior_summary_csv", "final_summary_csv_path"),
        ("inference_report_md", "inference_report_md_path"),
        ("posterior_predictive_csv", "posterior_predictive_csv_path"),
        ("posterior_predictive_report_md", "posterior_predictive_report_md_path"),
        ("posterior_predictive_plot", "posterior_predictive_plot_path"),
        ("holdout_posterior_predictive_csv", "holdout_posterior_predictive_csv_path"),
        (
            "holdout_posterior_predictive_report_md",
            "holdout_posterior_predictive_report_md_path",
        ),
        ("holdout_posterior_predictive_plot", "holdout_posterior_predictive_plot_path"),
        ("manifest_json", "manifest_json_path"),
    )
    for label, attribute in path_labels:
        value = getattr(result, attribute)
        if value is not None:
            print(f"{label}={value}")


def _has_holdout_outputs(args: argparse.Namespace) -> bool:
    """Return whether any holdout-only output path was requested."""
    return any(
        getattr(args, name) is not None
        for name in (
            "holdout_posterior_predictive_csv",
            "holdout_posterior_predictive_report_md",
            "holdout_posterior_predictive_plot",
        )
    )
