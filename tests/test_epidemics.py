"""Tests for compartmental epidemic helpers."""

import pytest

from indoeuropop.models import PopulationState
from indoeuropop.simulation.epidemics import (
    DECEASED,
    INFECTED,
    RECOVERED,
    SUSCEPTIBLE,
    EpidemicParameters,
    EpidemicState,
    advance_epidemic,
)


def test_epidemic_state_derives_totals_prevalence_and_population_state() -> None:
    """Epidemic states should expose compartment totals and living collapse."""
    state = EpidemicState(
        {
            "britain": {
                "local": {
                    SUSCEPTIBLE: 80,
                    INFECTED: 10,
                    RECOVERED: 5,
                    DECEASED: 5,
                },
                "steppe": {SUSCEPTIBLE: 40, INFECTED: 5, RECOVERED: 5},
            },
            "iberia": {
                "local": {SUSCEPTIBLE: 20, INFECTED: 0, RECOVERED: 10},
            },
        }
    )

    assert state.regions() == ("britain", "iberia")
    assert state.sources() == ("local", "steppe")
    assert state.sources("britain") == ("local", "steppe")
    assert state.total() == 180
    assert state.total(living_only=True) == 175
    assert state.total(region="britain") == 150
    assert state.total(region="britain", source="steppe") == 50
    assert state.total(compartment=SUSCEPTIBLE) == 140
    assert state.infection_prevalence(region="britain") == pytest.approx(15 / 145)
    assert state.infection_prevalence(region="britain", source="steppe") == 0.1
    assert state.to_population_state() == PopulationState(
        {
            "britain": {"local": 95, "steppe": 50},
            "iberia": {"local": 30},
        }
    )
    assert state.to_population_state(include_deceased=True) == PopulationState(
        {
            "britain": {"local": 100, "steppe": 50},
            "iberia": {"local": 30},
        }
    )


def test_epidemic_state_fills_missing_standard_compartments() -> None:
    """Missing standard compartments should be treated as zero counts."""
    state = EpidemicState({"britain": {"local": {SUSCEPTIBLE: 10}}})

    assert state.total(compartment=SUSCEPTIBLE) == 10
    assert state.total(compartment=INFECTED) == 0
    assert state.total(compartment=RECOVERED) == 0
    assert state.total(compartment=DECEASED) == 0


def test_zero_living_epidemic_state_has_zero_prevalence() -> None:
    """Prevalence should not divide by zero in an empty living population."""
    state = EpidemicState({"britain": {"local": {DECEASED: 10}}})

    assert state.infection_prevalence(region="britain") == 0


@pytest.mark.parametrize(
    "bad_counts",
    [
        {},
        {"": {"local": {SUSCEPTIBLE: 1}}},
        {"britain": {}},
        {"britain": {"": {SUSCEPTIBLE: 1}}},
        {"britain": {"local": {}}},
        {"britain": {"local": {SUSCEPTIBLE: -1}}},
        {"britain": {"local": {SUSCEPTIBLE: float("inf")}}},
        {"britain": {"local": {"unknown": 1}}},
    ],
)
def test_epidemic_state_rejects_invalid_counts(
    bad_counts: dict[str, dict[str, dict[str, float]]],
) -> None:
    """Invalid epidemic count mappings should fail at construction."""
    with pytest.raises(ValueError):
        EpidemicState(bad_counts)


def test_epidemic_state_rejects_invalid_compartment_filter() -> None:
    """Compartment filters should only accept modeled labels."""
    state = EpidemicState({"britain": {"local": {SUSCEPTIBLE: 10}}})

    with pytest.raises(ValueError):
        state.total(compartment="unknown")


def test_default_epidemic_parameters_construct_successfully() -> None:
    """Default epidemic parameters should be valid."""
    parameters = EpidemicParameters()

    assert parameters.transmission_rate == 0
    assert parameters.recovery_rate == 0
    assert parameters.source_susceptibility == {}


@pytest.mark.parametrize(
    "field_name,bad_value",
    [
        ("transmission_rate", -0.1),
        ("transmission_rate", float("nan")),
        ("recovery_rate", 1.1),
        ("recovery_rate", -0.1),
        ("disease_mortality_rate", 1.1),
        ("background_mortality_rate", -0.1),
    ],
)
def test_epidemic_parameters_reject_invalid_scalar_values(
    field_name: str, bad_value: float
) -> None:
    """Invalid scalar epidemic parameters should raise validation errors."""
    with pytest.raises(ValueError):
        if field_name == "transmission_rate":
            EpidemicParameters(transmission_rate=bad_value)
        elif field_name == "recovery_rate":
            EpidemicParameters(recovery_rate=bad_value)
        elif field_name == "disease_mortality_rate":
            EpidemicParameters(disease_mortality_rate=bad_value)
        else:
            EpidemicParameters(background_mortality_rate=bad_value)


@pytest.mark.parametrize(
    "susceptibility",
    [
        {"": 1.0},
        {"steppe": -1.0},
        {"steppe": float("inf")},
    ],
)
def test_epidemic_parameters_reject_invalid_susceptibility(
    susceptibility: dict[str, float],
) -> None:
    """Source susceptibility multipliers should be valid non-negative values."""
    with pytest.raises(ValueError):
        EpidemicParameters(source_susceptibility=susceptibility)


def test_advance_epidemic_projects_transmission_recovery_and_death() -> None:
    """Epidemic projection should apply transmission and infected removals."""
    state = EpidemicState(
        {
            "britain": {
                "local": {SUSCEPTIBLE: 90, INFECTED: 10},
                "steppe": {SUSCEPTIBLE: 50},
            }
        }
    )
    parameters = EpidemicParameters(
        transmission_rate=0.3,
        recovery_rate=0.2,
        disease_mortality_rate=0.1,
    )

    projected = advance_epidemic(state, parameters, years=1)

    force = 0.3 * 10 / 150
    assert projected.total(
        region="britain", source="local", compartment=SUSCEPTIBLE
    ) == pytest.approx(90 - 90 * force)
    assert projected.total(
        region="britain", source="local", compartment=INFECTED
    ) == pytest.approx(10 + 90 * force - 3)
    assert projected.total(
        region="britain", source="local", compartment=RECOVERED
    ) == pytest.approx(2)
    assert projected.total(
        region="britain", source="local", compartment=DECEASED
    ) == pytest.approx(1)
    assert projected.total(
        region="britain", source="steppe", compartment=INFECTED
    ) == pytest.approx(50 * force)


def test_advance_epidemic_applies_background_mortality_and_susceptibility() -> None:
    """Background mortality and source susceptibility should affect transitions."""
    state = EpidemicState(
        {
            "britain": {
                "local": {SUSCEPTIBLE: 100, INFECTED: 100, RECOVERED: 100},
                "steppe": {SUSCEPTIBLE: 100},
            }
        }
    )
    parameters = EpidemicParameters(
        transmission_rate=0.4,
        background_mortality_rate=0.1,
        source_susceptibility={"steppe": 2.0},
    )

    projected = advance_epidemic(state, parameters, years=1)

    force = 0.4 * 100 / 400
    assert projected.total(
        region="britain", source="local", compartment=SUSCEPTIBLE
    ) == pytest.approx(90 - 90 * force)
    assert projected.total(
        region="britain", source="steppe", compartment=SUSCEPTIBLE
    ) == pytest.approx(90 - 90 * force * 2)
    assert projected.total(compartment=DECEASED) == pytest.approx(40)


def test_advance_epidemic_caps_rates_to_avoid_negative_compartments() -> None:
    """Large rates over long steps should not create negative compartments."""
    state = EpidemicState(
        {"britain": {"local": {SUSCEPTIBLE: 10, INFECTED: 10, RECOVERED: 10}}}
    )
    parameters = EpidemicParameters(
        transmission_rate=10,
        recovery_rate=1,
        disease_mortality_rate=1,
        background_mortality_rate=0,
    )

    projected = advance_epidemic(state, parameters, years=2)

    assert projected.total(compartment=SUSCEPTIBLE) == 0
    assert projected.total(compartment=INFECTED) == 10
    assert projected.total(compartment=RECOVERED) == 15
    assert projected.total(compartment=DECEASED) == 5


def test_advance_epidemic_handles_zero_living_regions() -> None:
    """Regions without living people should preserve deceased counts."""
    state = EpidemicState({"britain": {"local": {DECEASED: 10}}})
    parameters = EpidemicParameters(transmission_rate=1)

    projected = advance_epidemic(state, parameters, years=1)

    assert projected.total(compartment=DECEASED) == 10
    assert projected.total(living_only=True) == 0


def test_advance_epidemic_allows_zero_year_projection() -> None:
    """A zero-year projection should preserve epidemic counts exactly."""
    state = EpidemicState({"britain": {"local": {SUSCEPTIBLE: 10, INFECTED: 1}}})

    projected = advance_epidemic(
        state, EpidemicParameters(transmission_rate=1), years=0
    )

    assert projected == state


@pytest.mark.parametrize("bad_years", [-1.0, float("nan")])
def test_advance_epidemic_rejects_invalid_years(bad_years: float) -> None:
    """Projection length should be finite and non-negative."""
    state = EpidemicState({"britain": {"local": {SUSCEPTIBLE: 10}}})

    with pytest.raises(ValueError):
        advance_epidemic(state, EpidemicParameters(), years=bad_years)
