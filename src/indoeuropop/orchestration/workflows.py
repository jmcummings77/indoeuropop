"""Reusable workflow helpers for configured simulation runs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from indoeuropop.analysis.diagnostics import validate_simulation_result
from indoeuropop.analysis.fitting import score_result_against_targets
from indoeuropop.analysis.summary import summarize_trajectory
from indoeuropop.data.targets import TargetDataset
from indoeuropop.models import SimulationResult
from indoeuropop.orchestration.experiments import (
    ExperimentArtifact,
    ExperimentManifest,
    artifact_from_path,
    write_experiment_manifest_json,
)
from indoeuropop.reporting import diagnostic_issue_records, write_provenance_csv
from indoeuropop.reporting.provenance import (
    ProvenanceRecord,
    summary_provenance_records,
    target_fit_provenance_records,
    target_observation_provenance_records,
)
from indoeuropop.reporting.reproducibility import (
    ReproducibilityFingerprint,
    fingerprint_simulation_result,
)
from indoeuropop.reporting.visualization import plot_ancestry
from indoeuropop.simulation import run_deterministic, run_tau_leap
from indoeuropop.simulation.config import SimulationConfig

SimulatorKind = Literal["deterministic", "tau_leap"]

SIMULATOR_KINDS = frozenset({"deterministic", "tau_leap"})


@dataclass(frozen=True)
class SimulationRun:
    """A simulation result paired with the simulator metadata that produced it."""

    result: SimulationResult
    simulator: SimulatorKind
    seed: int | None = None

    def __post_init__(self) -> None:
        """Validate simulator identity and seed semantics."""
        _validated_simulator_kind(self.simulator)
        if self.simulator == "deterministic" and self.seed is not None:
            raise ValueError("deterministic runs should not store a seed")
        if self.simulator == "tau_leap" and self.seed is None:
            raise ValueError("tau_leap runs require a seed")

    def final_ancestry(self, source: str, region: str | None = None) -> float:
        """Return final ancestry proportion for a source and optional region."""
        return self.result.final_state.ancestry_proportion(source, region)

    def fingerprint(self) -> ReproducibilityFingerprint:
        """Return the reproducibility fingerprint for this simulation output."""
        return fingerprint_simulation_result(self.result)


@dataclass(frozen=True)
class SimulationOutputPaths:
    """Optional input and output paths for materializing run artifacts."""

    config: Path | None = None
    targets: Path | None = None
    plot: Path | None = None
    provenance_csv: Path | None = None
    manifest_json: Path | None = None


@dataclass(frozen=True)
class SimulationOutputBundle:
    """Files and records materialized for a simulation workflow run."""

    provenance_records: tuple[ProvenanceRecord, ...]
    artifacts: tuple[ExperimentArtifact, ...] = ()
    manifest: ExperimentManifest | None = None
    plot_path: Path | None = None
    provenance_csv_path: Path | None = None
    manifest_json_path: Path | None = None


def run_configured_simulation(
    config: SimulationConfig,
    *,
    simulator: SimulatorKind = "deterministic",
    seed: int = 7,
) -> SimulationRun:
    """Run a configured simulation with the selected simulator."""
    simulator_kind = _validated_simulator_kind(simulator)
    if simulator_kind == "deterministic":
        return SimulationRun(
            result=run_deterministic(
                config.initial_state,
                config.parameters,
                start_bce=config.start_bce,
                end_bce=config.end_bce,
                step_years=config.step_years,
                schedule=config.schedule,
                parameter_set=config.parameter_set,
            ),
            simulator=simulator_kind,
        )
    return SimulationRun(
        result=run_tau_leap(
            config.initial_state,
            config.parameters,
            start_bce=config.start_bce,
            end_bce=config.end_bce,
            step_years=config.step_years,
            seed=seed,
            schedule=config.schedule,
            parameter_set=config.parameter_set,
        ),
        simulator=simulator_kind,
        seed=seed,
    )


def simulation_provenance_records(
    run: SimulationRun,
    *,
    source: str,
    region: str | None = None,
    dataset: TargetDataset | None = None,
) -> tuple[ProvenanceRecord, ...]:
    """Return provenance records for a configured simulation run."""
    records = list(
        summary_provenance_records(
            summarize_trajectory(run.result, source=source, region=region)
        )
    )
    records.extend(diagnostic_issue_records(validate_simulation_result(run.result)))
    if dataset is not None:
        for observation in dataset.observations:
            records.extend(target_observation_provenance_records(observation))
        records.extend(
            target_fit_provenance_records(
                score_result_against_targets(run.result, dataset)
            )
        )
    return tuple(records)


def write_simulation_outputs(
    run: SimulationRun,
    *,
    source: str,
    region: str | None = None,
    dataset: TargetDataset | None = None,
    paths: SimulationOutputPaths | None = None,
    command: str = "programmatic-run",
    manifest_name: str = "simulation-run",
    manifest_description: str = "Configured simulation run manifest",
    manifest_metadata: Mapping[str, str] | None = None,
) -> SimulationOutputBundle:
    """Write requested plot, provenance, and manifest outputs for a run."""
    output_paths = SimulationOutputPaths() if paths is None else paths
    provenance_records = simulation_provenance_records(
        run,
        source=source,
        region=region,
        dataset=dataset,
    )
    if output_paths.plot is not None:
        figure = plot_ancestry(run.result, source=source, region=region)
        output_paths.plot.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output_paths.plot)
    if output_paths.provenance_csv is not None:
        write_provenance_csv(provenance_records, output_paths.provenance_csv)

    artifacts: tuple[ExperimentArtifact, ...] = ()
    manifest: ExperimentManifest | None = None
    if output_paths.manifest_json is not None:
        artifacts = _output_artifacts(output_paths)
        manifest = simulation_experiment_manifest(
            run,
            source=source,
            region=region,
            artifacts=artifacts,
            command=command,
            name=manifest_name,
            description=manifest_description,
            metadata=manifest_metadata,
        )
        write_experiment_manifest_json(manifest, output_paths.manifest_json)
    return SimulationOutputBundle(
        provenance_records=provenance_records,
        artifacts=artifacts,
        manifest=manifest,
        plot_path=output_paths.plot,
        provenance_csv_path=output_paths.provenance_csv,
        manifest_json_path=output_paths.manifest_json,
    )


def simulation_experiment_manifest(
    run: SimulationRun,
    *,
    source: str,
    region: str | None = None,
    artifacts: Iterable[ExperimentArtifact] = (),
    command: str = "programmatic-run",
    name: str = "simulation-run",
    description: str = "Configured simulation run manifest",
    metadata: Mapping[str, str] | None = None,
) -> ExperimentManifest:
    """Return an experiment manifest for a configured simulation run."""
    manifest_metadata = {
        "command": command,
        "simulator": run.simulator,
        "source": source,
        "region": region or "all",
        "seed": "" if run.seed is None else str(run.seed),
    }
    manifest_metadata.update({} if metadata is None else metadata)
    return ExperimentManifest(
        name=name,
        description=description,
        artifacts=tuple(artifacts),
        fingerprints=(run.fingerprint(),),
        metadata=manifest_metadata,
    )


def _output_artifacts(paths: SimulationOutputPaths) -> tuple[ExperimentArtifact, ...]:
    """Return checksum-bearing artifacts for requested workflow paths."""
    artifacts: list[ExperimentArtifact] = []
    if paths.config is not None:
        artifacts.append(artifact_from_path("config", "config", paths.config))
    if paths.targets is not None:
        artifacts.append(artifact_from_path("targets", "targets", paths.targets))
    if paths.plot is not None:
        artifacts.append(artifact_from_path("plot", "plot", paths.plot))
    if paths.provenance_csv is not None:
        artifacts.append(
            artifact_from_path("provenance_csv", "provenance", paths.provenance_csv)
        )
    return tuple(artifacts)


def _validated_simulator_kind(value: SimulatorKind) -> SimulatorKind:
    """Return a validated simulator kind."""
    if value not in SIMULATOR_KINDS:
        raise ValueError("simulator is not supported")
    return value
