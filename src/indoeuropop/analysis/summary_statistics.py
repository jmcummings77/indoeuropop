"""Reusable summary-statistic vectors for simulation comparison."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isfinite, sqrt

from indoeuropop.analysis.summary import TrajectorySummary


@dataclass(frozen=True)
class SummaryStatistic:
    """One named numeric statistic with an optional comparison scale."""

    name: str
    value: float
    scale: float = 1.0

    def __post_init__(self) -> None:
        """Validate statistic name, value, and scale."""
        if not self.name:
            raise ValueError("summary statistic names must be non-empty")
        numeric_value = float(self.value)
        numeric_scale = float(self.scale)
        if not isfinite(numeric_value):
            raise ValueError("summary statistic values must be finite")
        if not isfinite(numeric_scale) or numeric_scale <= 0:
            raise ValueError("summary statistic scales must be positive and finite")
        object.__setattr__(self, "value", numeric_value)
        object.__setattr__(self, "scale", numeric_scale)

    @property
    def normalized_value(self) -> float:
        """Return this statistic divided by its comparison scale."""
        return self.value / self.scale


@dataclass(frozen=True)
class SummaryVector:
    """A named, validated collection of summary statistics."""

    statistics: tuple[SummaryStatistic, ...]

    def __post_init__(self) -> None:
        """Validate that the vector is non-empty and has unique names."""
        if not self.statistics:
            raise ValueError("summary vectors must contain at least one statistic")
        names = [statistic.name for statistic in self.statistics]
        if len(names) != len(set(names)):
            raise ValueError("summary statistic names must be unique")

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, float],
        *,
        scales: Mapping[str, float] | None = None,
    ) -> SummaryVector:
        """Build a summary vector from statistic values and optional scales."""
        scale_map = scales or {}
        return cls(
            tuple(
                SummaryStatistic(name=name, value=value, scale=scale_map.get(name, 1.0))
                for name, value in values.items()
            )
        )

    def names(self) -> tuple[str, ...]:
        """Return statistic names in deterministic vector order."""
        return tuple(statistic.name for statistic in self.statistics)

    def as_dict(self) -> dict[str, float]:
        """Return raw statistic values keyed by statistic name."""
        return {statistic.name: statistic.value for statistic in self.statistics}

    def statistic(self, name: str) -> SummaryStatistic:
        """Return one statistic by name."""
        for statistic in self.statistics:
            if statistic.name == name:
                return statistic
        raise KeyError(name)

    def value(self, name: str) -> float:
        """Return one raw statistic value by name."""
        return self.statistic(name).value

    def normalized_values(
        self, names: Iterable[str] | None = None
    ) -> tuple[float, ...]:
        """Return normalized values for selected names or the full vector."""
        selected_names = _selected_names(self.names(), names)
        return tuple(self.statistic(name).normalized_value for name in selected_names)

    def root_mean_square_distance(
        self, other: SummaryVector, names: Iterable[str] | None = None
    ) -> float:
        """Return scaled root-mean-square distance to another summary vector.

        The scale attached to this vector is used for each selected statistic.
        This keeps comparisons explicit while avoiding any claim that the
        distance is a likelihood or posterior probability.
        """
        selected_names = _selected_names(self.names(), names)
        squared_differences = []
        for name in selected_names:
            statistic = self.statistic(name)
            other_value = other.value(name)
            squared_differences.append(
                ((statistic.value - other_value) / statistic.scale) ** 2
            )
        return sqrt(sum(squared_differences) / len(squared_differences))


def trajectory_summary_vector(
    summary: TrajectorySummary,
    *,
    scales: Mapping[str, float] | None = None,
    include_extinction: bool = True,
) -> SummaryVector:
    """Return reusable numeric summary statistics from a trajectory summary."""
    values = {
        "initial_ancestry": summary.initial_ancestry,
        "final_ancestry": summary.final_ancestry,
        "ancestry_delta": summary.ancestry_delta,
        "ancestry_slope_per_century": summary.ancestry_slope_per_century,
        "min_total_population": summary.min_total_population,
        "final_total_population": summary.final_total_population,
    }
    if include_extinction:
        values["is_extinct"] = 1.0 if summary.is_extinct else 0.0
    return SummaryVector.from_mapping(values, scales=scales)


def _selected_names(
    available_names: tuple[str, ...], selected_names: Iterable[str] | None
) -> tuple[str, ...]:
    """Return selected statistic names after validating the selection."""
    names = available_names if selected_names is None else tuple(selected_names)
    if not names:
        raise ValueError("at least one summary statistic name must be selected")
    unknown_names = set(names).difference(available_names)
    if unknown_names:
        unknown_text = ", ".join(sorted(unknown_names))
        raise KeyError(f"unknown summary statistics: {unknown_text}")
    return names
