"""Stable fingerprints for reproducible simulation and sweep outputs."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields
from hashlib import sha256
from typing import Literal

from indoeuropop.models import PopulationState, SimulationParameters, SimulationResult
from indoeuropop.provenance import ProvenanceRecord
from indoeuropop.summary import TrajectorySummary
from indoeuropop.sweeps import SweepRun

FingerprintKind = Literal["simulation_result", "sweep_run", "sweep_collection"]

FINGERPRINT_KINDS = frozenset({"simulation_result", "sweep_run", "sweep_collection"})
FINGERPRINT_SCHEMA_VERSION = "indoeuropop-fingerprint-v1"
HEX_DIGITS = frozenset("0123456789abcdef")


@dataclass(frozen=True)
class ReproducibilityFingerprint:
    """A canonical SHA-256 digest for a reproducible model artifact."""

    kind: FingerprintKind
    digest_sha256: str
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        """Validate fingerprint kind, digest, and payload shape."""
        if self.kind not in FINGERPRINT_KINDS:
            raise ValueError("fingerprint kind is not supported")
        if len(self.digest_sha256) != 64 or any(
            character not in HEX_DIGITS for character in self.digest_sha256
        ):
            raise ValueError("digest_sha256 must be a 64-character hex digest")
        if not self.payload:
            raise ValueError("payload must not be empty")
        object.__setattr__(self, "payload", dict(self.payload))

    def canonical_json(self) -> str:
        """Return the canonical JSON text used to compute this fingerprint."""
        return canonical_json_payload(self.payload)

    def to_provenance_record(self) -> ProvenanceRecord:
        """Return this fingerprint as a derived provenance record."""
        return ProvenanceRecord(
            name=f"{self.kind}_fingerprint",
            kind="derived",
            value=self.digest_sha256,
            unit="sha256",
            metadata={
                "fingerprint_kind": self.kind,
                "schema_version": FINGERPRINT_SCHEMA_VERSION,
            },
        )


def canonical_json_payload(payload: Mapping[str, object]) -> str:
    """Return stable compact JSON for a fingerprint payload."""
    return json.dumps(payload, allow_nan=False, separators=(",", ":"), sort_keys=True)


def fingerprint_payload(
    kind: FingerprintKind, payload: Mapping[str, object]
) -> ReproducibilityFingerprint:
    """Return a reproducibility fingerprint for a canonical JSON payload."""
    normalized_payload = {
        "schema_version": FINGERPRINT_SCHEMA_VERSION,
        "kind": kind,
        "payload": dict(payload),
    }
    digest = sha256(canonical_json_payload(normalized_payload).encode()).hexdigest()
    return ReproducibilityFingerprint(
        kind=kind,
        digest_sha256=digest,
        payload=normalized_payload,
    )


def simulation_result_payload(result: SimulationResult) -> dict[str, object]:
    """Return a canonical payload for a simulation result."""
    return {
        "times_bce": [float(time_bce) for time_bce in result.times_bce],
        "states": [population_state_payload(state) for state in result.states],
    }


def fingerprint_simulation_result(
    result: SimulationResult,
) -> ReproducibilityFingerprint:
    """Return a reproducibility fingerprint for a simulation result."""
    return fingerprint_payload("simulation_result", simulation_result_payload(result))


def sweep_run_payload(run: SweepRun) -> dict[str, object]:
    """Return a canonical payload for one sweep run."""
    return {
        "index": run.index,
        "sampled_values": _sorted_numeric_mapping(run.sampled_values),
        "parameters": simulation_parameters_payload(run.parameters),
        "summary": trajectory_summary_payload(run.summary),
    }


def fingerprint_sweep_run(run: SweepRun) -> ReproducibilityFingerprint:
    """Return a reproducibility fingerprint for one sweep run."""
    return fingerprint_payload("sweep_run", sweep_run_payload(run))


def sweep_collection_payload(runs: Iterable[SweepRun]) -> dict[str, object]:
    """Return a canonical payload for a collection of sweep runs."""
    run_tuple = tuple(runs)
    if not run_tuple:
        raise ValueError("runs must contain at least one sweep run")
    return {
        "runs": [sweep_run_payload(run) for run in run_tuple],
    }


def fingerprint_sweep_collection(
    runs: Iterable[SweepRun],
) -> ReproducibilityFingerprint:
    """Return a reproducibility fingerprint for a sweep run collection."""
    return fingerprint_payload("sweep_collection", sweep_collection_payload(runs))


def population_state_payload(state: PopulationState) -> dict[str, object]:
    """Return a canonical payload for a population state."""
    return {
        "regions": [
            {
                "region": region,
                "sources": [
                    {"source": source, "count": source_counts[source]}
                    for source in sorted(source_counts)
                ],
            }
            for region, source_counts in sorted(state.counts.items())
        ]
    }


def simulation_parameters_payload(
    parameters: SimulationParameters,
) -> dict[str, object]:
    """Return a canonical payload for simulation parameters."""
    return {
        parameter_field.name: float(getattr(parameters, parameter_field.name))
        for parameter_field in fields(SimulationParameters)
    }


def trajectory_summary_payload(summary: TrajectorySummary) -> dict[str, object]:
    """Return a canonical payload for a trajectory summary."""
    return {
        "source": summary.source,
        "region": summary.region or "",
        "start_bce": summary.start_bce,
        "end_bce": summary.end_bce,
        "initial_ancestry": summary.initial_ancestry,
        "final_ancestry": summary.final_ancestry,
        "ancestry_delta": summary.ancestry_delta,
        "ancestry_slope_per_century": summary.ancestry_slope_per_century,
        "min_total_population": summary.min_total_population,
        "final_total_population": summary.final_total_population,
        "is_extinct": summary.is_extinct,
    }


def _sorted_numeric_mapping(values: Mapping[str, float]) -> list[dict[str, object]]:
    """Return sorted numeric key-value pairs for canonical payloads."""
    return [{"name": name, "value": values[name]} for name in sorted(values)]
