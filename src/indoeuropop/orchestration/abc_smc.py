"""Workflow helpers for sequential ABC-style calibration."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from indoeuropop.analysis.abc_smc import (
    ABCSMCOptions,
    ABCSMCResult,
    run_abc_smc_inference,
)
from indoeuropop.analysis.posterior_predictive import (
    PosteriorPredictiveDiagnostics,
    posterior_predictive_diagnostics,
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
    _posterior_predictive_metadata,
    _write_posterior_predictive_outputs,
    score_accepted_runs_against_targets,
)
from indoeuropop.orchestration.sweeps import SweepRun, SweepSpec
from indoeuropop.reporting.abc_smc import (
    write_abc_smc_generations_csv,
    write_abc_smc_markdown,
)
from indoeuropop.reporting.inference import (
    write_accepted_samples_csv,
    write_posterior_summaries_csv,
)
from indoeuropop.reporting.reproducibility import fingerprint_sweep_collection


@dataclass(frozen=True)
class ABCSMCOutputPaths:
    """Input and output paths for sequential ABC calibration artifacts."""

    config: Path | None = None
    targets: Path | None = None
    generations_csv: Path | None = None
    final_samples_csv: Path | None = None
    final_summary_csv: Path | None = None
    inference_report_md: Path | None = None
    posterior_predictive_csv: Path | None = None
    posterior_predictive_report_md: Path | None = None
    posterior_predictive_plot: Path | None = None
    holdout_targets: Path | None = None
    holdout_posterior_predictive_csv: Path | None = None
    holdout_posterior_predictive_report_md: Path | None = None
    holdout_posterior_predictive_plot: Path | None = None
    manifest_json: Path | None = None


@dataclass(frozen=True)
class ABCSMCWorkflowResult:
    """Sequential ABC calibration result and materialized artifacts."""

    inference: ABCSMCResult
    artifacts: tuple[ExperimentArtifact, ...] = ()
    manifest: ExperimentManifest | None = None
    posterior_predictive: PosteriorPredictiveDiagnostics | None = None
    holdout_posterior_predictive: PosteriorPredictiveDiagnostics | None = None
    generations_csv_path: Path | None = None
    final_samples_csv_path: Path | None = None
    final_summary_csv_path: Path | None = None
    inference_report_md_path: Path | None = None
    posterior_predictive_csv_path: Path | None = None
    posterior_predictive_report_md_path: Path | None = None
    posterior_predictive_plot_path: Path | None = None
    holdout_posterior_predictive_csv_path: Path | None = None
    holdout_posterior_predictive_report_md_path: Path | None = None
    holdout_posterior_predictive_plot_path: Path | None = None
    manifest_json_path: Path | None = None


def run_abc_smc_workflow(
    spec: SweepSpec,
    targets: TargetDataset,
    *,
    options: ABCSMCOptions | None = None,
    paths: ABCSMCOutputPaths | None = None,
    command: str = "programmatic-infer-target-parameters-smc",
    manifest_name: str = "abc-smc-calibration",
    manifest_description: str = "ABC-SMC-style target calibration manifest",
    manifest_metadata: Mapping[str, str] | None = None,
    interval_probability: float = 0.9,
    holdout_targets: TargetDataset | None = None,
) -> ABCSMCWorkflowResult:
    """Run sequential ABC calibration and write requested artifacts."""
    output_paths = ABCSMCOutputPaths() if paths is None else paths
    inference = run_abc_smc_inference(spec, targets, options)
    if output_paths.generations_csv is not None:
        write_abc_smc_generations_csv(inference, output_paths.generations_csv)
    if output_paths.final_samples_csv is not None:
        write_accepted_samples_csv(
            inference.final_inference,
            output_paths.final_samples_csv,
        )
    if output_paths.final_summary_csv is not None:
        write_posterior_summaries_csv(
            inference.final_inference.parameter_summaries,
            output_paths.final_summary_csv,
        )
    if output_paths.inference_report_md is not None:
        write_abc_smc_markdown(inference, output_paths.inference_report_md)
    posterior_predictive = posterior_predictive_diagnostics(
        inference.final_inference.accepted_runs,
        interval_probability=interval_probability,
    )
    _write_posterior_predictive_outputs(
        posterior_predictive,
        csv_path=output_paths.posterior_predictive_csv,
        report_path=output_paths.posterior_predictive_report_md,
        plot_path=output_paths.posterior_predictive_plot,
        title="ABC-SMC Posterior Predictive Diagnostics",
    )
    holdout_posterior_predictive = _holdout_posterior_predictive(
        spec,
        inference,
        holdout_targets,
        interval_probability,
        output_paths,
    )
    artifacts = abc_smc_artifacts(output_paths)
    manifest = _maybe_write_abc_smc_manifest(
        inference,
        artifacts=artifacts,
        output_path=output_paths.manifest_json,
        command=command,
        name=manifest_name,
        description=manifest_description,
        metadata=manifest_metadata,
        posterior_predictive=posterior_predictive,
        holdout_posterior_predictive=holdout_posterior_predictive,
    )
    return ABCSMCWorkflowResult(
        inference=inference,
        artifacts=artifacts,
        manifest=manifest,
        posterior_predictive=posterior_predictive,
        holdout_posterior_predictive=holdout_posterior_predictive,
        generations_csv_path=output_paths.generations_csv,
        final_samples_csv_path=output_paths.final_samples_csv,
        final_summary_csv_path=output_paths.final_summary_csv,
        inference_report_md_path=output_paths.inference_report_md,
        posterior_predictive_csv_path=output_paths.posterior_predictive_csv,
        posterior_predictive_report_md_path=output_paths.posterior_predictive_report_md,
        posterior_predictive_plot_path=output_paths.posterior_predictive_plot,
        holdout_posterior_predictive_csv_path=(
            output_paths.holdout_posterior_predictive_csv
        ),
        holdout_posterior_predictive_report_md_path=(
            output_paths.holdout_posterior_predictive_report_md
        ),
        holdout_posterior_predictive_plot_path=(
            output_paths.holdout_posterior_predictive_plot
        ),
        manifest_json_path=output_paths.manifest_json,
    )


def abc_smc_artifacts(paths: ABCSMCOutputPaths) -> tuple[ExperimentArtifact, ...]:
    """Return checksum-bearing artifacts for requested SMC output paths."""
    artifacts: list[ExperimentArtifact] = []
    _append_artifact(artifacts, "config", "config", paths.config)
    _append_artifact(artifacts, "targets", "targets", paths.targets)
    _append_artifact(artifacts, "generations_csv", "target_fit", paths.generations_csv)
    _append_artifact(
        artifacts, "final_samples_csv", "target_fit", paths.final_samples_csv
    )
    _append_artifact(artifacts, "final_summary_csv", "other", paths.final_summary_csv)
    _append_artifact(
        artifacts, "inference_report_md", "other", paths.inference_report_md
    )
    _append_artifact(
        artifacts,
        "posterior_predictive_csv",
        "target_fit",
        paths.posterior_predictive_csv,
    )
    _append_artifact(
        artifacts,
        "posterior_predictive_report_md",
        "other",
        paths.posterior_predictive_report_md,
    )
    _append_artifact(
        artifacts,
        "posterior_predictive_plot",
        "plot",
        paths.posterior_predictive_plot,
    )
    _append_artifact(artifacts, "holdout_targets", "targets", paths.holdout_targets)
    _append_artifact(
        artifacts,
        "holdout_posterior_predictive_csv",
        "target_fit",
        paths.holdout_posterior_predictive_csv,
    )
    _append_artifact(
        artifacts,
        "holdout_posterior_predictive_report_md",
        "other",
        paths.holdout_posterior_predictive_report_md,
    )
    _append_artifact(
        artifacts,
        "holdout_posterior_predictive_plot",
        "plot",
        paths.holdout_posterior_predictive_plot,
    )
    return tuple(artifacts)


def abc_smc_experiment_manifest(
    result: ABCSMCResult,
    *,
    runs: Iterable[SweepRun],
    artifacts: Iterable[ExperimentArtifact] = (),
    command: str = "programmatic-infer-target-parameters-smc",
    name: str = "abc-smc-calibration",
    description: str = "ABC-SMC-style target calibration manifest",
    metadata: Mapping[str, str] | None = None,
    posterior_predictive: PosteriorPredictiveDiagnostics | None = None,
    holdout_posterior_predictive: PosteriorPredictiveDiagnostics | None = None,
) -> ExperimentManifest:
    """Return a manifest for one sequential ABC calibration workflow."""
    manifest_metadata = {
        "command": command,
        "fit_metric": result.options.fit_metric,
        "generation_count": str(len(result.generations)),
        "total_candidate_count": str(result.total_candidate_count),
        "final_accepted_count": str(result.final_inference.accepted_count),
        "final_acceptance_threshold": (
            f"{result.final_inference.acceptance_threshold:.12g}"
        ),
        "threshold_schedule": ",".join(
            f"{threshold:.12g}" for threshold in result.threshold_schedule
        ),
        "final_best_run_index": str(result.final_inference.best_run.run.index),
    }
    if posterior_predictive is not None:
        manifest_metadata.update(
            _posterior_predictive_metadata(
                "posterior_predictive",
                posterior_predictive,
            )
        )
    if holdout_posterior_predictive is not None:
        manifest_metadata.update(
            _posterior_predictive_metadata(
                "holdout_posterior_predictive",
                holdout_posterior_predictive,
            )
        )
    manifest_metadata.update({} if metadata is None else metadata)
    return ExperimentManifest(
        name=name,
        description=description,
        artifacts=tuple(artifacts),
        fingerprints=(fingerprint_sweep_collection(tuple(runs)),),
        metadata=manifest_metadata,
    )


def abc_smc_scored_runs(result: ABCSMCResult) -> tuple[SweepRun, ...]:
    """Return all scored sweep runs from all SMC generations."""
    return tuple(
        scored_run.run
        for generation in result.generations
        for scored_run in generation.inference.ranked_runs
    )


def _maybe_write_abc_smc_manifest(
    result: ABCSMCResult,
    *,
    artifacts: Iterable[ExperimentArtifact],
    output_path: Path | None,
    command: str,
    name: str,
    description: str,
    metadata: Mapping[str, str] | None,
    posterior_predictive: PosteriorPredictiveDiagnostics,
    holdout_posterior_predictive: PosteriorPredictiveDiagnostics | None,
) -> ExperimentManifest | None:
    """Write and return a manifest when requested."""
    if output_path is None:
        return None
    manifest = abc_smc_experiment_manifest(
        result,
        runs=abc_smc_scored_runs(result),
        artifacts=artifacts,
        command=command,
        name=name,
        description=description,
        metadata=metadata,
        posterior_predictive=posterior_predictive,
        holdout_posterior_predictive=holdout_posterior_predictive,
    )
    write_experiment_manifest_json(manifest, output_path)
    return manifest


def _holdout_posterior_predictive(
    spec: SweepSpec,
    result: ABCSMCResult,
    holdout_targets: TargetDataset | None,
    interval_probability: float,
    paths: ABCSMCOutputPaths,
) -> PosteriorPredictiveDiagnostics | None:
    """Return and write optional holdout posterior predictive diagnostics."""
    if holdout_targets is None:
        return None
    holdout_runs = score_accepted_runs_against_targets(
        spec,
        result.final_inference.accepted_runs,
        holdout_targets,
    )
    diagnostics = posterior_predictive_diagnostics(
        holdout_runs,
        interval_probability=interval_probability,
    )
    _write_posterior_predictive_outputs(
        diagnostics,
        csv_path=paths.holdout_posterior_predictive_csv,
        report_path=paths.holdout_posterior_predictive_report_md,
        plot_path=paths.holdout_posterior_predictive_plot,
        title="ABC-SMC Holdout Posterior Predictive Diagnostics",
    )
    return diagnostics


def _append_artifact(
    artifacts: list[ExperimentArtifact],
    name: str,
    role: ArtifactRole,
    path: Path | None,
) -> None:
    """Append one artifact for an existing optional output path."""
    if path is not None:
        artifacts.append(artifact_from_path(name, role, path))
