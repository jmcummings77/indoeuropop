"""Debugging helpers for comparing simulation trajectories."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from indoeuropop.events import SimulationSchedule
from indoeuropop.models import PopulationState, SimulationParameters, SimulationResult
from indoeuropop.parameterization import ParameterSet
from indoeuropop.simulation import run_deterministic, run_tau_leap


@dataclass(frozen=True)
class AncestryComparison:
    """Pointwise comparison between two ancestry trajectories."""

    first_label: str
    second_label: str
    source: str
    region: str | None
    times_bce: tuple[float, ...]
    first_ancestry: tuple[float, ...]
    second_ancestry: tuple[float, ...]
    differences: tuple[float, ...]
    max_abs_difference: float
    final_difference: float
    root_mean_squared_difference: float


def compare_ancestry_trajectories(
    first: SimulationResult,
    second: SimulationResult,
    *,
    source: str = "steppe",
    region: str | None = None,
    first_label: str = "first",
    second_label: str = "second",
) -> AncestryComparison:
    """Compare two simulation results on a shared ancestry trajectory.

    The two results must use identical BCE time labels. Keeping this strict
    avoids hiding interpolation choices inside debugging summaries.
    """
    if first.times_bce != second.times_bce:
        raise ValueError("simulation results must share identical times_bce")

    first_ancestry = _ancestry_tuple(first, source=source, region=region)
    second_ancestry = _ancestry_tuple(second, source=source, region=region)
    differences = tuple(
        second_value - first_value
        for first_value, second_value in zip(
            first_ancestry, second_ancestry, strict=True
        )
    )
    max_abs_difference = max(abs(difference) for difference in differences)
    root_mean_squared_difference = sqrt(
        sum(difference**2 for difference in differences) / len(differences)
    )
    return AncestryComparison(
        first_label=first_label,
        second_label=second_label,
        source=source,
        region=region,
        times_bce=first.times_bce,
        first_ancestry=first_ancestry,
        second_ancestry=second_ancestry,
        differences=differences,
        max_abs_difference=max_abs_difference,
        final_difference=differences[-1],
        root_mean_squared_difference=root_mean_squared_difference,
    )


def compare_deterministic_and_tau_leap(
    initial_state: PopulationState,
    parameters: SimulationParameters,
    *,
    source: str = "steppe",
    region: str | None = None,
    start_bce: float = 3500.0,
    end_bce: float = 1500.0,
    step_years: float = 25.0,
    seed: int = 7,
    schedule: SimulationSchedule | None = None,
    parameter_set: ParameterSet | None = None,
) -> AncestryComparison:
    """Run deterministic and tau-leap simulations and compare ancestry output."""
    deterministic = run_deterministic(
        initial_state,
        parameters,
        start_bce=start_bce,
        end_bce=end_bce,
        step_years=step_years,
        schedule=schedule,
        parameter_set=parameter_set,
    )
    tau_leap = run_tau_leap(
        initial_state,
        parameters,
        start_bce=start_bce,
        end_bce=end_bce,
        step_years=step_years,
        seed=seed,
        schedule=schedule,
        parameter_set=parameter_set,
    )
    return compare_ancestry_trajectories(
        deterministic,
        tau_leap,
        source=source,
        region=region,
        first_label="deterministic",
        second_label="tau_leap",
    )


def _ancestry_tuple(
    result: SimulationResult, *, source: str, region: str | None
) -> tuple[float, ...]:
    """Return a simulation ancestry series as plain Python floats."""
    return tuple(float(value) for value in result.ancestry_series(source, region))
