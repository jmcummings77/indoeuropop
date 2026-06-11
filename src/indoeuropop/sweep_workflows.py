"""Reusable workflow helpers for deterministic parameter sweeps."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from indoeuropop.experiments import (
    ExperimentArtifact,
    ExperimentManifest,
    artifact_from_path,
    write_experiment_manifest_json,
)
from indoeuropop.fitting import ScoredSweepRun, run_scored_parameter_sweep
from indoeuropop.reproducibility import fingerprint_sweep_collection
from indoeuropop.sensitivity import SensitivityResult, analyze_sensitivity
from indoeuropop.sweep_reporting import (
    write_scored_sweep_runs_csv,
    write_sensitivity_csv,
    write_sweep_runs_csv,
)
from indoeuropop.sweeps import SweepRun, SweepSpec, run_parameter_sweep
from indoeuropop.targets import TargetDataset


@dataclass(frozen=True)
class SweepOutputPaths:
    """Optional input and output paths for materializing sweep artifacts."""

    config: Path | None = None
    targets: Path | None = None
    sweep_runs_csv: Path | None = None
    sensitivity_csv: Path | None = None
    target_fit_csv: Path | None = None
    manifest_json: Path | None = None


@dataclass(frozen=True)
class SweepWorkflowResult:
    """Runs, diagnostics, and files materialized for a sweep workflow."""

    runs: tuple[SweepRun, ...]
    sensitivity_results: tuple[SensitivityResult, ...]
    scored_runs: tuple[ScoredSweepRun, ...] = ()
    artifacts: tuple[ExperimentArtifact, ...] = ()
    manifest: ExperimentManifest | None = None
    sweep_runs_csv_path: Path | None = None
    sensitivity_csv_path: Path | None = None
    target_fit_csv_path: Path | None = None
    manifest_json_path: Path | None = None


def run_sweep_workflow(
    spec: SweepSpec,
    *,
    paths: SweepOutputPaths | None = None,
    targets: TargetDataset | None = None,
    sensitivity_outcome: str = "final_ancestry",
    fit_metric: str = "chi_square",
    command: str = "programmatic-sweep",
    manifest_name: str = "parameter-sweep",
    manifest_description: str = "Deterministic parameter sweep manifest",
    manifest_metadata: Mapping[str, str] | None = None,
) -> SweepWorkflowResult:
    """Run a deterministic sweep and materialize requested outputs."""
    scored_runs = (
        ()
        if targets is None
        else run_scored_parameter_sweep(spec, targets, metric=fit_metric)
    )
    return write_sweep_outputs(
        run_parameter_sweep(spec),
        paths=paths,
        scored_runs=scored_runs,
        sensitivity_outcome=sensitivity_outcome,
        fit_metric=fit_metric,
        command=command,
        manifest_name=manifest_name,
        manifest_description=manifest_description,
        manifest_metadata=manifest_metadata,
    )


def write_sweep_outputs(
    runs: Iterable[SweepRun],
    *,
    paths: SweepOutputPaths | None = None,
    sensitivity_results: Iterable[SensitivityResult] | None = None,
    scored_runs: Iterable[ScoredSweepRun] = (),
    sensitivity_outcome: str = "final_ancestry",
    fit_metric: str = "chi_square",
    command: str = "programmatic-sweep",
    manifest_name: str = "parameter-sweep",
    manifest_description: str = "Deterministic parameter sweep manifest",
    manifest_metadata: Mapping[str, str] | None = None,
) -> SweepWorkflowResult:
    """Write requested sweep CSVs and an optional manifest for existing runs."""
    run_tuple = _validated_runs(runs)
    output_paths = SweepOutputPaths() if paths is None else paths
    scored_tuple = tuple(scored_runs)
    sensitivity_tuple = (
        analyze_sensitivity(run_tuple, outcome=sensitivity_outcome)
        if sensitivity_results is None
        else tuple(sensitivity_results)
    )
    if output_paths.target_fit_csv is not None and not scored_tuple:
        raise ValueError("target_fit_csv requires scored sweep runs")
    if output_paths.sweep_runs_csv is not None:
        write_sweep_runs_csv(run_tuple, output_paths.sweep_runs_csv)
    if output_paths.sensitivity_csv is not None:
        write_sensitivity_csv(sensitivity_tuple, output_paths.sensitivity_csv)
    if output_paths.target_fit_csv is not None:
        write_scored_sweep_runs_csv(scored_tuple, output_paths.target_fit_csv)

    artifacts = _sweep_artifacts(output_paths)
    manifest: ExperimentManifest | None = None
    if output_paths.manifest_json is not None:
        manifest = sweep_experiment_manifest(
            run_tuple,
            artifacts=artifacts,
            sensitivity_outcome=sensitivity_outcome,
            target_fit_metric=fit_metric if scored_tuple else None,
            command=command,
            name=manifest_name,
            description=manifest_description,
            metadata=manifest_metadata,
        )
        write_experiment_manifest_json(manifest, output_paths.manifest_json)
    return SweepWorkflowResult(
        runs=run_tuple,
        sensitivity_results=sensitivity_tuple,
        scored_runs=scored_tuple,
        artifacts=artifacts,
        manifest=manifest,
        sweep_runs_csv_path=output_paths.sweep_runs_csv,
        sensitivity_csv_path=output_paths.sensitivity_csv,
        target_fit_csv_path=output_paths.target_fit_csv,
        manifest_json_path=output_paths.manifest_json,
    )


def sweep_experiment_manifest(
    runs: Iterable[SweepRun],
    *,
    artifacts: Iterable[ExperimentArtifact] = (),
    sensitivity_outcome: str = "final_ancestry",
    target_fit_metric: str | None = None,
    command: str = "programmatic-sweep",
    name: str = "parameter-sweep",
    description: str = "Deterministic parameter sweep manifest",
    metadata: Mapping[str, str] | None = None,
) -> ExperimentManifest:
    """Return an experiment manifest for deterministic sweep outputs."""
    run_tuple = _validated_runs(runs)
    first_summary = run_tuple[0].summary
    manifest_metadata = {
        "command": command,
        "sample_count": str(len(run_tuple)),
        "sensitivity_outcome": sensitivity_outcome,
        "source": first_summary.source,
        "region": first_summary.region or "all",
    }
    if target_fit_metric is not None:
        manifest_metadata["target_fit_metric"] = target_fit_metric
    manifest_metadata.update({} if metadata is None else metadata)
    return ExperimentManifest(
        name=name,
        description=description,
        artifacts=tuple(artifacts),
        fingerprints=(fingerprint_sweep_collection(run_tuple),),
        metadata=manifest_metadata,
    )


def _sweep_artifacts(paths: SweepOutputPaths) -> tuple[ExperimentArtifact, ...]:
    """Return checksum-bearing artifacts for requested sweep paths."""
    artifacts: list[ExperimentArtifact] = []
    if paths.config is not None:
        artifacts.append(artifact_from_path("config", "config", paths.config))
    if paths.targets is not None:
        artifacts.append(artifact_from_path("targets", "targets", paths.targets))
    if paths.sweep_runs_csv is not None:
        artifacts.append(
            artifact_from_path(
                "sweep_runs_csv",
                "sweep_runs",
                paths.sweep_runs_csv,
            )
        )
    if paths.sensitivity_csv is not None:
        artifacts.append(
            artifact_from_path(
                "sensitivity_csv",
                "sensitivity",
                paths.sensitivity_csv,
            )
        )
    if paths.target_fit_csv is not None:
        artifacts.append(
            artifact_from_path(
                "target_fit_csv",
                "target_fit",
                paths.target_fit_csv,
            )
        )
    return tuple(artifacts)


def _validated_runs(runs: Iterable[SweepRun]) -> tuple[SweepRun, ...]:
    """Return a non-empty sweep-run tuple."""
    run_tuple = tuple(runs)
    if not run_tuple:
        raise ValueError("runs must contain at least one sweep run")
    return run_tuple
