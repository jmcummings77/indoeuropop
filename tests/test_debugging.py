"""Tests for simulation debugging helpers."""

import pytest

from indoeuropop.debugging import (
    compare_ancestry_trajectories,
    compare_deterministic_and_tau_leap,
)
from indoeuropop.models import PopulationState, SimulationParameters, SimulationResult


def _result(steppe_counts: tuple[float, float]) -> SimulationResult:
    """Build a two-point result for comparison tests."""
    return SimulationResult(
        (3000, 2950),
        (
            PopulationState(
                {
                    "britain": {
                        "local": 100 - steppe_counts[0],
                        "steppe": steppe_counts[0],
                    }
                }
            ),
            PopulationState(
                {
                    "britain": {
                        "local": 100 - steppe_counts[1],
                        "steppe": steppe_counts[1],
                    }
                }
            ),
        ),
    )


def test_compare_ancestry_trajectories_reports_differences() -> None:
    """Trajectory comparison should report pointwise and aggregate differences."""
    comparison = compare_ancestry_trajectories(
        _result((0, 10)),
        _result((5, 25)),
        source="steppe",
        region="britain",
        first_label="mean_field",
        second_label="sampled",
    )

    assert comparison.first_label == "mean_field"
    assert comparison.second_label == "sampled"
    assert comparison.times_bce == (3000, 2950)
    assert comparison.first_ancestry == pytest.approx((0.0, 0.1))
    assert comparison.second_ancestry == pytest.approx((0.05, 0.25))
    assert comparison.differences == pytest.approx((0.05, 0.15))
    assert comparison.max_abs_difference == pytest.approx(0.15)
    assert comparison.final_difference == pytest.approx(0.15)
    assert comparison.root_mean_squared_difference == pytest.approx(0.1118033989)


def test_compare_ancestry_trajectories_rejects_mismatched_times() -> None:
    """Comparison should fail when results use different time labels."""
    first = _result((0, 10))
    second = SimulationResult(
        (3000, 2925),
        (
            PopulationState({"britain": {"local": 100, "steppe": 0}}),
            PopulationState({"britain": {"local": 75, "steppe": 25}}),
        ),
    )

    with pytest.raises(ValueError, match="identical times_bce"):
        compare_ancestry_trajectories(first, second, region="britain")


def test_compare_deterministic_and_tau_leap_runs_shared_scenario() -> None:
    """The paired comparison helper should run both simulators with one setup."""
    comparison = compare_deterministic_and_tau_leap(
        PopulationState({"britain": {"local": 1000, "steppe": 10}}),
        SimulationParameters(
            fertility_rate=0.0,
            local_mortality_rate=0.0,
            steppe_mortality_rate=0.0,
            migration_rate=0.001,
        ),
        start_bce=3000,
        end_bce=2950,
        step_years=25,
        seed=5,
        region="britain",
    )

    assert comparison.first_label == "deterministic"
    assert comparison.second_label == "tau_leap"
    assert comparison.times_bce == (3000, 2975, 2950)
    assert comparison.max_abs_difference >= 0.0
