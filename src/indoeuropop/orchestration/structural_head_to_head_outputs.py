"""Output artifacts for same-baseline structural comparisons."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from indoeuropop.analysis.child_region_candidates import ChildRegionCandidate
from indoeuropop.analysis.structural_candidates import PosteriorPredictiveMetricDelta
from indoeuropop.analysis.structural_head_to_head import StructuredPulseCandidate
from indoeuropop.orchestration.experiments import (
    ArtifactRole,
    ExperimentArtifact,
    ExperimentManifest,
    artifact_from_path,
)
from indoeuropop.orchestration.inference import ABCRejectionOutputPaths
from indoeuropop.orchestration.sweeps import SweepRun
from indoeuropop.reporting.reproducibility import fingerprint_sweep_collection


@dataclass(frozen=True)
class StructuredHeadToHeadOutputPaths:
    """Input and output paths for a same-baseline structural comparison."""

    config: Path | None = None
    targets: Path | None = None
    child_region_overrides: Path | None = None
    structured_pulse_config_toml: Path | None = None
    child_candidate_config_toml: Path | None = None
    baseline_posterior_predictive_csv: Path | None = None
    baseline_posterior_predictive_report_md: Path | None = None
    baseline_posterior_predictive_plot: Path | None = None
    structured_pulse_posterior_predictive_csv: Path | None = None
    structured_pulse_posterior_predictive_report_md: Path | None = None
    structured_pulse_posterior_predictive_plot: Path | None = None
    child_posterior_predictive_csv: Path | None = None
    child_posterior_predictive_report_md: Path | None = None
    child_posterior_predictive_plot: Path | None = None
    head_to_head_report_md: Path | None = None
    manifest_json: Path | None = None


def structured_head_to_head_artifacts(
    paths: StructuredHeadToHeadOutputPaths,
) -> tuple[ExperimentArtifact, ...]:
    """Return checksum-bearing artifacts for requested head-to-head paths."""
    artifacts: list[ExperimentArtifact] = []
    for name, role, path in _artifact_specs(paths):
        if path is not None:
            artifacts.append(artifact_from_path(name, cast(ArtifactRole, role), path))
    return tuple(artifacts)


def structured_head_to_head_manifest(
    structured_pulse_candidate: StructuredPulseCandidate,
    structured_pulse_region_count: int,
    child_candidate: ChildRegionCandidate,
    structured_pulse_delta: PosteriorPredictiveMetricDelta,
    child_delta: PosteriorPredictiveMetricDelta,
    *,
    runs: Iterable[SweepRun],
    artifacts: Iterable[ExperimentArtifact] = (),
    command: str = "programmatic-compare-structured-candidates",
    name: str = "structured-candidate-head-to-head",
    description: str = "Same-baseline structural comparison manifest",
    metadata: Mapping[str, str] | None = None,
) -> ExperimentManifest:
    """Return a manifest for one same-baseline structural comparison."""
    manifest_metadata = _manifest_metadata(
        structured_pulse_candidate,
        structured_pulse_region_count,
        child_candidate,
        structured_pulse_delta,
        child_delta,
        command,
    )
    manifest_metadata.update({} if metadata is None else metadata)
    return ExperimentManifest(
        name=name,
        description=description,
        artifacts=tuple(artifacts),
        fingerprints=(fingerprint_sweep_collection(tuple(runs)),),
        metadata=manifest_metadata,
    )


def head_to_head_baseline_paths(
    paths: StructuredHeadToHeadOutputPaths,
) -> ABCRejectionOutputPaths:
    """Return baseline inference output paths."""
    return ABCRejectionOutputPaths(
        config=paths.config,
        targets=paths.targets,
        posterior_predictive_csv=paths.baseline_posterior_predictive_csv,
        posterior_predictive_report_md=paths.baseline_posterior_predictive_report_md,
        posterior_predictive_plot=paths.baseline_posterior_predictive_plot,
    )


def head_to_head_structured_pulse_paths(
    paths: StructuredHeadToHeadOutputPaths,
) -> ABCRejectionOutputPaths:
    """Return structured-pulse inference output paths."""
    return ABCRejectionOutputPaths(
        config=paths.structured_pulse_config_toml,
        targets=paths.targets,
        posterior_predictive_csv=paths.structured_pulse_posterior_predictive_csv,
        posterior_predictive_report_md=(
            paths.structured_pulse_posterior_predictive_report_md
        ),
        posterior_predictive_plot=paths.structured_pulse_posterior_predictive_plot,
    )


def head_to_head_child_paths(
    paths: StructuredHeadToHeadOutputPaths,
) -> ABCRejectionOutputPaths:
    """Return child-candidate inference output paths."""
    return ABCRejectionOutputPaths(
        config=paths.child_candidate_config_toml,
        targets=paths.targets,
        posterior_predictive_csv=paths.child_posterior_predictive_csv,
        posterior_predictive_report_md=paths.child_posterior_predictive_report_md,
        posterior_predictive_plot=paths.child_posterior_predictive_plot,
    )


def _artifact_specs(
    paths: StructuredHeadToHeadOutputPaths,
) -> tuple[tuple[str, str, Path | None], ...]:
    """Return artifact names, roles, and paths for requested outputs."""
    return (
        ("config", "config", paths.config),
        ("targets", "targets", paths.targets),
        ("child_region_overrides", "config", paths.child_region_overrides),
        ("structured_pulse_config_toml", "config", paths.structured_pulse_config_toml),
        ("child_candidate_config_toml", "config", paths.child_candidate_config_toml),
        (
            "baseline_posterior_predictive_csv",
            "target_fit",
            paths.baseline_posterior_predictive_csv,
        ),
        (
            "baseline_posterior_predictive_report_md",
            "other",
            paths.baseline_posterior_predictive_report_md,
        ),
        (
            "baseline_posterior_predictive_plot",
            "plot",
            paths.baseline_posterior_predictive_plot,
        ),
        (
            "structured_pulse_posterior_predictive_csv",
            "target_fit",
            paths.structured_pulse_posterior_predictive_csv,
        ),
        (
            "structured_pulse_posterior_predictive_report_md",
            "other",
            paths.structured_pulse_posterior_predictive_report_md,
        ),
        (
            "structured_pulse_posterior_predictive_plot",
            "plot",
            paths.structured_pulse_posterior_predictive_plot,
        ),
        (
            "child_posterior_predictive_csv",
            "target_fit",
            paths.child_posterior_predictive_csv,
        ),
        (
            "child_posterior_predictive_report_md",
            "other",
            paths.child_posterior_predictive_report_md,
        ),
        (
            "child_posterior_predictive_plot",
            "plot",
            paths.child_posterior_predictive_plot,
        ),
        ("head_to_head_report_md", "other", paths.head_to_head_report_md),
    )


def _manifest_metadata(
    pulse_candidate: StructuredPulseCandidate,
    pulse_region_count: int,
    child_candidate: ChildRegionCandidate,
    pulse_delta: PosteriorPredictiveMetricDelta,
    child_delta: PosteriorPredictiveMetricDelta,
    command: str,
) -> dict[str, str]:
    """Return manifest metadata for a same-baseline comparison."""
    rmse_delta_gap = (
        child_delta.root_mean_squared_error_delta
        - pulse_delta.root_mean_squared_error_delta
    )
    return {
        "command": command,
        "structured_pulse_candidate_name": pulse_candidate.name,
        "structured_pulse_region_prefix": pulse_candidate.region_prefix,
        "structured_pulse_region_count": str(pulse_region_count),
        "structured_pulse_start_bce": f"{pulse_candidate.start_bce:.12g}",
        "structured_pulse_end_bce": f"{pulse_candidate.end_bce:.12g}",
        "structured_pulse_annual_rate": f"{pulse_candidate.annual_rate:.12g}",
        "child_candidate_name": child_candidate.name,
        "child_candidate_override_path": child_candidate.override_path,
        "child_candidate_overridden_region_count": (
            str(child_candidate.overridden_region_count)
        ),
        "child_candidate_migration_pulse_count": (
            str(child_candidate.migration_pulse_count)
        ),
        "structured_pulse_root_mean_squared_error_delta": (
            f"{pulse_delta.root_mean_squared_error_delta:.12g}"
        ),
        "child_root_mean_squared_error_delta": (
            f"{child_delta.root_mean_squared_error_delta:.12g}"
        ),
        "child_minus_structured_pulse_root_mean_squared_error_delta": (
            f"{rmse_delta_gap:.12g}"
        ),
        "structured_pulse_coverage_rate_delta": (
            f"{pulse_delta.coverage_rate_delta:.12g}"
        ),
        "child_coverage_rate_delta": f"{child_delta.coverage_rate_delta:.12g}",
        "structured_pulse_focus_residual_delta": (
            f"{pulse_delta.focus_residual_delta:.12g}"
        ),
        "child_focus_residual_delta": f"{child_delta.focus_residual_delta:.12g}",
        "focus_observation_index": str(child_delta.focus_observation_index),
    }
