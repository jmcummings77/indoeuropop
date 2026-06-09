"""Target ancestry observations and simulation comparison helpers."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Literal, cast

import numpy as np

from indoeuropop.models import SimulationResult

ObservationStatus = Literal["synthetic", "published"]

REQUIRED_TARGET_COLUMNS = frozenset(
    {
        "status",
        "region",
        "source",
        "time_bce",
        "mean",
        "uncertainty",
        "citation_key",
        "citation",
        "note",
    }
)


@dataclass(frozen=True)
class TargetObservation:
    """One ancestry target with citation metadata.

    `mean` and `uncertainty` are proportions on the inclusive interval [0, 1].
    The initial scaffold uses broad ancestry-source labels rather than genotype
    data so target values remain explicitly separate from simulator logic.
    """

    status: ObservationStatus
    region: str
    source: str
    time_bce: float
    mean: float
    uncertainty: float
    citation_key: str
    citation: str
    note: str = ""

    def __post_init__(self) -> None:
        """Validate target fields before they enter an inference workflow."""
        if self.status not in ("synthetic", "published"):
            raise ValueError("status must be 'synthetic' or 'published'")
        for field_name in ("region", "source", "citation_key", "citation"):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must be non-empty")
        if not isfinite(self.time_bce):
            raise ValueError("time_bce must be finite")
        if not isfinite(self.mean) or not 0 <= self.mean <= 1:
            raise ValueError("mean must be a finite proportion")
        if not isfinite(self.uncertainty) or not 0 < self.uncertainty <= 1:
            raise ValueError("uncertainty must be a positive finite proportion")

    @property
    def lower_bound(self) -> float:
        """Return the lower one-sigma bound clipped to zero."""
        return max(0.0, self.mean - self.uncertainty)

    @property
    def upper_bound(self) -> float:
        """Return the upper one-sigma bound clipped to one."""
        return min(1.0, self.mean + self.uncertainty)


@dataclass(frozen=True)
class TargetComparison:
    """Comparison between one target observation and one simulated trajectory."""

    observation: TargetObservation
    predicted: float

    @property
    def residual(self) -> float:
        """Return predicted minus observed ancestry."""
        return self.predicted - self.observation.mean

    @property
    def z_score(self) -> float:
        """Return the residual scaled by observation uncertainty."""
        return self.residual / self.observation.uncertainty


@dataclass(frozen=True)
class TargetDataset:
    """A validated collection of target observations."""

    observations: tuple[TargetObservation, ...]

    @classmethod
    def from_rows(cls, rows: Iterable[TargetObservation]) -> TargetDataset:
        """Build a dataset from an iterable of already validated observations."""
        return cls(tuple(rows))

    def require_observations(self) -> TargetDataset:
        """Return this dataset after checking it contains at least one row."""
        if not self.observations:
            raise ValueError("target dataset must contain at least one observation")
        return self

    def regions(self) -> tuple[str, ...]:
        """Return unique region labels in observation order."""
        return _unique(observation.region for observation in self.observations)

    def sources(self) -> tuple[str, ...]:
        """Return unique source labels in observation order."""
        return _unique(observation.source for observation in self.observations)

    def filter(
        self,
        *,
        region: str | None = None,
        source: str | None = None,
        status: ObservationStatus | None = None,
    ) -> TargetDataset:
        """Return observations matching optional region, source, and status."""
        return TargetDataset.from_rows(
            observation
            for observation in self.observations
            if (region is None or observation.region == region)
            and (source is None or observation.source == source)
            and (status is None or observation.status == status)
        )

    def compare(self, result: SimulationResult) -> tuple[TargetComparison, ...]:
        """Compare every target to interpolated simulation ancestry."""
        return tuple(
            TargetComparison(
                observation=observation,
                predicted=_interpolated_ancestry(result, observation),
            )
            for observation in self.observations
        )


def load_target_dataset(path: str | Path) -> TargetDataset:
    """Load target observations from a CSV file with citation metadata."""
    target_path = Path(path)
    with target_path.open(newline="", encoding="utf-8") as target_file:
        reader = csv.DictReader(target_file)
        if reader.fieldnames is None:
            raise ValueError("target CSV must include a header row")

        missing_columns = REQUIRED_TARGET_COLUMNS.difference(reader.fieldnames)
        if missing_columns:
            missing_text = ", ".join(sorted(missing_columns))
            raise ValueError(f"target CSV missing columns: {missing_text}")

        observations = [
            _observation_from_row(row, line_number)
            for line_number, row in enumerate(reader, start=2)
        ]

    return TargetDataset.from_rows(observations).require_observations()


def _observation_from_row(
    row: dict[str, str | None], line_number: int
) -> TargetObservation:
    """Convert one CSV row into a target observation with line-aware errors."""
    try:
        status = _status(_cell(row, "status"))
        return TargetObservation(
            status=status,
            region=_cell(row, "region"),
            source=_cell(row, "source"),
            time_bce=float(_cell(row, "time_bce")),
            mean=float(_cell(row, "mean")),
            uncertainty=float(_cell(row, "uncertainty")),
            citation_key=_cell(row, "citation_key"),
            citation=_cell(row, "citation"),
            note=_cell(row, "note"),
        )
    except ValueError as error:
        raise ValueError(f"invalid target CSV row {line_number}: {error}") from error


def _cell(row: dict[str, str | None], column: str) -> str:
    """Return a stripped CSV cell or raise for blank required values."""
    value = row.get(column)
    if value is None or value.strip() == "":
        raise ValueError(f"{column} is required")
    return value.strip()


def _status(value: str) -> ObservationStatus:
    """Validate a CSV status cell."""
    if value not in ("synthetic", "published"):
        raise ValueError("status must be 'synthetic' or 'published'")
    return cast(ObservationStatus, value)


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    """Return unique strings while preserving insertion order."""
    unique_values: list[str] = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)
    return tuple(unique_values)


def _interpolated_ancestry(
    result: SimulationResult, observation: TargetObservation
) -> float:
    """Return simulated ancestry at an observation time using linear interpolation."""
    times = np.array(result.times_bce, dtype=np.float64)
    series = result.ancestry_series(observation.source, observation.region)
    sorted_indices = np.argsort(times)
    sorted_times = times[sorted_indices]

    if (
        observation.time_bce < sorted_times[0]
        or observation.time_bce > sorted_times[-1]
    ):
        raise ValueError("target time is outside the simulation time range")

    return float(np.interp(observation.time_bce, sorted_times, series[sorted_indices]))
