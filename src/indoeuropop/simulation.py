"""Deterministic and tau-leap simulation routines."""

from __future__ import annotations

from math import ceil

import numpy as np
from numpy.random import Generator

from indoeuropop.events import SimulationSchedule
from indoeuropop.models import PopulationState, SimulationParameters, SimulationResult
from indoeuropop.parameterization import (
    ParameterSet,
    ResolvedSourceParameters,
)

LOCAL_SOURCE = "local"
STEPPE_SOURCE = "steppe"


def run_deterministic(
    initial_state: PopulationState,
    parameters: SimulationParameters,
    *,
    start_bce: float = 3500.0,
    end_bce: float = 1500.0,
    step_years: float = 25.0,
    schedule: SimulationSchedule | None = None,
    parameter_set: ParameterSet | None = None,
) -> SimulationResult:
    """Run a deterministic mean-field simulation.

    The implementation uses elapsed years internally while storing BCE labels in
    the result. This avoids the common bug where adding time steps to a BCE year
    accidentally moves the simulation backward from its intended end date.
    """
    total_years, step_count = _timeline(start_bce, end_bce, step_years)
    states = [initial_state]
    times = [float(start_bce)]
    active_schedule = schedule or SimulationSchedule()
    active_parameters = parameter_set or ParameterSet()

    for step_index in range(step_count):
        elapsed_years = step_index * step_years
        remaining_years = total_years - elapsed_years
        dt = min(step_years, remaining_years)
        next_time_bce = start_bce - min(total_years, elapsed_years + dt)
        step_midpoint_bce = (times[-1] + next_time_bce) / 2
        states.append(
            _advance_mean_field(
                states[-1],
                parameters,
                dt,
                step_midpoint_bce,
                active_schedule,
                active_parameters,
            )
        )
        times.append(next_time_bce)

    return SimulationResult(tuple(times), tuple(states))


def run_tau_leap(
    initial_state: PopulationState,
    parameters: SimulationParameters,
    *,
    start_bce: float = 3500.0,
    end_bce: float = 1500.0,
    step_years: float = 25.0,
    seed: int = 7,
    schedule: SimulationSchedule | None = None,
    parameter_set: ParameterSet | None = None,
) -> SimulationResult:
    """Run a seeded tau-leap stochastic simulation.

    This is a lightweight stochastic scaffold, not a final demographic engine.
    Event counts are sampled from Poisson distributions and capped so death
    events cannot produce negative source counts.
    """
    total_years, step_count = _timeline(start_bce, end_bce, step_years)
    random_generator = np.random.default_rng(seed)
    states = [initial_state]
    times = [float(start_bce)]
    active_schedule = schedule or SimulationSchedule()
    active_parameters = parameter_set or ParameterSet()

    for step_index in range(step_count):
        elapsed_years = step_index * step_years
        remaining_years = total_years - elapsed_years
        dt = min(step_years, remaining_years)
        next_time_bce = start_bce - min(total_years, elapsed_years + dt)
        step_midpoint_bce = (times[-1] + next_time_bce) / 2
        states.append(
            _advance_tau_leap(
                states[-1],
                parameters,
                dt,
                random_generator,
                step_midpoint_bce,
                active_schedule,
                active_parameters,
            )
        )
        times.append(next_time_bce)

    return SimulationResult(tuple(times), tuple(states))


def _timeline(start_bce: float, end_bce: float, step_years: float) -> tuple[float, int]:
    """Return total elapsed years and number of simulation steps."""
    if start_bce <= end_bce:
        raise ValueError("start_bce must be greater than end_bce")
    if step_years <= 0:
        raise ValueError("step_years must be positive")
    total_years = start_bce - end_bce
    return total_years, ceil(total_years / step_years)


def _advance_mean_field(
    state: PopulationState,
    parameters: SimulationParameters,
    dt: float,
    time_bce: float,
    schedule: SimulationSchedule,
    parameter_set: ParameterSet,
) -> PopulationState:
    """Advance a state by one deterministic time increment."""
    next_counts: dict[str, dict[str, float]] = {}
    for region, source_counts in state.counts.items():
        regional_parameters = parameter_set.parameters_for_region(parameters, region)
        effective_parameters = schedule.effective_parameters(
            regional_parameters, time_bce
        )
        local_parameters = parameter_set.source_for(
            effective_parameters, region=region, source=LOCAL_SOURCE
        )
        steppe_parameters = parameter_set.source_for(
            effective_parameters, region=region, source=STEPPE_SOURCE
        )
        local_count = source_counts.get(LOCAL_SOURCE, 0.0)
        steppe_count = source_counts.get(STEPPE_SOURCE, 0.0)
        scheduled_rate = schedule.migration_rate_for(
            region=region, source=STEPPE_SOURCE, time_bce=time_bce
        )
        migration_rate = effective_parameters.migration_rate + scheduled_rate
        next_counts[region] = {
            LOCAL_SOURCE: _mean_source_count(
                local_count,
                _fertility_rate(effective_parameters, local_parameters),
                local_parameters.mortality_rate,
                _epidemic_rate(effective_parameters, local_parameters),
                _stress_rate(effective_parameters),
                dt,
            ),
            STEPPE_SOURCE: _mean_source_count(
                steppe_count,
                _fertility_rate(effective_parameters, steppe_parameters),
                steppe_parameters.mortality_rate,
                _epidemic_rate(effective_parameters, steppe_parameters),
                _stress_rate(effective_parameters),
                dt,
            )
            + state.total(region) * migration_rate * dt,
        }
    return PopulationState(next_counts)


def _mean_source_count(
    count: float,
    fertility_rate: float,
    mortality_rate: float,
    epidemic_rate: float,
    violence_rate: float,
    dt: float,
) -> float:
    """Return a source count after mean births and deaths."""
    births = count * fertility_rate * dt
    deaths = count * min(1.0, (mortality_rate + epidemic_rate + violence_rate) * dt)
    return max(0.0, count + births - deaths)


def _advance_tau_leap(
    state: PopulationState,
    parameters: SimulationParameters,
    dt: float,
    random_generator: Generator,
    time_bce: float,
    schedule: SimulationSchedule,
    parameter_set: ParameterSet,
) -> PopulationState:
    """Advance a state by one stochastic tau-leap increment."""
    next_counts: dict[str, dict[str, float]] = {}
    for region, source_counts in state.counts.items():
        regional_parameters = parameter_set.parameters_for_region(parameters, region)
        effective_parameters = schedule.effective_parameters(
            regional_parameters, time_bce
        )
        local_parameters = parameter_set.source_for(
            effective_parameters, region=region, source=LOCAL_SOURCE
        )
        steppe_parameters = parameter_set.source_for(
            effective_parameters, region=region, source=STEPPE_SOURCE
        )
        local_count = source_counts.get(LOCAL_SOURCE, 0.0)
        steppe_count = source_counts.get(STEPPE_SOURCE, 0.0)
        scheduled_rate = schedule.migration_rate_for(
            region=region, source=STEPPE_SOURCE, time_bce=time_bce
        )
        migration_rate = effective_parameters.migration_rate + scheduled_rate
        next_counts[region] = {
            LOCAL_SOURCE: _tau_source_count(
                local_count,
                _fertility_rate(effective_parameters, local_parameters),
                local_parameters.mortality_rate,
                _epidemic_rate(effective_parameters, local_parameters),
                _stress_rate(effective_parameters),
                dt,
                random_generator,
            ),
            STEPPE_SOURCE: _tau_source_count(
                steppe_count,
                _fertility_rate(effective_parameters, steppe_parameters),
                steppe_parameters.mortality_rate,
                _epidemic_rate(effective_parameters, steppe_parameters),
                _stress_rate(effective_parameters),
                dt,
                random_generator,
            )
            + float(
                random_generator.poisson(
                    max(0.0, state.total(region) * migration_rate * dt)
                )
            ),
        }
    return PopulationState(next_counts)


def _tau_source_count(
    count: float,
    fertility_rate: float,
    mortality_rate: float,
    epidemic_rate: float,
    violence_rate: float,
    dt: float,
    random_generator: Generator,
) -> float:
    """Return a source count after sampled births and deaths."""
    births = float(random_generator.poisson(max(0.0, count * fertility_rate * dt)))
    death_lambda = count * min(
        1.0, (mortality_rate + epidemic_rate + violence_rate) * dt
    )
    deaths = min(count, float(random_generator.poisson(max(0.0, death_lambda))))
    return count + births - deaths


def _fertility_rate(
    parameters: SimulationParameters, source_parameters: ResolvedSourceParameters
) -> float:
    """Return climate-adjusted fertility for one simulation step."""
    return (
        source_parameters.fertility_rate
        * (1.0 - parameters.climate_stress)
        * source_parameters.reproductive_multiplier
    )


def _epidemic_rate(
    parameters: SimulationParameters, source_parameters: ResolvedSourceParameters
) -> float:
    """Return source-specific epidemic mortality for one simulation step."""
    return parameters.epidemic_mortality_rate * source_parameters.epidemic_risk


def _stress_rate(parameters: SimulationParameters) -> float:
    """Return shared climate and violence mortality for one simulation step."""
    return parameters.violence_mortality_rate + 0.01 * parameters.climate_stress
