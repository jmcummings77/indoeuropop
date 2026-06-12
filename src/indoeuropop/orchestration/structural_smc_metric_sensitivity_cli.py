"""CLI handler for structural SMC fit-metric sensitivity validation."""

from __future__ import annotations

import argparse
from pathlib import Path

from indoeuropop.analysis.structural_head_to_head import StructuredPulseCandidate
from indoeuropop.data.targets import load_target_dataset
from indoeuropop.orchestration.child_region_overrides import (
    load_child_region_overrides,
)
from indoeuropop.orchestration.structural_smc_metric_sensitivity import (
    run_structural_smc_fit_metric_sensitivity,
    structural_smc_fit_metric_sensitivity_paths_from_dir,
)
from indoeuropop.orchestration.structural_smc_metric_sensitivity_models import (
    DEFAULT_STRUCTURAL_SMC_FIT_METRICS,
    StructuralSMCFitMetricSensitivityResult,
)
from indoeuropop.orchestration.structural_smc_validation_cli import (
    _require_inputs,
    _smc_options,
    _target_fragility_flags,
    _validation_folds,
)
from indoeuropop.reporting.structural_smc_uncertainty import (
    DEFAULT_MATERIAL_CHI_SQUARE_DELTA,
)
from indoeuropop.simulation.config import load_sweep_spec

STRUCTURAL_SMC_METRIC_SENSITIVITY_COMMANDS = (
    "validate-structured-smc-fit-metric-sensitivity",
)


def add_structural_smc_metric_sensitivity_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    """Register structural SMC fit-metric sensitivity CLI arguments."""
    parser.add_argument(
        "--fit-metric-sensitivity-output-dir",
        type=Path,
        help="directory for structural SMC fit-metric sensitivity artifacts",
    )
    parser.add_argument(
        "--fit-metric-sensitivity-metric",
        dest="fit_metric_sensitivity_metrics",
        action="append",
        help="fit metric to evaluate; may be passed more than once",
    )
    parser.add_argument(
        "--fit-metric-sensitivity-material-chi-square-delta",
        type=float,
        default=DEFAULT_MATERIAL_CHI_SQUARE_DELTA,
        help="minimum chi-square delta for material uncertainty preference",
    )


def run_structural_smc_metric_sensitivity_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int | None:
    """Run the fit-metric sensitivity command or return `None`."""
    if args.command not in STRUCTURAL_SMC_METRIC_SENSITIVITY_COMMANDS:
        return None
    _require_inputs(args, parser, require_validation_output_dir=False)
    if args.target_fragility_audit_csv is None:
        parser.error(f"{args.command} requires --target-fragility-audit-csv")
    if args.fit_metric_sensitivity_output_dir is None:
        parser.error(f"{args.command} requires --fit-metric-sensitivity-output-dir")
    targets = load_target_dataset(args.targets)
    result = run_structural_smc_fit_metric_sensitivity(
        load_sweep_spec(args.config),
        targets,
        load_child_region_overrides(args.child_region_overrides),
        StructuredPulseCandidate(
            name=args.structured_pulse_candidate_name,
            region_prefix=args.structured_pulse_region_prefix,
            start_bce=args.structured_pulse_start_bce,
            end_bce=args.structured_pulse_end_bce,
            annual_rate=args.structured_pulse_annual_rate,
        ),
        sample_audit_csv=args.target_fragility_audit_csv,
        folds=_validation_folds(args, parser, targets),
        fit_metrics=tuple(
            args.fit_metric_sensitivity_metrics or DEFAULT_STRUCTURAL_SMC_FIT_METRICS
        ),
        child_candidate_name=args.child_region_candidate_name,
        options=_smc_options(args),
        paths=structural_smc_fit_metric_sensitivity_paths_from_dir(
            args.fit_metric_sensitivity_output_dir
        ),
        interval_probability=args.posterior_predictive_interval_probability,
        excluded_flags=_target_fragility_flags(args),
        exclude_repeated_estimates=not args.target_fragility_keep_repeated_estimates,
        repeated_estimate_tolerance=args.target_fragility_repeated_estimate_tolerance,
        material_chi_square_delta=(
            args.fit_metric_sensitivity_material_chi_square_delta
        ),
        config_path=args.config,
        child_region_overrides_path=args.child_region_overrides,
        command=args.command,
    )
    _print_result(result)
    return 0


def _print_result(result: StructuralSMCFitMetricSensitivityResult) -> None:
    """Print compact machine-readable fit-metric sensitivity summary lines."""
    print("fit_metric_sensitivity=true")
    print(f"fit_metric_sensitivity_metric_count={len(result.runs)}")
    print(
        "fit_metric_sensitivity_original_target_count="
        f"{result.original_target_count}"
    )
    print(
        "fit_metric_sensitivity_retained_target_count="
        f"{result.filtered_target_count}"
    )
    print(
        "fit_metric_sensitivity_excluded_target_count="
        f"{result.excluded_target_count}"
    )
    print("fit_metric_sensitivity_skipped_fold_count=" f"{result.skipped_fold_count}")
    print(
        "fit_metric_sensitivity_unstable_holdout_fold_count="
        f"{result.unstable_holdout_fold_count}"
    )
    for run in result.runs:
        print(
            "fit_metric_sensitivity_metric="
            f"{run.fit_metric},"
            f"folds={len(run.validation_result.folds)},"
            f"disagreements={run.preference_disagreement_count},"
            f"uncertainty_ties={run.uncertainty_tie_target_count}"
        )
    print(f"fit_metric_sensitivity_summary_csv={result.paths.summary_csv}")
    print(f"fit_metric_sensitivity_report_md={result.paths.report_md}")
