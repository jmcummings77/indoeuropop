"""Tests for deterministic and stochastic simulation routines."""

import numpy as np
import pytest

from indoeuropop.events import ForcingWindow, MigrationPulse, SimulationSchedule
from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.parameterization import (
    ParameterSet,
    RegionParameters,
    SourceParameters,
)
from indoeuropop.simulation import run_deterministic, run_tau_leap


def test_deterministic_simulation_is_bounded_and_time_runs_down() -> None:
    """The deterministic smoke model should produce stable bounded ancestry."""
    result = run_deterministic(
        PopulationState({"britain": {"local": 1000, "steppe": 0}}),
        SimulationParameters(migration_rate=0.001),
        start_bce=3000,
        end_bce=2900,
        step_years=50,
    )

    ancestry = result.ancestry_series("steppe", "britain")
    assert result.times_bce == (3000, 2950, 2900)
    assert np.all(ancestry >= 0)
    assert np.all(ancestry <= 1)
    assert ancestry[-1] > ancestry[0]
    assert result.total_series("britain")[-1] > 0


def test_tau_leap_simulation_is_seeded() -> None:
    """The tau-leap simulator should be reproducible with a fixed seed."""
    state = PopulationState({"britain": {"local": 1000, "steppe": 10}})
    params = SimulationParameters(migration_rate=0.001)

    first = run_tau_leap(
        state, params, start_bce=3000, end_bce=2950, step_years=25, seed=13
    )
    second = run_tau_leap(
        state, params, start_bce=3000, end_bce=2950, step_years=25, seed=13
    )

    np.testing.assert_allclose(
        first.ancestry_series("steppe", "britain"),
        second.ancestry_series("steppe", "britain"),
    )


def test_migration_pulse_increases_steppe_ancestry() -> None:
    """An active migration pulse should increase final steppe ancestry."""
    state = PopulationState({"britain": {"local": 1000, "steppe": 0}})
    params = SimulationParameters(migration_rate=0)
    baseline = run_deterministic(
        state, params, start_bce=3000, end_bce=2900, step_years=50
    )
    pulsed = run_deterministic(
        state,
        params,
        start_bce=3000,
        end_bce=2900,
        step_years=50,
        schedule=SimulationSchedule(
            migration_pulses=(
                MigrationPulse(
                    region="britain",
                    start_bce=3000,
                    end_bce=2900,
                    annual_rate=0.002,
                ),
            )
        ),
    )

    assert pulsed.final_state.ancestry_proportion(
        "steppe", "britain"
    ) > baseline.final_state.ancestry_proportion("steppe", "britain")


def test_forcing_window_lowers_population_total() -> None:
    """Climate and epidemic forcing should reduce total population growth."""
    state = PopulationState({"britain": {"local": 1000, "steppe": 25}})
    params = SimulationParameters(epidemic_mortality_rate=0)
    baseline = run_deterministic(
        state, params, start_bce=3000, end_bce=2900, step_years=50
    )
    stressed = run_deterministic(
        state,
        params,
        start_bce=3000,
        end_bce=2900,
        step_years=50,
        schedule=SimulationSchedule(
            forcing_windows=(
                ForcingWindow(
                    start_bce=3000,
                    end_bce=2900,
                    climate_stress_delta=0.5,
                    epidemic_mortality_delta=0.01,
                ),
            )
        ),
    )

    assert stressed.final_state.total("britain") < baseline.final_state.total("britain")


def test_tau_leap_accepts_schedule() -> None:
    """The stochastic simulator should apply schedules without losing determinism."""
    result = run_tau_leap(
        PopulationState({"britain": {"local": 1000, "steppe": 10}}),
        SimulationParameters(migration_rate=0),
        start_bce=3000,
        end_bce=2950,
        step_years=25,
        seed=17,
        schedule=SimulationSchedule(
            migration_pulses=(
                MigrationPulse(
                    region="britain",
                    start_bce=3000,
                    end_bce=2950,
                    annual_rate=0.001,
                ),
            )
        ),
    )

    assert result.final_state.source_total("steppe", "britain") > 0


def test_region_parameter_override_changes_only_matching_region() -> None:
    """A region migration override should affect only its named region."""
    result = run_deterministic(
        PopulationState(
            {
                "britain": {"local": 1000, "steppe": 0},
                "iberia": {"local": 1000, "steppe": 0},
            }
        ),
        SimulationParameters(migration_rate=0),
        start_bce=3000,
        end_bce=2900,
        step_years=50,
        parameter_set=ParameterSet(
            region_parameters={
                "britain": RegionParameters(migration_rate=0.002),
            }
        ),
    )

    assert result.final_state.ancestry_proportion("steppe", "britain") > 0
    assert result.final_state.ancestry_proportion("steppe", "iberia") == 0


def test_source_parameter_override_changes_source_growth() -> None:
    """A source fertility override should change the matching source trajectory."""
    state = PopulationState({"britain": {"local": 1000, "steppe": 100}})
    parameters = SimulationParameters(migration_rate=0, fertility_rate=0.01)
    baseline = run_deterministic(
        state, parameters, start_bce=3000, end_bce=2950, step_years=50
    )
    boosted = run_deterministic(
        state,
        parameters,
        start_bce=3000,
        end_bce=2950,
        step_years=50,
        parameter_set=ParameterSet(
            source_parameters={
                "britain": {
                    "steppe": SourceParameters(
                        fertility_rate=0.04,
                        reproductive_multiplier=1.5,
                    )
                }
            }
        ),
    )

    assert boosted.final_state.source_total(
        "steppe", "britain"
    ) > baseline.final_state.source_total("steppe", "britain")


@pytest.mark.parametrize(
    "start_bce,end_bce,step_years",
    [
        (2900, 3000, 50),
        (3000, 3000, 50),
        (3000, 2900, 0),
    ],
)
def test_simulation_rejects_invalid_timelines(
    start_bce: float, end_bce: float, step_years: float
) -> None:
    """Invalid time windows should fail before simulation."""
    with pytest.raises(ValueError):
        run_deterministic(
            PopulationState({"britain": {"local": 1000, "steppe": 0}}),
            SimulationParameters(),
            start_bce=start_bce,
            end_bce=end_bce,
            step_years=step_years,
        )
