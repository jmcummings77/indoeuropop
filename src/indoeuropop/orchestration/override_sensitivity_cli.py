"""CLI handlers for child-override sensitivity sweeps."""

from __future__ import annotations

import argparse
from pathlib import Path

from indoeuropop.data.targets import load_target_dataset
from indoeuropop.orchestration.child_region_overrides import load_child_region_overrides
from indoeuropop.orchestration.override_sensitivity import (
    OverrideSensitivityOutputPaths,
    OverrideSensitivityWorkflowResult,
    run_child_override_sensitivity_workflow,
)
from indoeuropop.reporting.override_sensitivity import override_sensitivity_markdown
from indoeuropop.simulation.config import load_sweep_spec

OVERRIDE_SENSITIVITY_COMMANDS = (
    "sweep-child-overrides",
    "sweep-child-override-interactions",
)


def add_override_sensitivity_arguments(parser: argparse.ArgumentParser) -> None:
    """Add child-override sensitivity command arguments."""
    parser.add_argument(
        "--override-sensitivity-csv",
        type=Path,
        help="optional output path for ranked child-override sensitivity rows",
    )
    parser.add_argument(
        "--override-sensitivity-report-md",
        type=Path,
        help="optional output path for child-override sensitivity Markdown",
    )
    parser.add_argument(
        "--count-factor",
        action="append",
        type=float,
        help="count scaling factor for one-factor override sensitivity",
    )
    parser.add_argument(
        "--pulse-rate-factor",
        action="append",
        type=float,
        help="migration pulse annual-rate factor for override sensitivity",
    )
    parser.add_argument(
        "--pulse-window-shift",
        action="append",
        type=float,
        help="BCE year shift for migration pulse windows",
    )
    parser.add_argument(
        "--reproductive-multiplier-factor",
        action="append",
        type=float,
        help="source reproductive-multiplier factor for override sensitivity",
    )
    parser.add_argument(
        "--interaction-region",
        action="append",
        help="child region to include in count-by-reproduction interaction grids",
    )


def run_override_sensitivity_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int | None:
    """Run child-override sensitivity commands or return `None`."""
    if args.command not in OVERRIDE_SENSITIVITY_COMMANDS:
        return None
    if args.config is None:
        parser.error(f"{args.command} requires --config")
    if args.targets is None:
        parser.error(f"{args.command} requires --targets")
    if args.child_region_overrides is None:
        parser.error(f"{args.command} requires --child-region-overrides")

    interaction_mode = args.command == "sweep-child-override-interactions"
    result = run_child_override_sensitivity_workflow(
        load_sweep_spec(args.config),
        load_target_dataset(args.targets),
        load_child_region_overrides(args.child_region_overrides),
        holdout_field=args.validation_field,
        holdout_values=args.validation_value or None,
        priority_values=args.priority_validation_value or (),
        protected_values=args.protected_validation_value or (),
        tolerance=args.refinement_tolerance,
        fit_metric=args.fit_metric,
        count_factors=args.count_factor or _default_count_factors(interaction_mode),
        pulse_rate_factors=args.pulse_rate_factor or (0.85, 1.15),
        pulse_window_shifts=args.pulse_window_shift or (-50.0, 50.0),
        reproductive_multiplier_factors=(
            args.reproductive_multiplier_factor
            or _default_reproductive_factors(interaction_mode)
        ),
        candidate_mode=(
            "count_reproduction_interaction" if interaction_mode else "one_factor"
        ),
        interaction_regions=args.interaction_region or (),
        paths=OverrideSensitivityOutputPaths(
            config=args.config,
            targets=args.targets,
            child_region_overrides=args.child_region_overrides,
            sensitivity_summary_csv=args.override_sensitivity_csv,
            sensitivity_report_md=args.override_sensitivity_report_md,
            manifest_json=args.manifest_json,
        ),
        command=args.command,
        manifest_name="cli-child-override-sensitivity",
        manifest_description="CLI child-override sensitivity manifest",
    )
    _print_sensitivity_result(result, args)
    return 0


def _print_sensitivity_result(
    result: OverrideSensitivityWorkflowResult,
    args: argparse.Namespace,
) -> None:
    """Print a compact CLI summary for a sensitivity result."""
    if result.sensitivity_report_md_path is None:
        print(
            override_sensitivity_markdown(
                result.scenarios,
                result.baseline_folds,
                tolerance=args.refinement_tolerance,
            ),
            end="",
        )
    else:
        print(f"override_sensitivity_report={result.sensitivity_report_md_path}")
    if result.sensitivity_summary_csv_path is not None:
        print(f"override_sensitivity_csv={result.sensitivity_summary_csv_path}")
    if result.manifest_json_path is not None:
        print(f"manifest_json={result.manifest_json_path}")
    best = result.best_scenario(tolerance=args.refinement_tolerance)
    print(f"override_sensitivity_candidate_count={len(result.scenarios)}")
    print(f"override_sensitivity_best_candidate={best.name}")
    print(
        "override_sensitivity_best_priority_delta="
        f"{best.priority_mean_delta(result.baseline_folds):.6f}"
    )
    print(
        "override_sensitivity_best_protected_delta="
        f"{best.protected_max_delta(result.baseline_folds):.6f}"
    )
    accepted_text = str(
        best.accepted(result.baseline_folds, tolerance=args.refinement_tolerance)
    ).lower()
    print("override_sensitivity_best_accepted=" f"{accepted_text}")


def _default_count_factors(interaction_mode: bool) -> tuple[float, ...]:
    """Return default count factors for one-factor or interaction mode."""
    return (0.9, 1.0, 1.1) if interaction_mode else (0.9, 1.1)


def _default_reproductive_factors(interaction_mode: bool) -> tuple[float, ...]:
    """Return default reproductive factors for one-factor or interaction mode."""
    return (0.9, 0.95, 1.0, 1.05) if interaction_mode else (0.95, 1.05)
