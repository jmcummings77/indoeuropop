"""Reusable workflow helpers for configured simulation runs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

from indoeuropop.config import SimulationConfig
from indoeuropop.diagnostics import validate_simulation_result
from indoeuropop.experiments import ExperimentArtifact, ExperimentManifest
from indoeuropop.fitting import score_result_against_targets
from indoeuropop.models import SimulationResult
from indoeuropop.provenance import (
    ProvenanceRecord,
    summary_provenance_records,
    target_fit_provenance_records,
    target_observation_provenance_records,
)
from indoeuropop.reporting import diagnostic_issue_records
from indoeuropop.reproducibility import (
    ReproducibilityFingerprint,
    fingerprint_simulation_result,
)
from indoeuropop.simulation import run_deterministic, run_tau_leap
from indoeuropop.summary import summarize_trajectory
from indoeuropop.targets import TargetDataset

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


def _validated_simulator_kind(value: SimulatorKind) -> SimulatorKind:
    """Return a validated simulator kind."""
    if value not in SIMULATOR_KINDS:
        raise ValueError("simulator is not supported")
    return value
