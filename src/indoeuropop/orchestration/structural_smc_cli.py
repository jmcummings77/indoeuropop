"""CLI handlers for SMC-based structural candidate comparisons."""

from __future__ import annotations

import argparse
from pathlib import Path

from indoeuropop.analysis.abc_smc import ABCSMCOptions
from indoeuropop.analysis.structural_head_to_head import StructuredPulseCandidate
from indoeuropop.analysis.validation import split_targets_by_holdout_value
from indoeuropop.data.targets import TargetDataset, load_target_dataset
from indoeuropop.orchestration.abc_smc import ABCSMCWorkflowResult
from indoeuropop.orchestration.child_region_overrides import (
    load_child_region_overrides,
)
from indoeuropop.orchestration.structural_smc import (
    run_structural_smc_head_to_head_workflow,
)
from indoeuropop.orchestration.structural_smc_outputs import (
    StructuralSMCComparisonResult,
    structural_smc_output_paths_from_dir,
)
from indoeuropop.simulation.config import load_sweep_spec

STRUCTURAL_SMC_COMMANDS = ("compare-structured-candidates-smc",)


def add_structural_smc_arguments(parser: argparse.ArgumentParser) -> None:
    """Register structural SMC comparison arguments."""
    parser.add_argument(
        "--smc-comparison-output-dir",
        type=Path,
        help="directory for structural SMC comparison artifacts",
    )


def run_structural_smc_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int | None:
    """Run structural SMC commands or return `None` for unrelated commands."""
    if args.command != "compare-structured-candidates-smc":
        return None
    _require_structural_smc_inputs(args, parser)
    calibration_targets, holdout_targets = _target_datasets(args, parser)
    result = run_structural_smc_head_to_head_workflow(
        load_sweep_spec(args.config),
        calibration_targets,
        load_child_region_overrides(args.child_region_overrides),
        StructuredPulseCandidate(
            name=args.structured_pulse_candidate_name,
            region_prefix=args.structured_pulse_region_prefix,
            start_bce=args.structured_pulse_start_bce,
            end_bce=args.structured_pulse_end_bce,
            annual_rate=args.structured_pulse_annual_rate,
        ),
        child_candidate_name=args.child_region_candidate_name,
        options=_smc_options(args),
        paths=structural_smc_output_paths_from_dir(
            args.smc_comparison_output_dir,
            config=args.config,
            targets=args.targets,
            holdout_targets=args.holdout_targets,
            child_region_overrides=args.child_region_overrides,
        ),
        interval_probability=args.posterior_predictive_interval_probability,
        focus_observation_index=args.focus_observation_index,
        holdout_targets=holdout_targets,
        command=args.command,
        manifest_name="cli-structured-smc-head-to-head",
    )
    _print_structural_smc_result(result)
    return 0


def _require_structural_smc_inputs(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> None:
    """Raise argparse errors for missing structural SMC inputs."""
    for argument_name in (
        "config",
        "targets",
        "child_region_overrides",
        "structured_pulse_region_prefix",
        "structured_pulse_start_bce",
        "structured_pulse_end_bce",
        "structured_pulse_annual_rate",
        "smc_comparison_output_dir",
    ):
        if getattr(args, argument_name) is None:
            parser.error(
                "compare-structured-candidates-smc requires "
                f"--{argument_name.replace('_', '-')}"
            )


def _smc_options(args: argparse.Namespace) -> ABCSMCOptions:
    """Return SMC options for structural comparison."""
    return ABCSMCOptions(
        fit_metric=args.fit_metric,
        generation_count=args.smc_generations,
        sample_count=args.smc_sample_count,
        acceptance_quantile=args.acceptance_quantile,
        acceptance_count=args.acceptance_count,
        seed_stride=args.smc_seed_stride,
        range_quantile_low=args.smc_range_quantile_low,
        range_quantile_high=args.smc_range_quantile_high,
        range_padding_fraction=args.smc_range_padding_fraction,
    )


def _target_datasets(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> tuple[TargetDataset, TargetDataset | None]:
    """Return calibration and optional holdout targets for structural SMC."""
    targets = load_target_dataset(args.targets)
    validation_values = tuple(args.validation_value or ())
    if args.holdout_targets is not None:
        if validation_values:
            parser.error("--holdout-targets cannot be combined with --validation-value")
        return targets, load_target_dataset(args.holdout_targets)
    if validation_values:
        if len(validation_values) != 1:
            parser.error("compare-structured-candidates-smc requires one holdout value")
        split = split_targets_by_holdout_value(
            targets,
            args.validation_field,
            validation_values[0],
        )
        return split.calibration, split.validation
    return targets, None


def _print_structural_smc_result(result: StructuralSMCComparisonResult) -> None:
    """Print compact machine-readable structural SMC summary lines."""
    print("structured_smc_head_to_head=true")
    print(f"structured_pulse_candidate={result.structured_pulse_candidate.name}")
    print(f"structured_pulse_region_count={result.structured_pulse_region_count}")
    print(f"child_region_candidate={result.child_candidate.name}")
    print(f"baseline_smc_rmse={_rmse(result.baseline):.6f}")
    print(f"structured_pulse_smc_rmse={_rmse(result.structured_pulse_result):.6f}")
    print(f"child_smc_rmse={_rmse(result.child_result):.6f}")
    print(
        "structured_pulse_smc_rmse_delta="
        f"{result.structured_pulse_delta.root_mean_squared_error_delta:.6f}"
    )
    print(
        f"child_smc_rmse_delta={result.child_delta.root_mean_squared_error_delta:.6f}"
    )
    print(
        "child_minus_structured_pulse_smc_rmse_delta="
        f"{result.child_minus_structured_pulse_rmse_delta:.6f}"
    )
    if result.child_minus_structured_pulse_holdout_rmse_delta is not None:
        print(
            "child_minus_structured_pulse_holdout_rmse_delta="
            f"{result.child_minus_structured_pulse_holdout_rmse_delta:.6f}"
        )
    if result.head_to_head_report_md_path is not None:
        print(f"head_to_head_report_md={result.head_to_head_report_md_path}")
    if result.manifest_json_path is not None:
        print(f"manifest_json={result.manifest_json_path}")


def _rmse(result: ABCSMCWorkflowResult) -> float:
    """Return calibration posterior predictive RMSE for one workflow result."""
    posterior_predictive = result.posterior_predictive
    assert posterior_predictive is not None
    return float(posterior_predictive.root_mean_squared_error)
