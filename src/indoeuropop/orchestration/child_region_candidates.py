"""Workflows for child-region structural candidate comparisons."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from indoeuropop.analysis.child_region_candidates import (
    ChildRegionCandidate,
    StructuralComparisonReference,
)
from indoeuropop.analysis.inference import ABCRejectionOptions
from indoeuropop.analysis.structural_candidates import (
    PosteriorPredictiveMetricDelta,
    posterior_predictive_metric_delta,
)
from indoeuropop.data.targets import TargetDataset
from indoeuropop.orchestration.child_region_overrides import (
    ChildRegionOverrideSet,
    apply_child_region_overrides,
)
from indoeuropop.orchestration.experiments import (
    ArtifactRole,
    ExperimentArtifact,
    ExperimentManifest,
    artifact_from_path,
    write_experiment_manifest_json,
)
from indoeuropop.orchestration.inference import (
    ABCRejectionOutputPaths,
    ABCRejectionWorkflowResult,
    run_abc_rejection_workflow,
)
from indoeuropop.orchestration.sweep_config_export import write_sweep_spec_toml
from indoeuropop.orchestration.sweeps import SweepRun, SweepSpec
from indoeuropop.reporting.child_region_candidates import (
    write_child_region_candidate_markdown,
)
from indoeuropop.reporting.reproducibility import fingerprint_sweep_collection


@dataclass(frozen=True)
class ChildRegionCandidateOutputPaths:
    """Input and output paths for a child-region candidate comparison."""

    config: Path | None = None
    targets: Path | None = None
    child_region_overrides: Path | None = None
    candidate_config_toml: Path | None = None
    baseline_posterior_predictive_csv: Path | None = None
    baseline_posterior_predictive_report_md: Path | None = None
    baseline_posterior_predictive_plot: Path | None = None
    candidate_posterior_predictive_csv: Path | None = None
    candidate_posterior_predictive_report_md: Path | None = None
    candidate_posterior_predictive_plot: Path | None = None
    reference_manifest_json: Path | None = None
    comparison_report_md: Path | None = None
    manifest_json: Path | None = None


@dataclass(frozen=True)
class ChildRegionCandidateWorkflowResult:
    """Baseline, child-region candidate, and diagnostic deltas."""

    candidate: ChildRegionCandidate
    baseline: ABCRejectionWorkflowResult
    candidate_result: ABCRejectionWorkflowResult
    metric_delta: PosteriorPredictiveMetricDelta
    reference: StructuralComparisonReference | None = None
    artifacts: tuple[ExperimentArtifact, ...] = ()
    manifest: ExperimentManifest | None = None
    candidate_config_toml_path: Path | None = None
    comparison_report_md_path: Path | None = None
    manifest_json_path: Path | None = None


def run_child_region_candidate_workflow(
    spec: SweepSpec,
    targets: TargetDataset,
    overrides: ChildRegionOverrideSet,
    *,
    candidate_name: str = "child-region-candidate",
    options: ABCRejectionOptions | None = None,
    paths: ChildRegionCandidateOutputPaths | None = None,
    interval_probability: float = 0.9,
    focus_observation_index: int | None = None,
    reference: StructuralComparisonReference | None = None,
    command: str = "programmatic-evaluate-child-region-candidate",
    manifest_name: str = "child-region-candidate",
    manifest_description: str = "Child-region structural candidate manifest",
    manifest_metadata: Mapping[str, str] | None = None,
) -> ChildRegionCandidateWorkflowResult:
    """Compare structured baseline inference against child-region overrides."""
    output_paths = ChildRegionCandidateOutputPaths() if paths is None else paths
    inference_options = ABCRejectionOptions() if options is None else options
    candidate = _candidate_from_overrides(candidate_name, overrides, output_paths)
    candidate_spec = apply_child_region_overrides(spec, overrides)
    if output_paths.candidate_config_toml is not None:
        write_sweep_spec_toml(candidate_spec, output_paths.candidate_config_toml)

    baseline = run_abc_rejection_workflow(
        spec,
        targets,
        options=inference_options,
        paths=_baseline_inference_paths(output_paths),
        interval_probability=interval_probability,
        command=f"{command}:baseline",
        manifest_name=f"{manifest_name}-baseline",
    )
    candidate_result = run_abc_rejection_workflow(
        candidate_spec,
        targets,
        options=inference_options,
        paths=_candidate_inference_paths(output_paths),
        interval_probability=interval_probability,
        command=f"{command}:candidate",
        manifest_name=f"{manifest_name}-candidate",
    )
    assert baseline.posterior_predictive is not None
    assert candidate_result.posterior_predictive is not None
    metric_delta = posterior_predictive_metric_delta(
        baseline.posterior_predictive,
        candidate_result.posterior_predictive,
        focus_observation_index=focus_observation_index,
        candidate_label=candidate.name,
    )
    if output_paths.comparison_report_md is not None:
        write_child_region_candidate_markdown(
            candidate,
            baseline.posterior_predictive,
            candidate_result.posterior_predictive,
            metric_delta,
            output_paths.comparison_report_md,
            reference=reference,
        )

    artifacts = child_region_candidate_artifacts(output_paths)
    manifest: ExperimentManifest | None = None
    if output_paths.manifest_json is not None:
        manifest = child_region_candidate_manifest(
            candidate,
            metric_delta,
            runs=_workflow_runs(baseline, candidate_result),
            artifacts=artifacts,
            command=command,
            name=manifest_name,
            description=manifest_description,
            metadata=manifest_metadata,
            reference=reference,
        )
        write_experiment_manifest_json(manifest, output_paths.manifest_json)

    return ChildRegionCandidateWorkflowResult(
        candidate=candidate,
        baseline=baseline,
        candidate_result=candidate_result,
        metric_delta=metric_delta,
        reference=reference,
        artifacts=artifacts,
        manifest=manifest,
        candidate_config_toml_path=output_paths.candidate_config_toml,
        comparison_report_md_path=output_paths.comparison_report_md,
        manifest_json_path=output_paths.manifest_json,
    )


def load_structural_comparison_reference(
    path: str | Path,
) -> StructuralComparisonReference:
    """Load structural comparison deltas from an experiment manifest JSON file."""
    reference_path = Path(path)
    payload = json.loads(reference_path.read_text(encoding="utf-8"))
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("reference manifest must include metadata")
    try:
        return StructuralComparisonReference(
            name=str(metadata.get("candidate_name") or payload["name"]),
            root_mean_squared_error_delta=float(
                metadata["root_mean_squared_error_delta"]
            ),
            coverage_rate_delta=float(metadata["coverage_rate_delta"]),
            focus_residual_delta=float(metadata["focus_residual_delta"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            "reference manifest missing structural comparison deltas"
        ) from error


def child_region_candidate_artifacts(
    paths: ChildRegionCandidateOutputPaths,
) -> tuple[ExperimentArtifact, ...]:
    """Return checksum-bearing artifacts for requested child-candidate paths."""
    artifacts: list[ExperimentArtifact] = []
    for name, role, path in (
        ("config", "config", paths.config),
        ("targets", "targets", paths.targets),
        ("child_region_overrides", "config", paths.child_region_overrides),
        ("candidate_config_toml", "config", paths.candidate_config_toml),
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
            "candidate_posterior_predictive_csv",
            "target_fit",
            paths.candidate_posterior_predictive_csv,
        ),
        (
            "candidate_posterior_predictive_report_md",
            "other",
            paths.candidate_posterior_predictive_report_md,
        ),
        (
            "candidate_posterior_predictive_plot",
            "plot",
            paths.candidate_posterior_predictive_plot,
        ),
        ("reference_manifest_json", "other", paths.reference_manifest_json),
        ("comparison_report_md", "other", paths.comparison_report_md),
    ):
        if path is not None:
            artifacts.append(artifact_from_path(name, cast(ArtifactRole, role), path))
    return tuple(artifacts)


def child_region_candidate_manifest(
    candidate: ChildRegionCandidate,
    metric_delta: PosteriorPredictiveMetricDelta,
    *,
    runs: Iterable[SweepRun],
    artifacts: Iterable[ExperimentArtifact] = (),
    command: str = "programmatic-evaluate-child-region-candidate",
    name: str = "child-region-candidate",
    description: str = "Child-region structural candidate manifest",
    metadata: Mapping[str, str] | None = None,
    reference: StructuralComparisonReference | None = None,
) -> ExperimentManifest:
    """Return a manifest for one child-region candidate comparison."""
    manifest_metadata = _manifest_metadata(candidate, metric_delta, command)
    if reference is not None:
        manifest_metadata.update(_reference_metadata(metric_delta, reference))
    manifest_metadata.update({} if metadata is None else metadata)
    return ExperimentManifest(
        name=name,
        description=description,
        artifacts=tuple(artifacts),
        fingerprints=(fingerprint_sweep_collection(tuple(runs)),),
        metadata=manifest_metadata,
    )


def _candidate_from_overrides(
    name: str,
    overrides: ChildRegionOverrideSet,
    paths: ChildRegionCandidateOutputPaths,
) -> ChildRegionCandidate:
    """Build a candidate summary from curated child-region overrides."""
    overridden_regions = set(overrides.counts)
    overridden_regions.update(pulse.region for pulse in overrides.migration_pulses)
    overridden_regions.update(overrides.region_parameters)
    overridden_regions.update(overrides.source_parameters)
    return ChildRegionCandidate(
        name=name,
        override_path=(
            ""
            if paths.child_region_overrides is None
            else str(paths.child_region_overrides)
        ),
        overridden_region_count=len(overridden_regions),
        migration_pulse_count=len(overrides.migration_pulses),
    )


def _baseline_inference_paths(
    paths: ChildRegionCandidateOutputPaths,
) -> ABCRejectionOutputPaths:
    """Return baseline inference output paths."""
    return ABCRejectionOutputPaths(
        config=paths.config,
        targets=paths.targets,
        posterior_predictive_csv=paths.baseline_posterior_predictive_csv,
        posterior_predictive_report_md=paths.baseline_posterior_predictive_report_md,
        posterior_predictive_plot=paths.baseline_posterior_predictive_plot,
    )


def _candidate_inference_paths(
    paths: ChildRegionCandidateOutputPaths,
) -> ABCRejectionOutputPaths:
    """Return child-candidate inference output paths."""
    return ABCRejectionOutputPaths(
        config=paths.candidate_config_toml,
        targets=paths.targets,
        posterior_predictive_csv=paths.candidate_posterior_predictive_csv,
        posterior_predictive_report_md=paths.candidate_posterior_predictive_report_md,
        posterior_predictive_plot=paths.candidate_posterior_predictive_plot,
    )


def _workflow_runs(
    baseline: ABCRejectionWorkflowResult,
    candidate_result: ABCRejectionWorkflowResult,
) -> tuple[SweepRun, ...]:
    """Return all scored runs represented by both workflows."""
    return tuple(scored.run for scored in baseline.inference.ranked_runs) + tuple(
        scored.run for scored in candidate_result.inference.ranked_runs
    )


def _manifest_metadata(
    candidate: ChildRegionCandidate,
    metric_delta: PosteriorPredictiveMetricDelta,
    command: str,
) -> dict[str, str]:
    """Return child-candidate manifest metadata."""
    return {
        "command": command,
        "candidate_name": candidate.name,
        "candidate_override_path": candidate.override_path,
        "candidate_overridden_region_count": str(candidate.overridden_region_count),
        "candidate_migration_pulse_count": str(candidate.migration_pulse_count),
        "coverage_rate_delta": f"{metric_delta.coverage_rate_delta:.12g}",
        "mean_absolute_error_delta": (f"{metric_delta.mean_absolute_error_delta:.12g}"),
        "root_mean_squared_error_delta": (
            f"{metric_delta.root_mean_squared_error_delta:.12g}"
        ),
        "max_abs_z_score_delta": f"{metric_delta.max_abs_z_score_delta:.12g}",
        "focus_observation_index": str(metric_delta.focus_observation_index),
        "focus_residual_delta": f"{metric_delta.focus_residual_delta:.12g}",
    }


def _reference_metadata(
    metric_delta: PosteriorPredictiveMetricDelta,
    reference: StructuralComparisonReference,
) -> dict[str, str]:
    """Return manifest metadata comparing this candidate with a reference."""
    rmse_advantage = (
        metric_delta.root_mean_squared_error_delta
        - reference.root_mean_squared_error_delta
    )
    return {
        "reference_candidate_name": reference.name,
        "reference_root_mean_squared_error_delta": (
            f"{reference.root_mean_squared_error_delta:.12g}"
        ),
        "candidate_minus_reference_root_mean_squared_error_delta": (
            f"{rmse_advantage:.12g}"
        ),
        "reference_coverage_rate_delta": f"{reference.coverage_rate_delta:.12g}",
        "reference_focus_residual_delta": f"{reference.focus_residual_delta:.12g}",
    }
