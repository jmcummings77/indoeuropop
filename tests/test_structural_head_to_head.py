"""Tests for same-baseline structural candidate helpers."""

from __future__ import annotations

from typing import Any

import pytest

from indoeuropop.analysis.structural_head_to_head import (
    StructuredPulseCandidate,
    apply_structured_pulse_candidate,
    better_root_mean_squared_error_delta,
    structured_pulse_regions,
)
from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec


def test_structured_pulse_candidate_normalizes_and_applies_to_regions() -> None:
    """A structured pulse should target every matching child region."""
    candidate = StructuredPulseCandidate(
        name="  broad-pulse  ",
        region_prefix=" central_europe__ ",
        start_bce=3000,
        end_bce=2600,
        annual_rate=0.00005,
    )

    updated = apply_structured_pulse_candidate(_spec(), candidate)

    assert candidate.name == "broad-pulse"
    assert candidate.region_prefix == "central_europe__"
    assert structured_pulse_regions(_spec(), candidate) == (
        "central_europe__a",
        "central_europe__b",
    )
    assert [pulse.region for pulse in updated.schedule.migration_pulses] == [
        "central_europe__a",
        "central_europe__b",
    ]
    assert all(
        pulse.annual_rate == pytest.approx(0.00005)
        for pulse in updated.schedule.migration_pulses
    )


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"name": "   "}, "name must be non-empty"),
        ({"region_prefix": "   "}, "region_prefix must be non-empty"),
        ({"annual_rate": -0.1}, "annual_rate must be between 0 and 1"),
    ],
)
def test_structured_pulse_candidate_rejects_invalid_values(
    kwargs: dict[str, object],
    expected: str,
) -> None:
    """Candidate validation should reject unusable identity or pulse fields."""
    values: dict[str, Any] = {
        "name": "candidate",
        "region_prefix": "central_europe__",
        "start_bce": 3000,
        "end_bce": 2600,
        "annual_rate": 0.00005,
    }
    values.update(kwargs)

    with pytest.raises(ValueError, match=expected):
        StructuredPulseCandidate(**values)


def test_structured_pulse_regions_rejects_unmatched_prefix() -> None:
    """The comparison should fail loudly for a prefix that touches no regions."""
    candidate = StructuredPulseCandidate(
        name="miss",
        region_prefix="iberia__",
        start_bce=3000,
        end_bce=2600,
        annual_rate=0.00005,
    )

    with pytest.raises(ValueError, match="matched no modeled regions"):
        structured_pulse_regions(_spec(), candidate)


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [(-0.2, -0.1, "left"), (-0.1, -0.2, "right"), (-0.1, -0.1, "tie")],
)
def test_better_root_mean_squared_error_delta(
    left: float,
    right: float,
    expected: str,
) -> None:
    """The more negative RMSE delta represents the stronger improvement."""
    assert better_root_mean_squared_error_delta(left, right) == expected


def _spec() -> SweepSpec:
    """Return a tiny structured spec for helper tests."""
    return SweepSpec(
        initial_state=PopulationState(
            {
                "central_europe__a": {"local": 1000, "steppe": 5},
                "central_europe__b": {"local": 900, "steppe": 10},
                "britain": {"local": 1000, "steppe": 0},
            }
        ),
        base_parameters=SimulationParameters(migration_rate=0.0),
        parameter_ranges=(ParameterRange("migration_rate", 0.0, 0.001),),
        start_bce=3100,
        end_bce=2900,
        step_years=50,
        sample_count=2,
        seed=31,
        source="steppe",
        region="central_europe__a",
    )
