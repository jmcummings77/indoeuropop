"""Workflow helpers for targeted model-structure candidate comparisons."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from indoeuropop.analysis.inference import ABCRejectionOptions
from indoeuropop.analysis.structural_candidates import (
    MigrationPulseCandidate,
    PosteriorPredictiveMetricDelta,
    apply_migration_pulse_candidate,
    posterior_predictive_metric_delta,
)
from indoeuropop.data.targets import TargetDataset
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
from indoeuropop.reporting.reproducibility import fingerprint_sweep_collection
from indoeuropop.reporting.structural_candidates import (
    write_migration_pulse_candidate_markdown,
)


@dataclass(frozen=True)
class MigrationPulseCandidateOutputPaths:
    """Input and output paths for a migration-pulse candidate comparison."""

    config: Path | None = None
    targets: Path | None = None
    candidate_config_toml: Path | None = None
    baseline_posterior_predictive_csv: Path | None = None
    baseline_posterior_predictive_report_md: Path | None = None
    baseline_posterior_predictive_plot: Path | None = None
    candidate_posterior_predictive_csv: Path | None = None
    candidate_posterior_predictive_report_md: Path | None = None
    candidate_posterior_predictive_plot: Path | None = None
    comparison_report_md: Path | None = None
    manifest_json: Path | None = None


@dataclass(frozen=True)
class MigrationPulseCandidateWorkflowResult:
    """Baseline, candidate, and metric deltas for one structural comparison."""

    candidate: MigrationPulseCandidate
    baseline: ABCRejectionWorkflowResult
    candidate_result: ABCRejectionWorkflowResult
    metric_delta: PosteriorPredictiveMetricDelta
    artifacts: tuple[ExperimentArtifact, ...] = ()
    manifest: ExperimentManifest | None = None
    candidate_config_toml_path: Path | None = None
    comparison_report_md_path: Path | None = None
    manifest_json_path: Path | None = None


def run_migration_pulse_candidate_workflow(
    spec: SweepSpec,
    targets: TargetDataset,
    candidate: MigrationPulseCandidate,
    *,
    options: ABCRejectionOptions | None = None,
    paths: MigrationPulseCandidateOutputPaths | None = None,
    interval_probability: float = 0.9,
    focus_observation_index: int | None = None,
    command: str = "programmatic-evaluate-migration-pulse-candidate",
    manifest_name: str = "migration-pulse-candidate",
    manifest_description: str = "Migration-pulse structural candidate manifest",
    manifest_metadata: Mapping[str, str] | None = None,
) -> MigrationPulseCandidateWorkflowResult:
    """Compare baseline inference against an added migration-pulse candidate."""
    output_paths = MigrationPulseCandidateOutputPaths() if paths is None else paths
    inference_options = ABCRejectionOptions() if options is None else options
    candidate_spec = apply_migration_pulse_candidate(spec, candidate)
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
        write_migration_pulse_candidate_markdown(
            candidate,
            baseline.posterior_predictive,
            candidate_result.posterior_predictive,
            metric_delta,
            output_paths.comparison_report_md,
        )

    artifacts = migration_pulse_candidate_artifacts(output_paths)
    manifest: ExperimentManifest | None = None
    if output_paths.manifest_json is not None:
        manifest = migration_pulse_candidate_manifest(
            candidate,
            metric_delta,
            runs=_workflow_runs(baseline, candidate_result),
            artifacts=artifacts,
            command=command,
            name=manifest_name,
            description=manifest_description,
            metadata=manifest_metadata,
        )
        write_experiment_manifest_json(manifest, output_paths.manifest_json)

    return MigrationPulseCandidateWorkflowResult(
        candidate=candidate,
        baseline=baseline,
        candidate_result=candidate_result,
        metric_delta=metric_delta,
        artifacts=artifacts,
        manifest=manifest,
        candidate_config_toml_path=output_paths.candidate_config_toml,
        comparison_report_md_path=output_paths.comparison_report_md,
        manifest_json_path=output_paths.manifest_json,
    )


def migration_pulse_candidate_artifacts(
    paths: MigrationPulseCandidateOutputPaths,
) -> tuple[ExperimentArtifact, ...]:
    """Return checksum-bearing artifacts for requested candidate paths."""
    artifacts: list[ExperimentArtifact] = []
    for name, role, path in (
        ("config", "config", paths.config),
        ("targets", "targets", paths.targets),
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
        ("comparison_report_md", "other", paths.comparison_report_md),
    ):
        if path is not None:
            artifacts.append(artifact_from_path(name, cast(ArtifactRole, role), path))
    return tuple(artifacts)


def migration_pulse_candidate_manifest(
    candidate: MigrationPulseCandidate,
    metric_delta: PosteriorPredictiveMetricDelta,
    *,
    runs: Iterable[SweepRun],
    artifacts: Iterable[ExperimentArtifact] = (),
    command: str = "programmatic-evaluate-migration-pulse-candidate",
    name: str = "migration-pulse-candidate",
    description: str = "Migration-pulse structural candidate manifest",
    metadata: Mapping[str, str] | None = None,
) -> ExperimentManifest:
    """Return a manifest for one migration-pulse candidate comparison."""
    manifest_metadata = {
        "command": command,
        "candidate_name": candidate.name,
        "candidate_region": candidate.region,
        "candidate_start_bce": f"{candidate.start_bce:.12g}",
        "candidate_end_bce": f"{candidate.end_bce:.12g}",
        "candidate_annual_rate": f"{candidate.annual_rate:.12g}",
        "coverage_rate_delta": f"{metric_delta.coverage_rate_delta:.12g}",
        "mean_absolute_error_delta": (f"{metric_delta.mean_absolute_error_delta:.12g}"),
        "root_mean_squared_error_delta": (
            f"{metric_delta.root_mean_squared_error_delta:.12g}"
        ),
        "max_abs_z_score_delta": f"{metric_delta.max_abs_z_score_delta:.12g}",
        "focus_observation_index": str(metric_delta.focus_observation_index),
        "focus_residual_delta": f"{metric_delta.focus_residual_delta:.12g}",
    }
    manifest_metadata.update({} if metadata is None else metadata)
    return ExperimentManifest(
        name=name,
        description=description,
        artifacts=tuple(artifacts),
        fingerprints=(fingerprint_sweep_collection(tuple(runs)),),
        metadata=manifest_metadata,
    )


def _baseline_inference_paths(
    paths: MigrationPulseCandidateOutputPaths,
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
    paths: MigrationPulseCandidateOutputPaths,
) -> ABCRejectionOutputPaths:
    """Return candidate inference output paths."""
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
