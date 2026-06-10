"""Seeded parameter sweeps for deterministic scenario exploration."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from math import isfinite
from typing import Any, cast

import numpy as np

from indoeuropop.events import SimulationSchedule
from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.parameterization import ParameterSet
from indoeuropop.simulation import run_deterministic
from indoeuropop.summary import TrajectorySummary, summarize_trajectory

PARAMETER_FIELD_NAMES = frozenset(field.name for field in fields(SimulationParameters))


@dataclass(frozen=True)
class ParameterRange:
    """A closed numeric sampling interval for one SimulationParameters field."""

    name: str
    low: float
    high: float

    def __post_init__(self) -> None:
        """Validate range metadata and bounds."""
        if self.name not in PARAMETER_FIELD_NAMES:
            raise ValueError(f"unknown simulation parameter: {self.name}")
        low = float(self.low)
        high = float(self.high)
        if not isfinite(low) or not isfinite(high):
            raise ValueError("range bounds must be finite")
        if low > high:
            raise ValueError("low must be less than or equal to high")
        object.__setattr__(self, "low", low)
        object.__setattr__(self, "high", high)

    def scale(self, unit_value: float) -> float:
        """Map a unit interval value onto this range."""
        if unit_value < 0 or unit_value > 1:
            raise ValueError("unit_value must be between 0 and 1")
        return self.low + unit_value * (self.high - self.low)


@dataclass(frozen=True)
class SweepSpec:
    """Configuration for a deterministic Latin-hypercube parameter sweep."""

    initial_state: PopulationState
    base_parameters: SimulationParameters
    parameter_ranges: tuple[ParameterRange, ...]
    start_bce: float = 3500.0
    end_bce: float = 1500.0
    step_years: float = 25.0
    sample_count: int = 8
    seed: int = 7
    source: str = "steppe"
    region: str | None = None
    schedule: SimulationSchedule = field(default_factory=SimulationSchedule)
    parameter_set: ParameterSet = field(default_factory=ParameterSet)

    def __post_init__(self) -> None:
        """Validate sweep dimensions and parameter names."""
        if self.sample_count <= 0:
            raise ValueError("sample_count must be positive")
        if not self.parameter_ranges:
            raise ValueError("parameter_ranges must not be empty")
        names = [parameter_range.name for parameter_range in self.parameter_ranges]
        if len(names) != len(set(names)):
            raise ValueError("parameter_ranges must not contain duplicate names")


@dataclass(frozen=True)
class SweepRun:
    """One sampled parameter set and its resulting trajectory summary."""

    index: int
    sampled_values: dict[str, float]
    parameters: SimulationParameters
    summary: TrajectorySummary


def latin_hypercube_samples(
    parameter_ranges: tuple[ParameterRange, ...], *, sample_count: int, seed: int
) -> tuple[dict[str, float], ...]:
    """Return seeded Latin-hypercube samples for parameter ranges.

    Each parameter is stratified into `sample_count` bins and independently
    shuffled, which keeps small exploratory sweeps reproducible while covering
    every one-dimensional range more evenly than plain random sampling.
    """
    if sample_count <= 0:
        raise ValueError("sample_count must be positive")
    if not parameter_ranges:
        raise ValueError("parameter_ranges must not be empty")

    random_generator = np.random.default_rng(seed)
    unit_samples: dict[str, np.ndarray[Any, np.dtype[np.float64]]] = {}
    for parameter_range in parameter_ranges:
        bin_offsets = np.arange(sample_count) + random_generator.random(sample_count)
        shuffled = bin_offsets / sample_count
        random_generator.shuffle(shuffled)
        unit_samples[parameter_range.name] = shuffled

    samples: list[dict[str, float]] = []
    for sample_index in range(sample_count):
        samples.append(
            {
                parameter_range.name: parameter_range.scale(
                    float(unit_samples[parameter_range.name][sample_index])
                )
                for parameter_range in parameter_ranges
            }
        )
    return tuple(samples)


def run_parameter_sweep(spec: SweepSpec) -> tuple[SweepRun, ...]:
    """Run deterministic simulations for a Latin-hypercube sweep spec."""
    sampled_values = latin_hypercube_samples(
        spec.parameter_ranges, sample_count=spec.sample_count, seed=spec.seed
    )
    runs: list[SweepRun] = []
    for index, values in enumerate(sampled_values):
        parameters = _parameters_with_overrides(spec.base_parameters, values)
        result = run_deterministic(
            spec.initial_state,
            parameters,
            start_bce=spec.start_bce,
            end_bce=spec.end_bce,
            step_years=spec.step_years,
            schedule=spec.schedule,
            parameter_set=spec.parameter_set,
        )
        runs.append(
            SweepRun(
                index=index,
                sampled_values=values,
                parameters=parameters,
                summary=summarize_trajectory(
                    result, source=spec.source, region=spec.region
                ),
            )
        )
    return tuple(runs)


def _parameters_with_overrides(
    parameters: SimulationParameters, values: dict[str, float]
) -> SimulationParameters:
    """Return a SimulationParameters object with sampled field values applied."""
    raw_parameters = {
        field.name: getattr(parameters, field.name)
        for field in fields(SimulationParameters)
    }
    raw_parameters.update(values)
    return SimulationParameters(**cast(Any, raw_parameters))
