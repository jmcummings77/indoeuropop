"""CLI handlers for multi-fold structural SMC validation."""

from __future__ import annotations

import argparse
import tomllib
from pathlib import Path
from typing import Any

from indoeuropop.analysis.abc_smc import ABCSMCOptions
from indoeuropop.analysis.structural_head_to_head import StructuredPulseCandidate
from indoeuropop.data.targets import TargetDataset, load_target_dataset
from indoeuropop.orchestration.child_region_overrides import (
    load_child_region_overrides,
)
from indoeuropop.orchestration.structural_smc_validation import (
    default_structural_smc_validation_folds,
    run_structural_smc_multifold_validation_workflow,
)
from indoeuropop.orchestration.structural_smc_validation_models import (
    StructuralSMCMultiFoldValidationResult,
    StructuralSMCValidationFoldSpec,
    merge_structural_smc_validation_folds,
)
from indoeuropop.orchestration.structural_smc_validation_outputs import (
    structural_smc_validation_output_paths_from_dir,
)
from indoeuropop.orchestration.target_fragility import (
    run_structural_smc_target_fragility_gate,
    target_fragility_gate_paths_from_dir,
)
from indoeuropop.orchestration.target_fragility_models import (
    DEFAULT_REPEATED_ESTIMATE_TOLERANCE,
    DEFAULT_TARGET_FRAGILITY_FLAGS,
    TargetFragilityGateResult,
)
from indoeuropop.simulation.config import load_sweep_spec

STRUCTURAL_SMC_VALIDATION_COMMANDS = (
    "validate-structured-candidates-smc",
    "validate-structured-smc-target-fragility",
)


def add_structural_smc_validation_arguments(parser: argparse.ArgumentParser) -> None:
    """Register structural SMC multi-fold validation arguments."""
    parser.add_argument(
        "--smc-validation-output-dir",
        type=Path,
        help="directory for multi-fold structural SMC validation artifacts",
    )
    parser.add_argument(
        "--smc-validation-no-default-folds",
        action="store_true",
        help="use only explicit --validation-value folds",
    )
    parser.add_argument(
        "--smc-validation-no-chronology",
        action="store_true",
        help="omit default chronology-band validation folds",
    )
    parser.add_argument(
        "--target-fragility-audit-csv",
        type=Path,
        help="sample audit CSV used to identify fragile target IDs",
    )
    parser.add_argument(
        "--target-fragility-output-dir",
        type=Path,
        help="directory for target-fragility gate artifacts",
    )
    parser.add_argument(
        "--target-fragility-flag",
        dest="target_fragility_flags",
        action="append",
        help="sample flag that excludes a target; may be passed more than once",
    )
    parser.add_argument(
        "--target-fragility-keep-repeated-estimates",
        action="store_true",
        help="do not exclude targets whose samples share one repeated estimate",
    )
    parser.add_argument(
        "--target-fragility-repeated-estimate-tolerance",
        type=float,
        default=DEFAULT_REPEATED_ESTIMATE_TOLERANCE,
        help="absolute tolerance for detecting repeated sample estimates",
    )


def run_structural_smc_validation_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int | None:
    """Run structural SMC validation commands or return `None`."""
    if args.command not in STRUCTURAL_SMC_VALIDATION_COMMANDS:
        return None
    if args.command == "validate-structured-smc-target-fragility":
        return _run_target_fragility_command(args, parser)
    _require_inputs(args, parser)
    targets = load_target_dataset(args.targets)
    folds = _validation_folds(args, parser, targets)
    result = run_structural_smc_multifold_validation_workflow(
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
        folds=folds,
        child_candidate_name=args.child_region_candidate_name,
        options=_smc_options(args),
        paths=structural_smc_validation_output_paths_from_dir(
            args.smc_validation_output_dir,
            config=args.config,
            targets=args.targets,
            child_region_overrides=args.child_region_overrides,
        ),
        interval_probability=args.posterior_predictive_interval_probability,
        command=args.command,
    )
    _print_result(result)
    return 0


def _run_target_fragility_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    """Run a target-fragility sensitivity gate for structural SMC validation."""
    _require_inputs(args, parser, require_validation_output_dir=False)
    _require_target_fragility_inputs(args, parser)
    targets = load_target_dataset(args.targets)
    folds = _validation_folds(args, parser, targets)
    result = run_structural_smc_target_fragility_gate(
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
        folds=folds,
        child_candidate_name=args.child_region_candidate_name,
        options=_smc_options(args),
        paths=target_fragility_gate_paths_from_dir(args.target_fragility_output_dir),
        interval_probability=args.posterior_predictive_interval_probability,
        excluded_flags=_target_fragility_flags(args),
        exclude_repeated_estimates=not args.target_fragility_keep_repeated_estimates,
        repeated_estimate_tolerance=args.target_fragility_repeated_estimate_tolerance,
        config_path=args.config,
        child_region_overrides_path=args.child_region_overrides,
        command=args.command,
    )
    _print_target_fragility_result(result)
    return 0


def _require_inputs(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    *,
    require_validation_output_dir: bool = True,
) -> None:
    """Raise argparse errors for missing structural validation inputs."""
    required = [
        "config",
        "targets",
        "child_region_overrides",
        "structured_pulse_region_prefix",
        "structured_pulse_start_bce",
        "structured_pulse_end_bce",
        "structured_pulse_annual_rate",
    ]
    if require_validation_output_dir:
        required.append("smc_validation_output_dir")
    for argument_name in required:
        if getattr(args, argument_name) is None:
            parser.error(
                f"{args.command} requires " f"--{argument_name.replace('_', '-')}"
            )


def _require_target_fragility_inputs(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> None:
    """Raise argparse errors for missing target-fragility gate inputs."""
    for argument_name in ("target_fragility_audit_csv", "target_fragility_output_dir"):
        if getattr(args, argument_name) is None:
            parser.error(f"{args.command} requires --{argument_name.replace('_', '-')}")


def _validation_folds(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    targets: TargetDataset,
) -> tuple[StructuralSMCValidationFoldSpec, ...]:
    """Return default and explicit validation fold specifications."""
    protected_values = _review_holdout_values(
        args.child_region_overrides, "protected_holdouts"
    ) + tuple(args.protected_validation_value or ())
    priority_values = _review_holdout_values(
        args.child_region_overrides, "priority_holdouts"
    ) + tuple(args.priority_validation_value or ())
    folds: list[StructuralSMCValidationFoldSpec] = []
    if not args.smc_validation_no_default_folds:
        folds.extend(
            default_structural_smc_validation_folds(
                targets,
                region_prefix=args.structured_pulse_region_prefix,
                protected_values=protected_values,
                priority_values=priority_values,
                include_chronology=not args.smc_validation_no_chronology,
            )
        )
    folds.extend(_explicit_folds(args.validation_field, args.validation_value or ()))
    merged = merge_structural_smc_validation_folds(folds)
    if not merged:
        parser.error(f"{args.command} requires at least one fold")
    return merged


def _explicit_folds(
    holdout_field: str,
    values: tuple[str, ...],
) -> tuple[StructuralSMCValidationFoldSpec, ...]:
    """Return explicit field folds from CLI validation values."""
    return tuple(
        StructuralSMCValidationFoldSpec(
            name=f"{holdout_field}_{value}",
            categories=("explicit",),
            holdout_field=holdout_field,
            holdout_value=value,
        )
        for value in values
    )


def _review_holdout_values(path: Path, key: str) -> tuple[str, ...]:
    """Return priority/protected holdout values from an override review table."""
    with path.open("rb") as override_file:
        raw = tomllib.load(override_file)
    review = raw.get("review", {})
    raw_values: Any = review.get(key, ()) if isinstance(review, dict) else ()
    if isinstance(raw_values, str):
        return (raw_values.strip(),) if raw_values.strip() else ()
    return tuple(str(value).strip() for value in raw_values if str(value).strip())


def _smc_options(args: argparse.Namespace) -> ABCSMCOptions:
    """Return SMC options for multi-fold structural comparison."""
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


def _target_fragility_flags(args: argparse.Namespace) -> tuple[str, ...]:
    """Return CLI-selected target-fragility sample flags."""
    flags = args.target_fragility_flags
    if flags is None:
        return DEFAULT_TARGET_FRAGILITY_FLAGS
    return tuple(flag for flag in flags if flag.strip())


def _print_result(result: StructuralSMCMultiFoldValidationResult) -> None:
    """Print compact machine-readable structural SMC validation summary lines."""
    print("structural_smc_validation=true")
    print(f"structural_smc_validation_fold_count={len(result.folds)}")
    print(
        "structural_smc_validation_preference_disagreement_count="
        f"{result.preference_disagreement_count}"
    )
    print(
        "structural_smc_validation_calibration_child_preferred_count="
        f"{_candidate_count(result, 'calibration', 'child_override')}"
    )
    print(
        "structural_smc_validation_holdout_child_preferred_count="
        f"{_candidate_count(result, 'holdout', 'child_override')}"
    )
    if result.summary_csv_path is not None:
        print(f"structural_smc_validation_summary_csv={result.summary_csv_path}")
    if result.report_md_path is not None:
        print(f"structural_smc_validation_report_md={result.report_md_path}")
    if result.manifest_json_path is not None:
        print(f"manifest_json={result.manifest_json_path}")


def _print_target_fragility_result(result: TargetFragilityGateResult) -> None:
    """Print compact machine-readable target-fragility gate summary lines."""
    print("target_fragility_gate=true")
    print(f"target_fragility_original_target_count={result.original_target_count}")
    print(f"target_fragility_retained_target_count={result.filtered_target_count}")
    print(f"target_fragility_excluded_target_count={result.excluded_target_count}")
    print(f"target_fragility_skipped_fold_count={result.skipped_fold_count}")
    print(
        "target_fragility_validation_fold_count="
        f"{len(result.validation_result.folds)}"
    )
    print(
        "target_fragility_validation_preference_disagreement_count="
        f"{result.validation_result.preference_disagreement_count}"
    )
    print(f"target_fragility_filtered_targets={result.paths.filtered_targets_csv}")
    print(f"target_fragility_decisions_csv={result.paths.decisions_csv}")
    print(f"target_fragility_report_md={result.paths.report_md}")
    if result.validation_result.summary_csv_path is not None:
        print(
            "target_fragility_validation_summary_csv="
            f"{result.validation_result.summary_csv_path}"
        )
    if result.validation_result.report_md_path is not None:
        print(
            "target_fragility_validation_report_md="
            f"{result.validation_result.report_md_path}"
        )


def _candidate_count(
    result: StructuralSMCMultiFoldValidationResult,
    split: str,
    candidate: str,
) -> int:
    """Return how often one candidate is preferred in a split."""
    if split == "calibration":
        return sum(
            fold.calibration_preferred_candidate == candidate for fold in result.folds
        )
    return sum(fold.holdout_preferred_candidate == candidate for fold in result.folds)
