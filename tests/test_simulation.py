"""Tests for deterministic and stochastic simulation routines."""

import numpy as np
import pytest

from indoeuropop.models import PopulationState, SimulationParameters
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
