"""Target comparison and held-out validation CLI handlers."""

from __future__ import annotations

import argparse
from pathlib import Path

from indoeuropop.data.targets import load_target_dataset
from indoeuropop.orchestration.child_region_overrides import (
    ChildRegionOverrideOutputPaths,
    load_child_region_overrides,
    run_child_region_override_workflow,
)
from indoeuropop.orchestration.target_comparison import (
    TargetComparisonOutputPaths,
    run_target_comparison_workflow,
)
from indoeuropop.orchestration.target_refinement import (
    TargetRefinementOutputPaths,
    run_target_refinement_workflow,
)
from indoeuropop.orchestration.target_structure import (
    TargetStructureOutputPaths,
    run_target_structure_workflow,
)
from indoeuropop.orchestration.target_validation import (
    TargetValidationOutputPaths,
    run_target_validation_workflow,
)
from indoeuropop.simulation.config import load_sweep_spec

TARGET_COMMANDS = (
    "apply-child-region-overrides",
    "compare-targets",
    "refine-target-parameters",
    "structure-target-regions",
    "validate-targets",
)


def add_target_arguments(parser: argparse.ArgumentParser) -> None:
    """Add target-analysis command arguments to the shared CLI parser."""
    parser.add_argument(
        "--validation-field",
        default="region",
        help="target field to leave out: region, source, citation_key, or note:<key>",
    )
    parser.add_argument(
        "--structure-field",
        default="note:requested_group_id",
        help=(
            "target field used to split regions: region, source, citation_key, "
            "or note:<key>"
        ),
    )
    parser.add_argument(
        "--structure-region",
        action="append",
        help="parent region to split into target-aligned regions; repeat as needed",
    )
    parser.add_argument(
        "--structured-targets-out",
        type=Path,
        help="output CSV path for target-aligned structured targets",
    )
    parser.add_argument(
        "--structured-config-out",
        type=Path,
        help="output TOML path for target-aligned structured sweep config",
    )
    parser.add_argument(
        "--child-region-overrides",
        type=Path,
        help="partial TOML file with curated child-region override tables",
    )
    parser.add_argument(
        "--overridden-config-out",
        type=Path,
        help="output TOML path for a config after child-region overrides",
    )
    parser.add_argument(
        "--validation-value",
        action="append",
        help="specific holdout value; repeat or omit for leave-one-value-out",
    )
    parser.add_argument(
        "--validation-fit-csv",
        type=Path,
        help="optional output path for held-out validation fit rows",
    )
    parser.add_argument(
        "--validation-report-md",
        type=Path,
        help="optional output path for held-out validation Markdown",
    )
    parser.add_argument(
        "--priority-validation-value",
        action="append",
        help="holdout value expected to improve in refinement; can repeat",
    )
    parser.add_argument(
        "--protected-validation-value",
        action="append",
        help="holdout value that should not degrade in refinement; can repeat",
    )
    parser.add_argument(
        "--refinement-summary-csv",
        type=Path,
        help="optional output path for refinement scenario summary rows",
    )
    parser.add_argument(
        "--refinement-ranges-csv",
        type=Path,
        help="optional output path for refinement parameter-range rows",
    )
    parser.add_argument(
        "--refinement-report-md",
        type=Path,
        help="optional output path for refinement Markdown report",
    )
    parser.add_argument(
        "--refinement-narrow-fraction",
        type=float,
        default=0.5,
        help="fraction of original interval width for the narrowed candidate",
    )
    parser.add_argument(
        "--refinement-expand-factor",
        type=float,
        default=1.5,
        help="multiple of original interval width for the expanded candidate",
    )
    parser.add_argument(
        "--refinement-tolerance",
        type=float,
        default=0.0,
        help="non-negative metric tolerance for improvement/degradation flags",
    )


def run_target_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int | None:
    """Run target analysis commands or return `None` for unrelated commands."""
    if args.command == "apply-child-region-overrides":
        return _run_apply_child_region_overrides_command(args, parser)
    if args.command == "compare-targets":
        return _run_compare_targets_command(args, parser)
    if args.command == "refine-target-parameters":
        return _run_refine_target_parameters_command(args, parser)
    if args.command == "structure-target-regions":
        return _run_structure_target_regions_command(args, parser)
    if args.command == "validate-targets":
        return _run_validate_targets_command(args, parser)
    return None


def _run_compare_targets_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI deterministic target-comparison workflow."""
    if args.config is None:
        parser.error("compare-targets requires --config")
    if args.targets is None:
        parser.error("compare-targets requires --targets")
    result = run_target_comparison_workflow(
        load_sweep_spec(args.config),
        load_target_dataset(args.targets),
        paths=TargetComparisonOutputPaths(
            config=args.config,
            targets=args.targets,
            sweep_runs_csv=args.sweep_runs_csv,
            sensitivity_csv=args.sensitivity_csv,
            target_fit_csv=args.target_fit_csv,
            target_residuals_csv=args.target_residuals_csv,
            plot=args.plot,
            manifest_json=args.manifest_json,
        ),
        sensitivity_outcome=args.sensitivity_outcome,
        fit_metric=args.fit_metric,
        plot_source=args.source,
        plot_region=args.region,
        command=args.command,
        manifest_name="cli-target-comparison",
        manifest_description="CLI deterministic target-comparison manifest",
    )
    best_fit = result.best_run
    print(f"comparison_run_count={len(result.sweep.runs)}")
    print(
        "best_target_fit="
        f"run_index={best_fit.run.index},"
        f"metric={args.fit_metric},"
        f"value={best_fit.metric_value(args.fit_metric):.6f},"
        f"observations={best_fit.fit.observation_count}"
    )
    print(f"target_residual_count={len(result.best_comparisons)}")
    if result.target_residuals_csv_path is not None:
        print(f"target_residuals_csv={result.target_residuals_csv_path}")
    if result.plot_path is not None:
        print(f"target_comparison_plot={result.plot_path}")
    if result.manifest_json_path is not None:
        print(f"manifest_json={result.manifest_json_path}")
    return 0


def _run_validate_targets_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI held-out target-validation workflow."""
    if args.config is None:
        parser.error("validate-targets requires --config")
    if args.targets is None:
        parser.error("validate-targets requires --targets")
    result = run_target_validation_workflow(
        load_sweep_spec(args.config),
        load_target_dataset(args.targets),
        holdout_field=args.validation_field,
        holdout_values=args.validation_value or None,
        paths=TargetValidationOutputPaths(
            config=args.config,
            targets=args.targets,
            validation_fit_csv=args.validation_fit_csv,
            validation_report_md=args.validation_report_md,
            manifest_json=args.manifest_json,
        ),
        fit_metric=args.fit_metric,
        command=args.command,
        manifest_name="cli-target-validation",
        manifest_description="CLI held-out target-validation manifest",
    )
    print(f"validation_fold_count={len(result.folds)}")
    for fold in result.folds:
        best_run = fold.best_run
        print(
            "validation_fold="
            f"{fold.holdout_field}={fold.holdout_value},"
            f"best_run_index={best_run.run.index},"
            f"calibration_{args.fit_metric}="
            f"{best_run.metric_value(args.fit_metric, 'calibration'):.6f},"
            f"validation_{args.fit_metric}="
            f"{best_run.metric_value(args.fit_metric, 'validation'):.6f},"
            f"gap={best_run.generalization_gap(args.fit_metric):.6f}"
        )
    if result.validation_fit_csv_path is not None:
        print(f"validation_fit_csv={result.validation_fit_csv_path}")
    if result.validation_report_md_path is not None:
        print(f"validation_report_md={result.validation_report_md_path}")
    if result.manifest_json_path is not None:
        print(f"manifest_json={result.manifest_json_path}")
    return 0


def _run_refine_target_parameters_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI validation-guided target-parameter refinement workflow."""
    if args.config is None:
        parser.error("refine-target-parameters requires --config")
    if args.targets is None:
        parser.error("refine-target-parameters requires --targets")
    result = run_target_refinement_workflow(
        load_sweep_spec(args.config),
        load_target_dataset(args.targets),
        holdout_field=args.validation_field,
        holdout_values=args.validation_value or None,
        priority_values=args.priority_validation_value or (),
        protected_values=args.protected_validation_value or (),
        narrow_fraction=args.refinement_narrow_fraction,
        expand_factor=args.refinement_expand_factor,
        tolerance=args.refinement_tolerance,
        paths=TargetRefinementOutputPaths(
            config=args.config,
            targets=args.targets,
            refinement_summary_csv=args.refinement_summary_csv,
            refinement_ranges_csv=args.refinement_ranges_csv,
            refinement_report_md=args.refinement_report_md,
            manifest_json=args.manifest_json,
        ),
        fit_metric=args.fit_metric,
        command=args.command,
        manifest_name="cli-target-parameter-refinement",
        manifest_description="CLI validation-guided parameter refinement manifest",
    )
    print(f"refinement_candidate_count={len(result.scenarios)}")
    for scenario in result.scenarios:
        print(
            "refinement_candidate="
            f"{scenario.name},"
            f"kind={scenario.candidate.kind},"
            f"mean_validation_{args.fit_metric}="
            f"{scenario.mean_validation_metric():.6f},"
            f"worst_validation_{args.fit_metric}="
            f"{scenario.worst_validation_metric():.6f}"
        )
    if result.refinement_summary_csv_path is not None:
        print(f"refinement_summary_csv={result.refinement_summary_csv_path}")
    if result.refinement_ranges_csv_path is not None:
        print(f"refinement_ranges_csv={result.refinement_ranges_csv_path}")
    if result.refinement_report_md_path is not None:
        print(f"refinement_report_md={result.refinement_report_md_path}")
    if result.manifest_json_path is not None:
        print(f"manifest_json={result.manifest_json_path}")
    return 0


def _run_apply_child_region_overrides_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI child-region override workflow."""
    if args.config is None:
        parser.error("apply-child-region-overrides requires --config")
    if args.child_region_overrides is None:
        parser.error("apply-child-region-overrides requires --child-region-overrides")
    if args.overridden_config_out is None:
        parser.error("apply-child-region-overrides requires --overridden-config-out")
    result = run_child_region_override_workflow(
        load_sweep_spec(args.config),
        load_child_region_overrides(args.child_region_overrides),
        paths=ChildRegionOverrideOutputPaths(
            overridden_config_toml=args.overridden_config_out,
        ),
    )
    source_override_count = sum(
        len(source_table)
        for source_table in result.overrides.source_parameters.values()
    )
    print(f"count_override_count={len(result.overrides.counts)}")
    print(f"migration_pulse_override_count={len(result.overrides.migration_pulses)}")
    print(f"region_parameter_override_count={len(result.overrides.region_parameters)}")
    print(f"source_parameter_override_count={source_override_count}")
    print(f"overridden_config={result.overridden_config_toml_path}")
    return 0


def _run_structure_target_regions_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Run the CLI target-aligned structural-region workflow."""
    if args.config is None:
        parser.error("structure-target-regions requires --config")
    if args.targets is None:
        parser.error("structure-target-regions requires --targets")
    if args.structured_targets_out is None:
        parser.error("structure-target-regions requires --structured-targets-out")
    if args.structured_config_out is None:
        parser.error("structure-target-regions requires --structured-config-out")
    result = run_target_structure_workflow(
        load_sweep_spec(args.config),
        load_target_dataset(args.targets),
        structure_field=args.structure_field,
        structure_regions=args.structure_region or (),
        paths=TargetStructureOutputPaths(
            structured_targets_csv=args.structured_targets_out,
            structured_config_toml=args.structured_config_out,
        ),
    )
    print(f"structured_target_count={len(result.targets.observations)}")
    print(f"structured_region_count={len(result.mappings)}")
    print(f"structured_targets={result.structured_targets_csv_path}")
    print(f"structured_config={result.structured_config_toml_path}")
    for mapping in result.mappings:
        print(
            "structured_region="
            f"{mapping.original_region},"
            f"value={mapping.structure_value},"
            f"region={mapping.structured_region}"
        )
    return 0
