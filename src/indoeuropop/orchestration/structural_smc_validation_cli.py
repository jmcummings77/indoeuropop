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
from indoeuropop.simulation.config import load_sweep_spec

STRUCTURAL_SMC_VALIDATION_COMMANDS = ("validate-structured-candidates-smc",)


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


def run_structural_smc_validation_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int | None:
    """Run structural SMC validation commands or return `None`."""
    if args.command != "validate-structured-candidates-smc":
        return None
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


def _require_inputs(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Raise argparse errors for missing structural validation inputs."""
    for argument_name in (
        "config",
        "targets",
        "child_region_overrides",
        "structured_pulse_region_prefix",
        "structured_pulse_start_bce",
        "structured_pulse_end_bce",
        "structured_pulse_annual_rate",
        "smc_validation_output_dir",
    ):
        if getattr(args, argument_name) is None:
            parser.error(
                "validate-structured-candidates-smc requires "
                f"--{argument_name.replace('_', '-')}"
            )


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
        parser.error("validate-structured-candidates-smc requires at least one fold")
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
