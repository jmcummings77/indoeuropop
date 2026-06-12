"""CLI handler for the standard real-pipeline refresh workflow."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import cast

from indoeuropop.analysis.inference import ABCRejectionOptions
from indoeuropop.analysis.structural_head_to_head import StructuredPulseCandidate
from indoeuropop.orchestration.real_pipeline_refresh import (
    DEFAULT_ACCEPTED_TARGETS,
    DEFAULT_BASE_CONFIG,
    DEFAULT_CHILD_CANDIDATE_NAME,
    DEFAULT_CHILD_OVERRIDES,
    DEFAULT_FIT_METRIC,
    DEFAULT_FOCUS_OBSERVATION_INDEX,
    DEFAULT_STRUCTURED_CONFIG,
    DEFAULT_STRUCTURED_TARGETS,
    RealPipelineRefreshPaths,
    RealPipelineRefreshResult,
    default_structured_pulse_candidate,
    run_real_pipeline_refresh_workflow,
)
from indoeuropop.reporting.readiness_models import DEFAULT_DATA_SOURCE_CATALOG

REAL_PIPELINE_REFRESH_COMMANDS = ("refresh-real-pipeline",)


def add_real_pipeline_refresh_arguments(parser: argparse.ArgumentParser) -> None:
    """Register arguments specific to the real-pipeline refresh command."""
    parser.add_argument(
        "--refresh-fit-metric",
        default=DEFAULT_FIT_METRIC,
        help="fit metric used by refresh-real-pipeline when --fit-metric is omitted",
    )


def run_real_pipeline_refresh_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> int | None:
    """Run the real-pipeline refresh command or return `None`."""
    if args.command != "refresh-real-pipeline":
        return None
    result = run_real_pipeline_refresh_workflow(
        project_root=args.project_root,
        paths=_refresh_paths(args),
        structure_field=args.structure_field,
        structure_regions=args.structure_region or ("central_europe",),
        structured_pulse_candidate=_structured_pulse_candidate(args),
        child_candidate_name=_child_candidate_name(args),
        options=_abc_options(args),
        interval_probability=args.posterior_predictive_interval_probability,
        focus_observation_index=_focus_observation_index(args),
        readiness_curation_decision_files=args.curation_decision_file,
        readiness_data_source_catalog=(
            DEFAULT_DATA_SOURCE_CATALOG
            if args.data_sources is None
            else args.data_sources
        ),
        require_curation_artifacts=True,
    )
    _print_refresh_result(result)
    return 0 if result.ready else 1


def _refresh_paths(args: argparse.Namespace) -> RealPipelineRefreshPaths:
    """Return refresh paths from CLI arguments and standard defaults."""
    return RealPipelineRefreshPaths(
        base_config=_path_arg(args.config, DEFAULT_BASE_CONFIG),
        accepted_targets=_path_arg(args.targets, DEFAULT_ACCEPTED_TARGETS),
        structured_targets=_path_arg(
            args.structured_targets_out, DEFAULT_STRUCTURED_TARGETS
        ),
        structured_config=_path_arg(
            args.structured_config_out, DEFAULT_STRUCTURED_CONFIG
        ),
        child_region_overrides=_path_arg(
            args.child_region_overrides, DEFAULT_CHILD_OVERRIDES
        ),
        structured_pulse_config=_path_arg(
            args.structured_pulse_config_out,
            RealPipelineRefreshPaths.structured_pulse_config,
        ),
        child_candidate_config=_path_arg(
            args.child_candidate_config_out,
            RealPipelineRefreshPaths.child_candidate_config,
        ),
        baseline_posterior_predictive_report=_path_arg(
            args.posterior_predictive_report_md,
            RealPipelineRefreshPaths.baseline_posterior_predictive_report,
        ),
        baseline_posterior_predictive_plot=_path_arg(
            args.posterior_predictive_plot,
            RealPipelineRefreshPaths.baseline_posterior_predictive_plot,
        ),
        structured_pulse_posterior_predictive_report=_path_arg(
            args.structured_pulse_posterior_predictive_report_md,
            RealPipelineRefreshPaths.structured_pulse_posterior_predictive_report,
        ),
        structured_pulse_posterior_predictive_plot=_path_arg(
            args.structured_pulse_posterior_predictive_plot,
            RealPipelineRefreshPaths.structured_pulse_posterior_predictive_plot,
        ),
        child_posterior_predictive_report=_path_arg(
            args.child_posterior_predictive_report_md,
            RealPipelineRefreshPaths.child_posterior_predictive_report,
        ),
        child_posterior_predictive_plot=_path_arg(
            args.child_posterior_predictive_plot,
            RealPipelineRefreshPaths.child_posterior_predictive_plot,
        ),
        head_to_head_report=_path_arg(
            args.head_to_head_report_md,
            RealPipelineRefreshPaths.head_to_head_report,
        ),
        head_to_head_manifest=_path_arg(
            args.manifest_json,
            RealPipelineRefreshPaths.head_to_head_manifest,
        ),
        readiness_report=_path_arg(
            args.readiness_report_md,
            RealPipelineRefreshPaths.readiness_report,
        ),
    )


def _path_arg(value: Path | None, default: Path) -> Path:
    """Return a command path value or its refresh default."""
    return default if value is None else value


def _structured_pulse_candidate(args: argparse.Namespace) -> StructuredPulseCandidate:
    """Return the refresh broad-pulse candidate from CLI arguments."""
    default = default_structured_pulse_candidate()
    return StructuredPulseCandidate(
        name=(
            default.name
            if args.structured_pulse_candidate_name == "structured-broad-pulse"
            else args.structured_pulse_candidate_name
        ),
        region_prefix=args.structured_pulse_region_prefix or default.region_prefix,
        start_bce=args.structured_pulse_start_bce or default.start_bce,
        end_bce=args.structured_pulse_end_bce or default.end_bce,
        annual_rate=args.structured_pulse_annual_rate or default.annual_rate,
    )


def _child_candidate_name(args: argparse.Namespace) -> str:
    """Return the refresh child-candidate label."""
    if args.child_region_candidate_name == "child-region-candidate":
        return DEFAULT_CHILD_CANDIDATE_NAME
    return cast(str, args.child_region_candidate_name)


def _abc_options(args: argparse.Namespace) -> ABCRejectionOptions:
    """Return ABC options with refresh-friendly defaults."""
    acceptance_count = args.acceptance_count
    if acceptance_count is None and args.acceptance_threshold is None:
        acceptance_count = 6
    return ABCRejectionOptions(
        fit_metric=_fit_metric(args),
        acceptance_quantile=args.acceptance_quantile,
        acceptance_count=acceptance_count,
        acceptance_threshold=args.acceptance_threshold,
    )


def _fit_metric(args: argparse.Namespace) -> str:
    """Return the refresh fit metric while preserving existing CLI defaults."""
    if args.fit_metric == "chi_square":
        return cast(str, args.refresh_fit_metric)
    return cast(str, args.fit_metric)


def _focus_observation_index(args: argparse.Namespace) -> int | None:
    """Return the refresh focus target index."""
    if args.focus_observation_index is None:
        return DEFAULT_FOCUS_OBSERVATION_INDEX
    return cast(int, args.focus_observation_index)


def _print_refresh_result(result: RealPipelineRefreshResult) -> None:
    """Print compact machine-readable refresh summary lines."""
    baseline = result.head_to_head.baseline.posterior_predictive
    structured_pulse = result.head_to_head.structured_pulse_result.posterior_predictive
    child = result.head_to_head.child_result.posterior_predictive
    assert baseline is not None
    assert structured_pulse is not None
    assert child is not None
    print("real_pipeline_refresh=true")
    print(f"accepted_target_count={len(result.target_structure.targets.observations)}")
    print(f"structured_region_count={len(result.target_structure.mappings)}")
    print(f"structured_targets={result.target_structure.structured_targets_csv_path}")
    print(f"structured_config={result.target_structure.structured_config_toml_path}")
    print(
        f"structured_pulse_candidate={result.head_to_head.structured_pulse_candidate.name}"
    )
    print(f"child_region_candidate={result.head_to_head.child_candidate.name}")
    print(f"baseline_posterior_predictive_rmse={baseline.root_mean_squared_error:.6f}")
    print(
        "structured_pulse_posterior_predictive_rmse="
        f"{structured_pulse.root_mean_squared_error:.6f}"
    )
    print(f"child_posterior_predictive_rmse={child.root_mean_squared_error:.6f}")
    print(
        "child_minus_structured_pulse_rmse_delta="
        f"{result.head_to_head.child_minus_structured_pulse_rmse_delta:.6f}"
    )
    print(f"head_to_head_report_md={result.head_to_head.head_to_head_report_md_path}")
    print(f"manifest_json={result.head_to_head.manifest_json_path}")
    print(f"readiness_report={result.readiness_report_md_path}")
    print(f"pipeline_ready={str(result.ready).lower()}")
    print(f"readiness_issue_count={len(result.readiness.issues)}")
