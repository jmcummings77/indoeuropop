"""Core typed data structures for population dynamics simulations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite

import numpy as np
from numpy.typing import NDArray

CountsByRegion = dict[str, dict[str, float]]


def _require_finite_non_negative(name: str, value: float) -> float:
    """Return a numeric value after validating it is finite and non-negative."""
    numeric_value = float(value)
    if not isfinite(numeric_value) or numeric_value < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return numeric_value


def _require_probability(name: str, value: float) -> float:
    """Return a numeric value after validating it is a probability."""
    numeric_value = _require_finite_non_negative(name, value)
    if numeric_value > 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return numeric_value


@dataclass(frozen=True)
class PopulationState:
    """Population counts indexed by region and ancestry/source label.

    The model deliberately stores counts rather than ancestry proportions. A
    symbol such as `a_s` in later equations should be computed from these counts
    so demographic processes cannot bypass the underlying state.
    """

    counts: Mapping[str, Mapping[str, float]]

    def __post_init__(self) -> None:
        """Validate and normalize nested count mappings."""
        if not self.counts:
            raise ValueError("counts must contain at least one region")

        normalized: CountsByRegion = {}
        for region, source_counts in self.counts.items():
            if not region:
                raise ValueError("region names must be non-empty")
            if not source_counts:
                raise ValueError(f"{region} must contain at least one source")
            normalized[region] = {
                source: _require_finite_non_negative(
                    f"counts[{region!r}][{source!r}]", value
                )
                for source, value in source_counts.items()
            }
            if any(source == "" for source in normalized[region]):
                raise ValueError("source names must be non-empty")

        object.__setattr__(self, "counts", normalized)

    def regions(self) -> tuple[str, ...]:
        """Return the region labels in deterministic insertion order."""
        return tuple(self.counts)

    def sources(self, region: str | None = None) -> tuple[str, ...]:
        """Return source labels for one region or all regions."""
        if region is not None:
            return tuple(self.counts[region])

        ordered_sources: list[str] = []
        for source_counts in self.counts.values():
            for source in source_counts:
                if source not in ordered_sources:
                    ordered_sources.append(source)
        return tuple(ordered_sources)

    def total(self, region: str | None = None) -> float:
        """Return the total population count for a region or all regions."""
        if region is not None:
            return sum(self.counts[region].values())
        return sum(
            sum(source_counts.values()) for source_counts in self.counts.values()
        )

    def source_total(self, source: str, region: str | None = None) -> float:
        """Return a source count in one region or across all regions."""
        if region is not None:
            return self.counts[region].get(source, 0.0)
        return sum(
            source_counts.get(source, 0.0) for source_counts in self.counts.values()
        )

    def ancestry_proportion(self, source: str, region: str | None = None) -> float:
        """Return the proportion of a population assigned to a source label."""
        denominator = self.total(region)
        if denominator == 0:
            return 0.0
        return self.source_total(source, region) / denominator


@dataclass(frozen=True)
class SimulationParameters:
    """Validated scalar parameters for the first mean-field model.

    Rates are annual probabilities in this scaffold. More detailed phases can
    replace these globals with source-specific tables without changing the
    public state representation.
    """

    fertility_rate: float = 0.035
    local_mortality_rate: float = 0.030
    steppe_mortality_rate: float = 0.028
    migration_rate: float = 0.002
    epidemic_mortality_rate: float = 0.0
    local_epidemic_risk: float = 1.0
    steppe_epidemic_risk: float = 0.5
    violence_mortality_rate: float = 0.0
    climate_stress: float = 0.0
    elite_reproductive_advantage: float = 1.0

    def __post_init__(self) -> None:
        """Validate all rate and multiplier fields."""
        probability_fields = (
            "fertility_rate",
            "local_mortality_rate",
            "steppe_mortality_rate",
            "migration_rate",
            "epidemic_mortality_rate",
            "local_epidemic_risk",
            "steppe_epidemic_risk",
            "violence_mortality_rate",
            "climate_stress",
        )
        for field_name in probability_fields:
            object.__setattr__(
                self,
                field_name,
                _require_probability(field_name, getattr(self, field_name)),
            )

        elite_value = _require_finite_non_negative(
            "elite_reproductive_advantage", self.elite_reproductive_advantage
        )
        if elite_value < 1:
            raise ValueError("elite_reproductive_advantage must be at least 1")
        object.__setattr__(self, "elite_reproductive_advantage", elite_value)


@dataclass(frozen=True)
class SimulationResult:
    """Time series returned by a population simulation."""

    times_bce: tuple[float, ...]
    states: tuple[PopulationState, ...]

    def __post_init__(self) -> None:
        """Validate that times and states form a non-empty time series."""
        if not self.times_bce:
            raise ValueError("times_bce must not be empty")
        if len(self.times_bce) != len(self.states):
            raise ValueError("times_bce and states must have the same length")
        for time_bce in self.times_bce:
            if not isfinite(time_bce):
                raise ValueError("times_bce values must be finite")

    @property
    def final_state(self) -> PopulationState:
        """Return the final population state."""
        return self.states[-1]

    def ancestry_series(
        self, source: str, region: str | None = None
    ) -> NDArray[np.float64]:
        """Return ancestry proportions for each recorded time."""
        return np.array(
            [state.ancestry_proportion(source, region) for state in self.states],
            dtype=np.float64,
        )

    def total_series(self, region: str | None = None) -> NDArray[np.float64]:
        """Return total population counts for each recorded time."""
        return np.array(
            [state.total(region) for state in self.states],
            dtype=np.float64,
        )
