"""Output provenance records for simulation and target reporting."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from typing import Literal

from indoeuropop.fitting import TargetFit
from indoeuropop.summary import TrajectorySummary
from indoeuropop.targets import TargetObservation

RecordKind = Literal["simulated", "observed", "synthetic", "derived", "inferred"]
RecordValue = bool | float | str

RECORD_KINDS = frozenset({"simulated", "observed", "synthetic", "derived", "inferred"})


@dataclass(frozen=True)
class ProvenanceRecord:
    """One typed value with explicit output provenance.

    The record kind separates simulated values, observed or synthetic targets,
    derived diagnostics, and later inferred values. This prevents reports from
    silently mixing fundamentally different evidence statuses.
    """

    name: str
    kind: RecordKind
    value: RecordValue
    unit: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and normalize record fields."""
        if not self.name:
            raise ValueError("name must be non-empty")
        if self.kind not in RECORD_KINDS:
            raise ValueError("kind is not supported")
        _validate_record_value(self.value)
        normalized_metadata = _normalized_metadata(self.metadata)
        object.__setattr__(self, "metadata", normalized_metadata)

    def to_flat_row(self) -> dict[str, str]:
        """Return a string-only row suitable for CSV or markdown tables."""
        row = {
            "kind": self.kind,
            "name": self.name,
            "value": _value_text(self.value),
            "unit": self.unit,
        }
        for key, value in self.metadata.items():
            row[f"metadata_{key}"] = value
        return row


def summary_provenance_records(
    summary: TrajectorySummary,
) -> tuple[ProvenanceRecord, ...]:
    """Return simulated provenance records for one trajectory summary."""
    metadata = _trajectory_metadata(summary)
    return (
        ProvenanceRecord(
            name="initial_ancestry",
            kind="simulated",
            value=summary.initial_ancestry,
            unit="proportion",
            metadata=metadata,
        ),
        ProvenanceRecord(
            name="final_ancestry",
            kind="simulated",
            value=summary.final_ancestry,
            unit="proportion",
            metadata=metadata,
        ),
        ProvenanceRecord(
            name="ancestry_delta",
            kind="simulated",
            value=summary.ancestry_delta,
            unit="proportion",
            metadata=metadata,
        ),
        ProvenanceRecord(
            name="ancestry_slope_per_century",
            kind="simulated",
            value=summary.ancestry_slope_per_century,
            unit="proportion_per_century",
            metadata=metadata,
        ),
        ProvenanceRecord(
            name="min_total_population",
            kind="simulated",
            value=summary.min_total_population,
            unit="count",
            metadata=metadata,
        ),
        ProvenanceRecord(
            name="final_total_population",
            kind="simulated",
            value=summary.final_total_population,
            unit="count",
            metadata=metadata,
        ),
        ProvenanceRecord(
            name="is_extinct",
            kind="simulated",
            value=summary.is_extinct,
            unit="boolean",
            metadata=metadata,
        ),
    )


def target_observation_provenance_records(
    observation: TargetObservation,
) -> tuple[ProvenanceRecord, ...]:
    """Return provenance records for one target observation."""
    metadata = {
        "region": observation.region,
        "source": observation.source,
        "time_bce": _value_text(observation.time_bce),
        "citation_key": observation.citation_key,
        "status": observation.status,
    }
    kind: RecordKind = "observed" if observation.status == "published" else "synthetic"
    return (
        ProvenanceRecord(
            name="target_mean",
            kind=kind,
            value=observation.mean,
            unit="proportion",
            metadata=metadata,
        ),
        ProvenanceRecord(
            name="target_uncertainty",
            kind=kind,
            value=observation.uncertainty,
            unit="proportion",
            metadata=metadata,
        ),
    )


def target_fit_provenance_records(fit: TargetFit) -> tuple[ProvenanceRecord, ...]:
    """Return derived provenance records for target-fit metrics."""
    metadata = {"observation_count": str(fit.observation_count)}
    return (
        ProvenanceRecord(
            name="mean_absolute_error",
            kind="derived",
            value=fit.mean_absolute_error,
            unit="proportion",
            metadata=metadata,
        ),
        ProvenanceRecord(
            name="root_mean_squared_error",
            kind="derived",
            value=fit.root_mean_squared_error,
            unit="proportion",
            metadata=metadata,
        ),
        ProvenanceRecord(
            name="chi_square",
            kind="derived",
            value=fit.chi_square,
            unit="score",
            metadata=metadata,
        ),
        ProvenanceRecord(
            name="reduced_chi_square",
            kind="derived",
            value=fit.reduced_chi_square,
            unit="score",
            metadata=metadata,
        ),
        ProvenanceRecord(
            name="max_abs_z_score",
            kind="derived",
            value=fit.max_abs_z_score,
            unit="score",
            metadata=metadata,
        ),
    )


def _trajectory_metadata(summary: TrajectorySummary) -> dict[str, str]:
    """Return shared metadata for trajectory summary records."""
    return {
        "source": summary.source,
        "region": summary.region or "all",
        "start_bce": _value_text(summary.start_bce),
        "end_bce": _value_text(summary.end_bce),
    }


def _validate_record_value(value: RecordValue) -> None:
    """Validate a provenance record value."""
    if isinstance(value, bool):
        return
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("numeric values must be finite")
        return
    if isinstance(value, str) and value:
        return
    raise ValueError("value must be a finite number, boolean, or non-empty string")


def _normalized_metadata(metadata: Mapping[str, str]) -> dict[str, str]:
    """Return metadata as a plain dict after validating keys and values."""
    normalized: dict[str, str] = {}
    for key, value in metadata.items():
        if not key:
            raise ValueError("metadata keys must be non-empty")
        normalized[key] = str(value)
    return normalized


def _value_text(value: RecordValue) -> str:
    """Return a stable string representation for record values."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.12g}"
    return value
