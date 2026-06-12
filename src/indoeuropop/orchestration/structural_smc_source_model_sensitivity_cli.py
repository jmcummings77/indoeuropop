"""CLI handler for structural SMC source-model sensitivity validation."""

from __future__ import annotations

import argparse
import tomllib
from pathlib import Path
from typing import Any

from indoeuropop.analysis.structural_head_to_head import StructuredPulseCandidate
from indoeuropop.data.targets import load_target_dataset
from indoeuropop.orchestration.child_region_overrides import (
    load_child_region_overrides,
)
from indoeuropop.orchestration.structural_smc_source_model_sensitivity import (
    run_structural_smc_source_model_sensitivity,
    structural_smc_source_model_sensitivity_paths_from_dir,
)
from indoeuropop.orchestration.structural_smc_source_model_sensitivity_models import (
    StructuralSMCSourceModel,
    StructuralSMCSourceModelSensitivityResult,
)
from indoeuropop.orchestration.structural_smc_validation_cli import (
    _explicit_folds,
    _smc_options,
    _target_fragility_flags,
)
from indoeuropop.reporting.structural_smc_uncertainty import (
    DEFAULT_MATERIAL_CHI_SQUARE_DELTA,
)
from indoeuropop.simulation.config import load_sweep_spec

STRUCTURAL_SMC_SOURCE_MODEL_SENSITIVITY_COMMANDS = (
    "validate-structured-smc-source-model-sensitivity",
)


def add_structural_smc_source_model_sensitivity_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    """Register source-model sensitivity CLI arguments."""
    parser.add_argument(
        "--source-model-targets",
        dest="source_model_targets",
        action="append",
        help="labeled target CSV as LABEL=PATH; pass at least two",
    )
    parser.add_argument(
        "--source-model-sensitivity-output-dir",
        type=Path,
        help="directory for source-model sensitivity artifacts",
    )
    parser.add_argument(
        "--source-model-structure-field",
        default="note:requested_group_id",
        help="target field used to structure source-model targets",
    )
    parser.add_argument(
        "--source-model-structure-region",
        action="append",
        help="parent region to split for source-model targets; repeat as needed",
    )
    parser.add_argument(
        "--source-model-keep-unshared-targets",
        action="store_true",
        help="use the first model's target IDs instead of shared target IDs",
    )
    parser.add_argument(
        "--source-model-require-all-child-overrides",
        action="store_true",
        help="fail if a source-model target set lacks any child override region",
    )
    parser.add_argument(
        "--source-model-material-chi-square-delta",
        type=float,
        default=DEFAULT_MATERIAL_CHI_SQUARE_DELTA,
        help="minimum chi-square delta for material uncertainty preference",
    )


def run_structural_smc_source_model_sensitivity_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int | None:
    """Run the source-model sensitivity command or return `None`."""
    if args.command not in STRUCTURAL_SMC_SOURCE_MODEL_SENSITIVITY_COMMANDS:
        return None
    _require_inputs(args, parser)
    source_models = _parse_source_model_targets(args.source_model_targets, parser)
    result = run_structural_smc_source_model_sensitivity(
        load_sweep_spec(args.config),
        source_models,
        load_child_region_overrides(args.child_region_overrides),
        StructuredPulseCandidate(
            name=args.structured_pulse_candidate_name,
            region_prefix=args.structured_pulse_region_prefix,
            start_bce=args.structured_pulse_start_bce,
            end_bce=args.structured_pulse_end_bce,
            annual_rate=args.structured_pulse_annual_rate,
        ),
        sample_audit_csv=args.target_fragility_audit_csv,
        structure_field=args.source_model_structure_field,
        structure_regions=args.source_model_structure_region or (),
        align_common_targets=not args.source_model_keep_unshared_targets,
        require_all_child_overrides=args.source_model_require_all_child_overrides,
        include_default_folds=not args.smc_validation_no_default_folds,
        include_chronology=not args.smc_validation_no_chronology,
        region_prefix=args.structured_pulse_region_prefix,
        protected_values=_review_holdout_values(
            args.child_region_overrides, "protected_holdouts"
        )
        + tuple(args.protected_validation_value or ()),
        priority_values=_review_holdout_values(
            args.child_region_overrides, "priority_holdouts"
        )
        + tuple(args.priority_validation_value or ()),
        explicit_folds=_explicit_folds(
            args.validation_field, tuple(args.validation_value or ())
        ),
        child_candidate_name=args.child_region_candidate_name,
        options=_smc_options(args),
        paths=structural_smc_source_model_sensitivity_paths_from_dir(
            args.source_model_sensitivity_output_dir
        ),
        interval_probability=args.posterior_predictive_interval_probability,
        excluded_flags=_target_fragility_flags(args),
        exclude_repeated_estimates=not args.target_fragility_keep_repeated_estimates,
        repeated_estimate_tolerance=args.target_fragility_repeated_estimate_tolerance,
        material_chi_square_delta=args.source_model_material_chi_square_delta,
        child_region_overrides_path=args.child_region_overrides,
        command=args.command,
    )
    _print_result(result)
    return 0


def _require_inputs(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> None:
    """Raise argparse errors for missing source-model sensitivity inputs."""
    required = (
        "config",
        "child_region_overrides",
        "structured_pulse_region_prefix",
        "structured_pulse_start_bce",
        "structured_pulse_end_bce",
        "structured_pulse_annual_rate",
        "source_model_sensitivity_output_dir",
    )
    for argument_name in required:
        if getattr(args, argument_name) is None:
            parser.error(f"{args.command} requires --{argument_name.replace('_', '-')}")


def _parse_source_model_targets(
    values: list[str] | None,
    parser: argparse.ArgumentParser,
) -> tuple[StructuralSMCSourceModel, ...]:
    """Parse `LABEL=PATH` source-model target arguments."""
    if values is None or len(values) < 2:
        parser.error("source-model sensitivity requires at least two target sets")
    label_paths: list[tuple[str, Path]] = []
    labels: set[str] = set()
    for value in values:
        if "=" not in value:
            parser.error("--source-model-targets must be formatted as LABEL=PATH")
        label, raw_path = value.split("=", 1)
        label = label.strip()
        if not label:
            parser.error("--source-model-targets labels must be non-empty")
        if label in labels:
            parser.error(f"duplicate source-model label: {label}")
        labels.add(label)
        label_paths.append((label, Path(raw_path)))
    models: list[StructuralSMCSourceModel] = []
    for label, target_path in label_paths:
        models.append(
            StructuralSMCSourceModel(
                label=label,
                targets=load_target_dataset(target_path),
                target_path=target_path,
            )
        )
    return tuple(models)


def _review_holdout_values(path: Path, key: str) -> tuple[str, ...]:
    """Return priority/protected holdout values from an override review table."""
    with path.open("rb") as override_file:
        raw = tomllib.load(override_file)
    review = raw.get("review", {})
    raw_values: Any = review.get(key, ()) if isinstance(review, dict) else ()
    if isinstance(raw_values, str):
        return (raw_values.strip(),) if raw_values.strip() else ()
    return tuple(str(value).strip() for value in raw_values if str(value).strip())


def _print_result(result: StructuralSMCSourceModelSensitivityResult) -> None:
    """Print compact machine-readable source-model sensitivity summary lines."""
    print("source_model_sensitivity=true")
    print(f"source_model_sensitivity_model_count={result.source_model_count}")
    print(
        f"source_model_sensitivity_common_target_count={len(result.common_target_ids)}"
    )
    print(
        "source_model_sensitivity_excluded_fragile_target_count="
        f"{len(result.excluded_fragile_target_ids)}"
    )
    print(
        "source_model_sensitivity_retained_common_target_count="
        f"{result.retained_common_target_count}"
    )
    print(
        "source_model_sensitivity_unstable_holdout_fold_count="
        f"{result.unstable_holdout_fold_count}"
    )
    for run in result.runs:
        print(
            "source_model_sensitivity_model="
            f"{run.label},"
            f"targets={run.prepared_target_count},"
            f"folds={len(run.validation_result.folds)},"
            f"disagreements={run.preference_disagreement_count},"
            f"missing_overrides={len(run.missing_override_regions)}"
        )
    print(f"source_model_sensitivity_summary_csv={result.paths.summary_csv}")
    print(f"source_model_sensitivity_report_md={result.paths.report_md}")
