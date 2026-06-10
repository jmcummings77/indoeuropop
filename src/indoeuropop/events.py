"""Time-bounded events that can modify simulation parameters."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite

from indoeuropop.models import SimulationParameters

STEPPE_SOURCE = "steppe"


def _finite(name: str, value: float) -> float:
    """Return a finite numeric value or raise a validation error."""
    numeric_value = float(value)
    if not isfinite(numeric_value):
        raise ValueError(f"{name} must be finite")
    return numeric_value


def _probability(name: str, value: float) -> float:
    """Return a probability value on the inclusive interval [0, 1]."""
    numeric_value = _finite(name, value)
    if numeric_value < 0 or numeric_value > 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return numeric_value


@dataclass(frozen=True)
class TimeWindow:
    """A BCE time interval with inclusive bounds."""

    start_bce: float
    end_bce: float

    def __post_init__(self) -> None:
        """Validate that the BCE interval moves forward through elapsed time."""
        start_bce = _finite("start_bce", self.start_bce)
        end_bce = _finite("end_bce", self.end_bce)
        if start_bce <= end_bce:
            raise ValueError("start_bce must be greater than end_bce")
        object.__setattr__(self, "start_bce", start_bce)
        object.__setattr__(self, "end_bce", end_bce)

    def contains(self, time_bce: float) -> bool:
        """Return whether a BCE time lies inside the inclusive window."""
        checked_time = _finite("time_bce", time_bce)
        return self.start_bce >= checked_time >= self.end_bce


@dataclass(frozen=True)
class MigrationPulse:
    """An additive incoming migration rate for one modeled region."""

    region: str
    start_bce: float
    end_bce: float
    annual_rate: float
    source: str = STEPPE_SOURCE

    def __post_init__(self) -> None:
        """Validate pulse metadata and rate values."""
        if not self.region:
            raise ValueError("region must be non-empty")
        if self.source != STEPPE_SOURCE:
            raise ValueError("only steppe migration pulses are supported in v1")
        _ = TimeWindow(self.start_bce, self.end_bce)
        object.__setattr__(
            self, "annual_rate", _probability("annual_rate", self.annual_rate)
        )

    @property
    def window(self) -> TimeWindow:
        """Return this pulse's active time window."""
        return TimeWindow(self.start_bce, self.end_bce)

    def applies_to(self, *, region: str, source: str, time_bce: float) -> bool:
        """Return whether the pulse applies to a region/source/time tuple."""
        return (
            self.region == region
            and self.source == source
            and self.window.contains(time_bce)
        )


@dataclass(frozen=True)
class ForcingWindow:
    """A time-bounded additive climate and epidemic stress event."""

    start_bce: float
    end_bce: float
    climate_stress_delta: float = 0.0
    epidemic_mortality_delta: float = 0.0

    def __post_init__(self) -> None:
        """Validate forcing window bounds and deltas."""
        _ = TimeWindow(self.start_bce, self.end_bce)
        object.__setattr__(
            self,
            "climate_stress_delta",
            _probability("climate_stress_delta", self.climate_stress_delta),
        )
        object.__setattr__(
            self,
            "epidemic_mortality_delta",
            _probability("epidemic_mortality_delta", self.epidemic_mortality_delta),
        )

    @property
    def window(self) -> TimeWindow:
        """Return this forcing event's active time window."""
        return TimeWindow(self.start_bce, self.end_bce)

    def active_at(self, time_bce: float) -> bool:
        """Return whether this forcing event is active at a BCE time."""
        return self.window.contains(time_bce)


@dataclass(frozen=True)
class SimulationSchedule:
    """Time-bounded events layered on top of base simulation parameters."""

    migration_pulses: tuple[MigrationPulse, ...] = ()
    forcing_windows: tuple[ForcingWindow, ...] = ()

    def migration_rate_for(self, *, region: str, source: str, time_bce: float) -> float:
        """Return additive migration pressure for a region/source/time tuple."""
        return sum(
            pulse.annual_rate
            for pulse in self.migration_pulses
            if pulse.applies_to(region=region, source=source, time_bce=time_bce)
        )

    def effective_parameters(
        self, parameters: SimulationParameters, time_bce: float
    ) -> SimulationParameters:
        """Return base parameters after active forcing windows are applied."""
        active_windows = [
            forcing for forcing in self.forcing_windows if forcing.active_at(time_bce)
        ]
        climate_stress = min(
            1.0,
            parameters.climate_stress
            + sum(forcing.climate_stress_delta for forcing in active_windows),
        )
        epidemic_mortality_rate = min(
            1.0,
            parameters.epidemic_mortality_rate
            + sum(forcing.epidemic_mortality_delta for forcing in active_windows),
        )
        return replace(
            parameters,
            climate_stress=climate_stress,
            epidemic_mortality_rate=epidemic_mortality_rate,
        )
