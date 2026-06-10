"""Tests for time-bounded simulation events."""

from typing import Any, cast

import pytest

from indoeuropop.events import (
    ForcingWindow,
    MigrationPulse,
    SimulationSchedule,
    TimeWindow,
)
from indoeuropop.models import SimulationParameters


def test_time_window_contains_inclusive_bce_bounds() -> None:
    """BCE windows should include both endpoints and exclude outside times."""
    window = TimeWindow(start_bce=3000, end_bce=2900)

    assert window.contains(3000)
    assert window.contains(2950)
    assert window.contains(2900)
    assert not window.contains(3001)
    assert not window.contains(2899)


@pytest.mark.parametrize(
    "start_bce,end_bce",
    [
        (2900, 3000),
        (3000, 3000),
        (float("nan"), 2900),
    ],
)
def test_time_window_rejects_invalid_bounds(start_bce: float, end_bce: float) -> None:
    """Invalid BCE windows should fail during construction."""
    with pytest.raises(ValueError):
        TimeWindow(start_bce=start_bce, end_bce=end_bce)


def test_migration_pulse_applies_to_matching_region_source_and_time() -> None:
    """MigrationPulse should only apply to its exact region/source/window."""
    pulse = MigrationPulse(
        region="britain", start_bce=3000, end_bce=2900, annual_rate=0.01
    )

    assert pulse.window.contains(2950)
    assert pulse.applies_to(region="britain", source="steppe", time_bce=2950)
    assert not pulse.applies_to(region="iberia", source="steppe", time_bce=2950)
    assert not pulse.applies_to(region="britain", source="local", time_bce=2950)
    assert not pulse.applies_to(region="britain", source="steppe", time_bce=2850)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"region": ""},
        {"source": "local"},
        {"annual_rate": -0.1},
        {"annual_rate": 1.1},
    ],
)
def test_migration_pulse_rejects_invalid_fields(kwargs: dict[str, object]) -> None:
    """MigrationPulse should reject unsupported sources and bad rates."""
    valid_kwargs: dict[str, object] = {
        "region": "britain",
        "source": "steppe",
        "start_bce": 3000,
        "end_bce": 2900,
        "annual_rate": 0.01,
    }
    valid_kwargs.update(kwargs)

    with pytest.raises(ValueError):
        MigrationPulse(**cast(Any, valid_kwargs))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"climate_stress_delta": -0.1},
        {"climate_stress_delta": 1.1},
        {"epidemic_mortality_delta": -0.1},
        {"epidemic_mortality_delta": 1.1},
    ],
)
def test_forcing_window_rejects_invalid_deltas(kwargs: dict[str, float]) -> None:
    """ForcingWindow should validate probability-like deltas."""
    valid_kwargs = {
        "start_bce": 3000,
        "end_bce": 2900,
        "climate_stress_delta": 0.1,
        "epidemic_mortality_delta": 0.01,
    }
    valid_kwargs.update(kwargs)

    with pytest.raises(ValueError):
        ForcingWindow(**valid_kwargs)


def test_schedule_sums_active_pulses_and_forcing_windows() -> None:
    """SimulationSchedule should combine active events at a BCE time."""
    schedule = SimulationSchedule(
        migration_pulses=(
            MigrationPulse(
                region="britain", start_bce=3000, end_bce=2900, annual_rate=0.01
            ),
            MigrationPulse(
                region="britain", start_bce=3000, end_bce=2900, annual_rate=0.02
            ),
        ),
        forcing_windows=(
            ForcingWindow(
                start_bce=3000,
                end_bce=2900,
                climate_stress_delta=0.2,
                epidemic_mortality_delta=0.03,
            ),
        ),
    )

    active_parameters = schedule.effective_parameters(
        SimulationParameters(climate_stress=0.1, epidemic_mortality_rate=0.02),
        2950,
    )
    inactive_parameters = schedule.effective_parameters(SimulationParameters(), 2850)

    assert schedule.migration_rate_for(
        region="britain", source="steppe", time_bce=2950
    ) == pytest.approx(0.03)
    assert (
        schedule.migration_rate_for(region="iberia", source="steppe", time_bce=2950)
        == 0
    )
    assert active_parameters.climate_stress == pytest.approx(0.3)
    assert active_parameters.epidemic_mortality_rate == pytest.approx(0.05)
    assert inactive_parameters == SimulationParameters()


def test_schedule_caps_forcing_parameters() -> None:
    """Active forcing windows should cap probability-like parameters at one."""
    schedule = SimulationSchedule(
        forcing_windows=(
            ForcingWindow(
                start_bce=3000,
                end_bce=2900,
                climate_stress_delta=0.8,
                epidemic_mortality_delta=0.9,
            ),
        )
    )

    parameters = schedule.effective_parameters(
        SimulationParameters(climate_stress=0.5, epidemic_mortality_rate=0.5),
        2950,
    )

    assert parameters.climate_stress == 1
    assert parameters.epidemic_mortality_rate == 1
