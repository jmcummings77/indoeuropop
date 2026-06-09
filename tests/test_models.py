"""Tests for core data models."""

import numpy as np
import pytest

from indoeuropop.models import PopulationState, SimulationParameters, SimulationResult


def test_population_state_derives_counts_and_ancestry() -> None:
    """PopulationState should expose region/source totals and proportions."""
    state = PopulationState(
        {
            "britain": {"local": 75, "steppe": 25},
            "iberia": {"local": 90, "steppe": 10},
        }
    )

    assert state.regions() == ("britain", "iberia")
    assert state.sources() == ("local", "steppe")
    assert state.sources("britain") == ("local", "steppe")
    assert state.total() == 200
    assert state.total("britain") == 100
    assert state.source_total("steppe") == 35
    assert state.source_total("unknown") == 0
    assert state.source_total("steppe", "iberia") == 10
    assert state.ancestry_proportion("steppe", "britain") == 0.25
    assert state.ancestry_proportion("steppe") == 0.175


def test_zero_population_region_has_zero_ancestry() -> None:
    """An empty region should not divide by zero."""
    state = PopulationState({"test": {"local": 0, "steppe": 0}})

    assert state.ancestry_proportion("steppe", "test") == 0


@pytest.mark.parametrize(
    "bad_counts",
    [
        {},
        {"": {"local": 1}},
        {"region": {}},
        {"region": {"": 1}},
        {"region": {"local": -1}},
        {"region": {"local": float("inf")}},
    ],
)
def test_population_state_rejects_invalid_counts(
    bad_counts: dict[str, dict[str, float]],
) -> None:
    """Invalid count mappings should fail at construction."""
    with pytest.raises(ValueError):
        PopulationState(bad_counts)


def test_default_parameters_construct_successfully() -> None:
    """The default parameter set should be valid."""
    parameters = SimulationParameters()

    assert parameters.fertility_rate > 0
    assert parameters.elite_reproductive_advantage == 1


@pytest.mark.parametrize(
    "field_name,bad_value",
    [
        ("fertility_rate", -0.1),
        ("migration_rate", 1.1),
        ("climate_stress", float("nan")),
        ("elite_reproductive_advantage", 0.5),
    ],
)
def test_parameters_reject_invalid_values(field_name: str, bad_value: float) -> None:
    """Invalid scalar parameters should raise clear validation errors."""
    with pytest.raises(ValueError):
        SimulationParameters(**{field_name: bad_value})


def test_simulation_result_helpers() -> None:
    """SimulationResult should expose array helpers for plotting and checks."""
    states = (
        PopulationState({"britain": {"local": 100, "steppe": 0}}),
        PopulationState({"britain": {"local": 50, "steppe": 50}}),
    )
    result = SimulationResult((3000, 2950), states)

    assert result.final_state == states[-1]
    np.testing.assert_allclose(result.ancestry_series("steppe", "britain"), [0, 0.5])
    np.testing.assert_allclose(result.total_series("britain"), [100, 100])


@pytest.mark.parametrize(
    "times,states",
    [
        ((), (PopulationState({"britain": {"local": 1}}),)),
        ((3000,), ()),
        ((float("nan"),), (PopulationState({"britain": {"local": 1}}),)),
    ],
)
def test_simulation_result_rejects_invalid_series(
    times: tuple[float, ...],
    states: tuple[PopulationState, ...],
) -> None:
    """Malformed result series should fail before plotting or analysis."""
    with pytest.raises(ValueError):
        SimulationResult(times, states)
