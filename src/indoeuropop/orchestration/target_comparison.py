"""Workflow helpers for comparing deterministic sweeps to target observations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from indoeuropop.analysis.fitting import ScoredSweepRun
from indoeuropop.data.targets import TargetComparison, TargetDataset
from indoeuropop.models import SimulationResult
from indoeuropop.orchestration.experiments import (
    ExperimentArtifact,
    ExperimentManifest,
    artifact_from_path,
    write_experiment_manifest_json,
)
from indoeuropop.orchestration.sweep_workflows import (
    SweepOutputPaths,
    SweepWorkflowResult,
    run_sweep_workflow,
    sweep_experiment_manifest,
)
from indoeuropop.orchestration.sweeps import SweepRun, SweepSpec
from indoeuropop.reporting.target_comparison import write_target_comparisons_csv
from indoeuropop.reporting.visualization import plot_target_comparison
from indoeuropop.simulation import run_deterministic


@dataclass(frozen=True)
class TargetComparisonOutputPaths:
    """Optional input and output paths for target-comparison artifacts."""

    config: Path | None = None
    targets: Path | None = None
    sweep_runs_csv: Path | None = None
    sensitivity_csv: Path | None = None
    target_fit_csv: Path | None = None
    target_residuals_csv: Path | None = None
    plot: Path | None = None
    manifest_json: Path | None = None


@dataclass(frozen=True)
class TargetComparisonWorkflowResult:
    """Outputs and best-run diagnostics from a target-comparison workflow."""

    sweep: SweepWorkflowResult
    best_run: ScoredSweepRun
    best_result: SimulationResult
    best_comparisons: tuple[TargetComparison, ...]
    artifacts: tuple[ExperimentArtifact, ...] = ()
    manifest: ExperimentManifest | None = None
    target_residuals_csv_path: Path | None = None
    plot_path: Path | None = None
    manifest_json_path: Path | None = None


def run_target_comparison_workflow(
    spec: SweepSpec,
    targets: TargetDataset,
    *,
    paths: TargetComparisonOutputPaths | None = None,
    sensitivity_outcome: str = "final_ancestry",
    fit_metric: str = "chi_square",
    plot_source: str | None = None,
    plot_region: str | None = None,
    command: str = "programmatic-compare-targets",
    manifest_name: str = "target-comparison",
    manifest_description: str = "Deterministic target-comparison manifest",
    manifest_metadata: Mapping[str, str] | None = None,
) -> TargetComparisonWorkflowResult:
    """Run a sweep, rank it against targets, and write comparison artifacts."""
    target_dataset = targets.require_observations()
    output_paths = TargetComparisonOutputPaths() if paths is None else paths
    sweep_result = run_sweep_workflow(
        spec,
        paths=_sweep_paths_without_manifest(output_paths),
        targets=target_dataset,
        sensitivity_outcome=sensitivity_outcome,
        fit_metric=fit_metric,
        command=command,
        manifest_name=manifest_name,
        manifest_description=manifest_description,
        manifest_metadata=manifest_metadata,
    )
    best_run = sweep_result.scored_runs[0]
    best_result = run_sweep_run_simulation(spec, best_run)
    best_comparisons = target_dataset.compare(best_result)

    if output_paths.target_residuals_csv is not None:
        write_target_comparisons_csv(
            best_comparisons, output_paths.target_residuals_csv
        )
    if output_paths.plot is not None:
        output_paths.plot.parent.mkdir(parents=True, exist_ok=True)
        figure = plot_target_comparison(
            best_result,
            target_dataset,
            source=plot_source,
            region=plot_region,
        )
        figure.savefig(output_paths.plot)

    artifacts = target_comparison_artifacts(output_paths)
    manifest: ExperimentManifest | None = None
    if output_paths.manifest_json is not None:
        manifest = target_comparison_experiment_manifest(
            sweep_result.runs,
            best_run=best_run,
            target_count=len(target_dataset.observations),
            artifacts=artifacts,
            sensitivity_outcome=sensitivity_outcome,
            fit_metric=fit_metric,
            command=command,
            name=manifest_name,
            description=manifest_description,
            metadata=manifest_metadata,
        )
        write_experiment_manifest_json(manifest, output_paths.manifest_json)

    return TargetComparisonWorkflowResult(
        sweep=sweep_result,
        best_run=best_run,
        best_result=best_result,
        best_comparisons=best_comparisons,
        artifacts=artifacts,
        manifest=manifest,
        target_residuals_csv_path=output_paths.target_residuals_csv,
        plot_path=output_paths.plot,
        manifest_json_path=output_paths.manifest_json,
    )


def run_sweep_run_simulation(
    spec: SweepSpec, scored_run: ScoredSweepRun
) -> SimulationResult:
    """Re-run one deterministic sweep sample and return its full trajectory."""
    return run_deterministic(
        spec.initial_state,
        scored_run.run.parameters,
        start_bce=spec.start_bce,
        end_bce=spec.end_bce,
        step_years=spec.step_years,
        schedule=spec.schedule,
        parameter_set=spec.parameter_set,
    )


def target_comparison_artifacts(
    paths: TargetComparisonOutputPaths,
) -> tuple[ExperimentArtifact, ...]:
    """Return checksum-bearing artifacts for requested comparison paths."""
    artifacts: list[ExperimentArtifact] = []
    if paths.config is not None:
        artifacts.append(artifact_from_path("config", "config", paths.config))
    if paths.targets is not None:
        artifacts.append(artifact_from_path("targets", "targets", paths.targets))
    if paths.sweep_runs_csv is not None:
        artifacts.append(
            artifact_from_path("sweep_runs_csv", "sweep_runs", paths.sweep_runs_csv)
        )
    if paths.sensitivity_csv is not None:
        artifacts.append(
            artifact_from_path("sensitivity_csv", "sensitivity", paths.sensitivity_csv)
        )
    if paths.target_fit_csv is not None:
        artifacts.append(
            artifact_from_path("target_fit_csv", "target_fit", paths.target_fit_csv)
        )
    if paths.target_residuals_csv is not None:
        artifacts.append(
            artifact_from_path(
                "target_residuals_csv", "target_fit", paths.target_residuals_csv
            )
        )
    if paths.plot is not None:
        artifacts.append(
            artifact_from_path("target_comparison_plot", "plot", paths.plot)
        )
    return tuple(artifacts)


def target_comparison_experiment_manifest(
    runs: Iterable[SweepRun],
    *,
    best_run: ScoredSweepRun,
    target_count: int,
    artifacts: Iterable[ExperimentArtifact] = (),
    sensitivity_outcome: str = "final_ancestry",
    fit_metric: str = "chi_square",
    command: str = "programmatic-compare-targets",
    name: str = "target-comparison",
    description: str = "Deterministic target-comparison manifest",
    metadata: Mapping[str, str] | None = None,
) -> ExperimentManifest:
    """Return a manifest for a sweep-to-target comparison workflow."""
    manifest_metadata = {
        "target_observation_count": str(target_count),
        "best_run_index": str(best_run.run.index),
        "best_fit_metric": fit_metric,
        "best_fit_value": _value_text(best_run.metric_value(fit_metric)),
    }
    manifest_metadata.update({} if metadata is None else metadata)
    return sweep_experiment_manifest(
        runs,
        artifacts=artifacts,
        sensitivity_outcome=sensitivity_outcome,
        target_fit_metric=fit_metric,
        command=command,
        name=name,
        description=description,
        metadata=manifest_metadata,
    )


def _sweep_paths_without_manifest(
    paths: TargetComparisonOutputPaths,
) -> SweepOutputPaths:
    """Return sweep-output paths while leaving manifest ownership here."""
    return SweepOutputPaths(
        config=paths.config,
        targets=paths.targets,
        sweep_runs_csv=paths.sweep_runs_csv,
        sensitivity_csv=paths.sensitivity_csv,
        target_fit_csv=paths.target_fit_csv,
        manifest_json=None,
    )


def _value_text(value: float) -> str:
    """Return a stable string representation for numeric metadata."""
    return f"{value:.12g}"
