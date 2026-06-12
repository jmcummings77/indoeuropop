"""Workflow helpers for bounded ABC-style target-parameter inference."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from indoeuropop.analysis.fitting import (
    ScoredSweepRun,
    run_scored_parameter_sweep,
    score_result_against_targets,
)
from indoeuropop.analysis.inference import (
    ABCRejectionOptions,
    ABCRejectionResult,
    run_abc_rejection_inference,
)
from indoeuropop.analysis.posterior_predictive import (
    PosteriorPredictiveDiagnostics,
    posterior_predictive_diagnostics,
)
from indoeuropop.data.targets import TargetDataset
from indoeuropop.orchestration.experiments import (
    ExperimentArtifact,
    ExperimentManifest,
    artifact_from_path,
    write_experiment_manifest_json,
)
from indoeuropop.orchestration.sweeps import SweepRun, SweepSpec
from indoeuropop.reporting.inference import (
    write_abc_rejection_markdown,
    write_accepted_samples_csv,
    write_posterior_summaries_csv,
)
from indoeuropop.reporting.posterior_predictive import (
    write_posterior_predictive_csv,
    write_posterior_predictive_markdown,
    write_posterior_predictive_plot,
)
from indoeuropop.reporting.reproducibility import fingerprint_sweep_collection
from indoeuropop.simulation import run_deterministic


@dataclass(frozen=True)
class ABCRejectionOutputPaths:
    """Input and output paths for ABC rejection inference artifacts."""

    config: Path | None = None
    targets: Path | None = None
    accepted_samples_csv: Path | None = None
    posterior_summary_csv: Path | None = None
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
class ABCRejectionWorkflowResult:
    """ABC rejection result and materialized workflow artifacts."""

    inference: ABCRejectionResult
    artifacts: tuple[ExperimentArtifact, ...] = ()
    manifest: ExperimentManifest | None = None
    posterior_predictive: PosteriorPredictiveDiagnostics | None = None
    holdout_posterior_predictive: PosteriorPredictiveDiagnostics | None = None
    accepted_samples_csv_path: Path | None = None
    posterior_summary_csv_path: Path | None = None
    inference_report_md_path: Path | None = None
    posterior_predictive_csv_path: Path | None = None
    posterior_predictive_report_md_path: Path | None = None
    posterior_predictive_plot_path: Path | None = None
    holdout_posterior_predictive_csv_path: Path | None = None
    holdout_posterior_predictive_report_md_path: Path | None = None
    holdout_posterior_predictive_plot_path: Path | None = None
    manifest_json_path: Path | None = None


def run_abc_rejection_workflow(
    spec: SweepSpec,
    targets: TargetDataset,
    *,
    options: ABCRejectionOptions | None = None,
    paths: ABCRejectionOutputPaths | None = None,
    command: str = "programmatic-infer-target-parameters",
    manifest_name: str = "abc-rejection-inference",
    manifest_description: str = "ABC rejection target-parameter inference manifest",
    manifest_metadata: Mapping[str, str] | None = None,
    interval_probability: float = 0.9,
    holdout_targets: TargetDataset | None = None,
) -> ABCRejectionWorkflowResult:
    """Run a scored deterministic sweep and retain ABC-style accepted samples."""
    inference_options = ABCRejectionOptions() if options is None else options
    target_dataset = targets.require_observations()
    scored_runs = run_scored_parameter_sweep(
        spec,
        target_dataset,
        metric=inference_options.fit_metric,
    )
    inference = run_abc_rejection_inference(scored_runs, inference_options)
    output_paths = ABCRejectionOutputPaths() if paths is None else paths
    if output_paths.accepted_samples_csv is not None:
        write_accepted_samples_csv(inference, output_paths.accepted_samples_csv)
    if output_paths.posterior_summary_csv is not None:
        write_posterior_summaries_csv(
            inference.parameter_summaries,
            output_paths.posterior_summary_csv,
        )
    if output_paths.inference_report_md is not None:
        write_abc_rejection_markdown(inference, output_paths.inference_report_md)
    posterior_predictive = posterior_predictive_diagnostics(
        inference.accepted_runs,
        interval_probability=interval_probability,
    )
    _write_posterior_predictive_outputs(
        posterior_predictive,
        csv_path=output_paths.posterior_predictive_csv,
        report_path=output_paths.posterior_predictive_report_md,
        plot_path=output_paths.posterior_predictive_plot,
        title="Posterior Predictive Diagnostics",
    )

    holdout_posterior_predictive: PosteriorPredictiveDiagnostics | None = None
    if holdout_targets is not None:
        holdout_runs = score_accepted_runs_against_targets(
            spec,
            inference.accepted_runs,
            holdout_targets,
        )
        holdout_posterior_predictive = posterior_predictive_diagnostics(
            holdout_runs,
            interval_probability=interval_probability,
        )
        _write_posterior_predictive_outputs(
            holdout_posterior_predictive,
            csv_path=output_paths.holdout_posterior_predictive_csv,
            report_path=output_paths.holdout_posterior_predictive_report_md,
            plot_path=output_paths.holdout_posterior_predictive_plot,
            title="Holdout Posterior Predictive Diagnostics",
        )

    artifacts = abc_rejection_artifacts(output_paths)
    manifest: ExperimentManifest | None = None
    if output_paths.manifest_json is not None:
        manifest = abc_rejection_experiment_manifest(
            inference,
            runs=tuple(scored.run for scored in inference.ranked_runs),
            artifacts=artifacts,
            command=command,
            name=manifest_name,
            description=manifest_description,
            metadata=manifest_metadata,
            posterior_predictive=posterior_predictive,
            holdout_posterior_predictive=holdout_posterior_predictive,
        )
        write_experiment_manifest_json(manifest, output_paths.manifest_json)

    return ABCRejectionWorkflowResult(
        inference=inference,
        artifacts=artifacts,
        manifest=manifest,
        posterior_predictive=posterior_predictive,
        holdout_posterior_predictive=holdout_posterior_predictive,
        accepted_samples_csv_path=output_paths.accepted_samples_csv,
        posterior_summary_csv_path=output_paths.posterior_summary_csv,
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


def score_accepted_runs_against_targets(
    spec: SweepSpec,
    accepted_runs: Iterable[ScoredSweepRun],
    targets: TargetDataset,
) -> tuple[ScoredSweepRun, ...]:
    """Re-score accepted parameter samples against another target dataset."""
    target_dataset = targets.require_observations()
    scored_runs: list[ScoredSweepRun] = []
    for accepted_run in accepted_runs:
        result = run_deterministic(
            spec.initial_state,
            accepted_run.run.parameters,
            start_bce=spec.start_bce,
            end_bce=spec.end_bce,
            step_years=spec.step_years,
            schedule=spec.schedule,
            parameter_set=spec.parameter_set,
        )
        scored_runs.append(
            ScoredSweepRun(
                run=accepted_run.run,
                fit=score_result_against_targets(result, target_dataset),
            )
        )
    if not scored_runs:
        raise ValueError("accepted_runs must contain at least one run")
    return tuple(scored_runs)


def abc_rejection_artifacts(
    paths: ABCRejectionOutputPaths,
) -> tuple[ExperimentArtifact, ...]:
    """Return checksum-bearing artifacts for requested inference paths."""
    artifacts: list[ExperimentArtifact] = []
    if paths.config is not None:
        artifacts.append(artifact_from_path("config", "config", paths.config))
    if paths.targets is not None:
        artifacts.append(artifact_from_path("targets", "targets", paths.targets))
    if paths.accepted_samples_csv is not None:
        artifacts.append(
            artifact_from_path(
                "accepted_samples_csv",
                "target_fit",
                paths.accepted_samples_csv,
            )
        )
    if paths.posterior_summary_csv is not None:
        artifacts.append(
            artifact_from_path(
                "posterior_summary_csv",
                "other",
                paths.posterior_summary_csv,
            )
        )
    if paths.inference_report_md is not None:
        artifacts.append(
            artifact_from_path(
                "inference_report_md",
                "other",
                paths.inference_report_md,
            )
        )
    if paths.posterior_predictive_csv is not None:
        artifacts.append(
            artifact_from_path(
                "posterior_predictive_csv",
                "target_fit",
                paths.posterior_predictive_csv,
            )
        )
    if paths.posterior_predictive_report_md is not None:
        artifacts.append(
            artifact_from_path(
                "posterior_predictive_report_md",
                "other",
                paths.posterior_predictive_report_md,
            )
        )
    if paths.posterior_predictive_plot is not None:
        artifacts.append(
            artifact_from_path(
                "posterior_predictive_plot",
                "plot",
                paths.posterior_predictive_plot,
            )
        )
    if paths.holdout_targets is not None:
        artifacts.append(
            artifact_from_path("holdout_targets", "targets", paths.holdout_targets)
        )
    if paths.holdout_posterior_predictive_csv is not None:
        artifacts.append(
            artifact_from_path(
                "holdout_posterior_predictive_csv",
                "target_fit",
                paths.holdout_posterior_predictive_csv,
            )
        )
    if paths.holdout_posterior_predictive_report_md is not None:
        artifacts.append(
            artifact_from_path(
                "holdout_posterior_predictive_report_md",
                "other",
                paths.holdout_posterior_predictive_report_md,
            )
        )
    if paths.holdout_posterior_predictive_plot is not None:
        artifacts.append(
            artifact_from_path(
                "holdout_posterior_predictive_plot",
                "plot",
                paths.holdout_posterior_predictive_plot,
            )
        )
    return tuple(artifacts)


def abc_rejection_experiment_manifest(
    result: ABCRejectionResult,
    *,
    runs: Iterable[SweepRun],
    artifacts: Iterable[ExperimentArtifact] = (),
    command: str = "programmatic-infer-target-parameters",
    name: str = "abc-rejection-inference",
    description: str = "ABC rejection target-parameter inference manifest",
    metadata: Mapping[str, str] | None = None,
    posterior_predictive: PosteriorPredictiveDiagnostics | None = None,
    holdout_posterior_predictive: PosteriorPredictiveDiagnostics | None = None,
) -> ExperimentManifest:
    """Return a manifest for one ABC rejection inference workflow."""
    manifest_metadata = {
        "command": command,
        "fit_metric": result.options.fit_metric,
        "acceptance_criterion": result.options.criterion,
        "candidate_count": str(result.candidate_count),
        "accepted_count": str(result.accepted_count),
        "acceptance_rate": f"{result.acceptance_rate:.12g}",
        "acceptance_threshold": f"{result.acceptance_threshold:.12g}",
        "best_run_index": str(result.best_run.run.index),
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


def _write_posterior_predictive_outputs(
    diagnostics: PosteriorPredictiveDiagnostics,
    *,
    csv_path: Path | None,
    report_path: Path | None,
    plot_path: Path | None,
    title: str,
) -> None:
    """Write requested posterior predictive artifacts."""
    if csv_path is not None:
        write_posterior_predictive_csv(diagnostics, csv_path)
    if report_path is not None:
        write_posterior_predictive_markdown(diagnostics, report_path, title=title)
    if plot_path is not None:
        write_posterior_predictive_plot(diagnostics, plot_path)


def _posterior_predictive_metadata(
    prefix: str,
    diagnostics: PosteriorPredictiveDiagnostics,
) -> dict[str, str]:
    """Return manifest metadata for one posterior predictive diagnostic set."""
    return {
        f"{prefix}_observation_count": str(diagnostics.observation_count),
        f"{prefix}_coverage_rate": f"{diagnostics.coverage_rate:.12g}",
        f"{prefix}_mean_absolute_error": (f"{diagnostics.mean_absolute_error:.12g}"),
        f"{prefix}_root_mean_squared_error": (
            f"{diagnostics.root_mean_squared_error:.12g}"
        ),
        f"{prefix}_max_abs_z_score": f"{diagnostics.max_abs_z_score:.12g}",
    }
