"""CLI handlers for targeted model-structure candidate workflows."""

from __future__ import annotations

import argparse
from pathlib import Path

from indoeuropop.analysis.inference import ABCRejectionOptions
from indoeuropop.analysis.structural_candidates import MigrationPulseCandidate
from indoeuropop.data.targets import load_target_dataset
from indoeuropop.orchestration.child_region_candidates import (
    ChildRegionCandidateOutputPaths,
    ChildRegionCandidateWorkflowResult,
    load_structural_comparison_reference,
    run_child_region_candidate_workflow,
)
from indoeuropop.orchestration.child_region_overrides import (
    load_child_region_overrides,
)
from indoeuropop.orchestration.structural_candidates import (
    MigrationPulseCandidateOutputPaths,
    MigrationPulseCandidateWorkflowResult,
    run_migration_pulse_candidate_workflow,
)
from indoeuropop.simulation.config import load_sweep_spec

STRUCTURAL_CANDIDATE_COMMANDS = (
    "evaluate-child-region-candidate",
    "evaluate-migration-pulse-candidate",
)


def add_structural_candidate_arguments(parser: argparse.ArgumentParser) -> None:
    """Register structural-candidate command arguments on the shared parser."""
    parser.add_argument(
        "--pulse-candidate-name",
        default="migration-pulse-candidate",
        help="label for an added migration-pulse candidate",
    )
    parser.add_argument(
        "--pulse-region",
        help="modeled region receiving the additional migration pulse",
    )
    parser.add_argument(
        "--pulse-start-bce",
        type=float,
        help="BCE start date for the additional migration pulse",
    )
    parser.add_argument(
        "--pulse-end-bce",
        type=float,
        help="BCE end date for the additional migration pulse",
    )
    parser.add_argument(
        "--pulse-annual-rate",
        type=float,
        help="annual additive migration rate for the additional pulse",
    )
    parser.add_argument(
        "--candidate-config-out",
        type=Path,
        help="optional output path for the candidate sweep config",
    )
    parser.add_argument(
        "--candidate-posterior-predictive-csv",
        type=Path,
        help="optional output path for candidate posterior predictive rows",
    )
    parser.add_argument(
        "--candidate-posterior-predictive-report-md",
        type=Path,
        help="optional output path for candidate posterior predictive report",
    )
    parser.add_argument(
        "--candidate-posterior-predictive-plot",
        type=Path,
        help="optional output path for candidate posterior predictive plot",
    )
    parser.add_argument(
        "--candidate-comparison-report-md",
        type=Path,
        help="optional output path for baseline-vs-candidate Markdown report",
    )
    parser.add_argument(
        "--child-region-candidate-name",
        default="child-region-candidate",
        help="label for a child-region override candidate",
    )
    parser.add_argument(
        "--reference-comparison-manifest",
        type=Path,
        help="optional manifest JSON from another structural candidate comparison",
    )
    parser.add_argument(
        "--focus-observation-index",
        type=int,
        help="target observation index for residual-delta emphasis",
    )


def run_structural_candidate_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int | None:
    """Run structural-candidate commands or return `None` for unrelated commands."""
    if args.command == "evaluate-child-region-candidate":
        return _run_evaluate_child_region_candidate(args, parser)
    if args.command == "evaluate-migration-pulse-candidate":
        return _run_evaluate_migration_pulse_candidate(args, parser)
    return None


def _run_evaluate_child_region_candidate(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    """Run a child-region structural candidate comparison."""
    if args.config is None:
        parser.error("evaluate-child-region-candidate requires --config")
    if args.targets is None:
        parser.error("evaluate-child-region-candidate requires --targets")
    if args.child_region_overrides is None:
        parser.error(
            "evaluate-child-region-candidate requires --child-region-overrides"
        )
    reference = (
        load_structural_comparison_reference(args.reference_comparison_manifest)
        if args.reference_comparison_manifest is not None
        else None
    )
    result = run_child_region_candidate_workflow(
        load_sweep_spec(args.config),
        load_target_dataset(args.targets),
        load_child_region_overrides(args.child_region_overrides),
        candidate_name=args.child_region_candidate_name,
        options=_abc_options(args),
        paths=ChildRegionCandidateOutputPaths(
            config=args.config,
            targets=args.targets,
            child_region_overrides=args.child_region_overrides,
            candidate_config_toml=args.candidate_config_out,
            baseline_posterior_predictive_csv=args.posterior_predictive_csv,
            baseline_posterior_predictive_report_md=(
                args.posterior_predictive_report_md
            ),
            baseline_posterior_predictive_plot=args.posterior_predictive_plot,
            candidate_posterior_predictive_csv=(
                args.candidate_posterior_predictive_csv
            ),
            candidate_posterior_predictive_report_md=(
                args.candidate_posterior_predictive_report_md
            ),
            candidate_posterior_predictive_plot=(
                args.candidate_posterior_predictive_plot
            ),
            reference_manifest_json=args.reference_comparison_manifest,
            comparison_report_md=args.candidate_comparison_report_md,
            manifest_json=args.manifest_json,
        ),
        interval_probability=args.posterior_predictive_interval_probability,
        focus_observation_index=args.focus_observation_index,
        reference=reference,
        command=args.command,
        manifest_name="cli-child-region-candidate",
    )
    _print_child_region_candidate_result(result)
    return 0


def _run_evaluate_migration_pulse_candidate(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int:
    """Run a migration-pulse structural candidate comparison."""
    if args.config is None:
        parser.error("evaluate-migration-pulse-candidate requires --config")
    if args.targets is None:
        parser.error("evaluate-migration-pulse-candidate requires --targets")
    for argument_name in ("pulse_region", "pulse_start_bce", "pulse_end_bce"):
        if getattr(args, argument_name) is None:
            parser.error(
                "evaluate-migration-pulse-candidate requires "
                f"--{argument_name.replace('_', '-')}"
            )
    if args.pulse_annual_rate is None:
        parser.error("evaluate-migration-pulse-candidate requires --pulse-annual-rate")

    result = run_migration_pulse_candidate_workflow(
        load_sweep_spec(args.config),
        load_target_dataset(args.targets),
        MigrationPulseCandidate(
            name=args.pulse_candidate_name,
            region=args.pulse_region,
            start_bce=args.pulse_start_bce,
            end_bce=args.pulse_end_bce,
            annual_rate=args.pulse_annual_rate,
        ),
        options=_abc_options(args),
        paths=MigrationPulseCandidateOutputPaths(
            config=args.config,
            targets=args.targets,
            candidate_config_toml=args.candidate_config_out,
            baseline_posterior_predictive_csv=args.posterior_predictive_csv,
            baseline_posterior_predictive_report_md=(
                args.posterior_predictive_report_md
            ),
            baseline_posterior_predictive_plot=args.posterior_predictive_plot,
            candidate_posterior_predictive_csv=(
                args.candidate_posterior_predictive_csv
            ),
            candidate_posterior_predictive_report_md=(
                args.candidate_posterior_predictive_report_md
            ),
            candidate_posterior_predictive_plot=(
                args.candidate_posterior_predictive_plot
            ),
            comparison_report_md=args.candidate_comparison_report_md,
            manifest_json=args.manifest_json,
        ),
        interval_probability=args.posterior_predictive_interval_probability,
        focus_observation_index=args.focus_observation_index,
        command=args.command,
        manifest_name="cli-migration-pulse-candidate",
    )
    _print_migration_pulse_candidate_result(result)
    return 0


def _abc_options(args: argparse.Namespace) -> ABCRejectionOptions:
    """Return ABC rejection options shared by structural candidate commands."""
    return ABCRejectionOptions(
        fit_metric=args.fit_metric,
        acceptance_quantile=args.acceptance_quantile,
        acceptance_count=args.acceptance_count,
        acceptance_threshold=args.acceptance_threshold,
    )


def _print_child_region_candidate_result(
    result: ChildRegionCandidateWorkflowResult,
) -> None:
    """Print compact CLI summary lines for a child-region candidate result."""
    delta = result.metric_delta
    baseline = result.baseline.posterior_predictive
    candidate = result.candidate_result.posterior_predictive
    assert baseline is not None
    assert candidate is not None
    print(f"child_region_candidate={result.candidate.name}")
    print(f"candidate_override_path={result.candidate.override_path}")
    print(
        f"candidate_overridden_region_count={result.candidate.overridden_region_count}"
    )
    print(f"candidate_migration_pulse_count={result.candidate.migration_pulse_count}")
    print(f"baseline_posterior_predictive_rmse={baseline.root_mean_squared_error:.6f}")
    print(
        f"candidate_posterior_predictive_rmse="
        f"{candidate.root_mean_squared_error:.6f}"
    )
    print(f"candidate_rmse_delta={delta.root_mean_squared_error_delta:.6f}")
    print(f"candidate_coverage_delta={delta.coverage_rate_delta:.6f}")
    print(f"focus_observation_index={delta.focus_observation_index}")
    print(f"focus_residual_delta={delta.focus_residual_delta:.6f}")
    if result.reference is not None:
        rmse_advantage = (
            delta.root_mean_squared_error_delta
            - result.reference.root_mean_squared_error_delta
        )
        print(f"reference_candidate={result.reference.name}")
        print("candidate_minus_reference_rmse_delta=" f"{rmse_advantage:.6f}")
    if result.candidate_config_toml_path is not None:
        print(f"candidate_config={result.candidate_config_toml_path}")
    if result.baseline.posterior_predictive_report_md_path is not None:
        print(
            "baseline_posterior_predictive_report_md="
            f"{result.baseline.posterior_predictive_report_md_path}"
        )
    if result.candidate_result.posterior_predictive_report_md_path is not None:
        print(
            "candidate_posterior_predictive_report_md="
            f"{result.candidate_result.posterior_predictive_report_md_path}"
        )
    if result.comparison_report_md_path is not None:
        print(f"candidate_comparison_report_md={result.comparison_report_md_path}")
    if result.manifest_json_path is not None:
        print(f"manifest_json={result.manifest_json_path}")


def _print_migration_pulse_candidate_result(
    result: MigrationPulseCandidateWorkflowResult,
) -> None:
    """Print compact CLI summary lines for a structural candidate result."""
    delta = result.metric_delta
    baseline = result.baseline.posterior_predictive
    candidate = result.candidate_result.posterior_predictive
    assert baseline is not None
    assert candidate is not None
    print(f"migration_pulse_candidate={result.candidate.name}")
    print(f"candidate_region={result.candidate.region}")
    print(f"candidate_start_bce={result.candidate.start_bce:.6f}")
    print(f"candidate_end_bce={result.candidate.end_bce:.6f}")
    print(f"candidate_annual_rate={result.candidate.annual_rate:.12g}")
    print(f"baseline_posterior_predictive_rmse={baseline.root_mean_squared_error:.6f}")
    print(
        f"candidate_posterior_predictive_rmse="
        f"{candidate.root_mean_squared_error:.6f}"
    )
    print(f"candidate_rmse_delta={delta.root_mean_squared_error_delta:.6f}")
    print(f"candidate_coverage_delta={delta.coverage_rate_delta:.6f}")
    print(f"focus_observation_index={delta.focus_observation_index}")
    print(f"focus_residual_delta={delta.focus_residual_delta:.6f}")
    if result.candidate_config_toml_path is not None:
        print(f"candidate_config={result.candidate_config_toml_path}")
    if result.baseline.posterior_predictive_report_md_path is not None:
        print(
            "baseline_posterior_predictive_report_md="
            f"{result.baseline.posterior_predictive_report_md_path}"
        )
    if result.candidate_result.posterior_predictive_report_md_path is not None:
        print(
            "candidate_posterior_predictive_report_md="
            f"{result.candidate_result.posterior_predictive_report_md_path}"
        )
    if result.comparison_report_md_path is not None:
        print(f"candidate_comparison_report_md={result.comparison_report_md_path}")
    if result.manifest_json_path is not None:
        print(f"manifest_json={result.manifest_json_path}")
