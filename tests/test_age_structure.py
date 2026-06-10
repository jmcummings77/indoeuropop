"""Tests for age-structured population helpers."""

import pytest

from indoeuropop.age_structure import (
    ADULT,
    ELDER,
    JUVENILE,
    AgeStructuredState,
    AgeStructureParameters,
    advance_age_structure,
)
from indoeuropop.models import PopulationState


def test_age_structured_state_derives_totals_and_ancestry() -> None:
    """Age-structured states should collapse to source totals."""
    state = AgeStructuredState(
        {
            "britain": {
                "local": {JUVENILE: 20, ADULT: 50, ELDER: 10},
                "steppe": {JUVENILE: 5, ADULT: 10, ELDER: 5},
            },
            "iberia": {
                "local": {JUVENILE: 30, ADULT: 60, ELDER: 10},
            },
        }
    )

    assert state.regions() == ("britain", "iberia")
    assert state.sources() == ("local", "steppe")
    assert state.sources("britain") == ("local", "steppe")
    assert state.total() == 200
    assert state.total(region="britain") == 100
    assert state.total(region="britain", source="steppe") == 20
    assert state.total(age_class=ADULT) == 120
    assert state.ancestry_proportion("steppe", "britain") == 0.2
    assert state.to_population_state() == PopulationState(
        {
            "britain": {"local": 80, "steppe": 20},
            "iberia": {"local": 100},
        }
    )


def test_age_structured_state_fills_missing_standard_classes() -> None:
    """Missing standard age classes should be treated as zero counts."""
    state = AgeStructuredState({"britain": {"local": {ADULT: 10}}})

    assert state.total(age_class=JUVENILE) == 0
    assert state.total(age_class=ADULT) == 10
    assert state.total(age_class=ELDER) == 0


def test_zero_population_age_state_has_zero_ancestry() -> None:
    """Empty age-structured populations should not divide by zero."""
    state = AgeStructuredState({"britain": {"local": {ADULT: 0}}})

    assert state.ancestry_proportion("steppe", "britain") == 0


@pytest.mark.parametrize(
    "bad_counts",
    [
        {},
        {"": {"local": {ADULT: 1}}},
        {"britain": {}},
        {"britain": {"": {ADULT: 1}}},
        {"britain": {"local": {}}},
        {"britain": {"local": {ADULT: -1}}},
        {"britain": {"local": {ADULT: float("inf")}}},
        {"britain": {"local": {"unknown": 1}}},
    ],
)
def test_age_structured_state_rejects_invalid_counts(
    bad_counts: dict[str, dict[str, dict[str, float]]],
) -> None:
    """Invalid age-structured count mappings should fail at construction."""
    with pytest.raises(ValueError):
        AgeStructuredState(bad_counts)


def test_default_age_structure_parameters_construct_successfully() -> None:
    """Default age-structure parameters should be valid."""
    parameters = AgeStructureParameters()

    assert parameters.annual_birth_rate > 0
    assert parameters.adult_mortality_rate > 0


@pytest.mark.parametrize(
    "field_name,bad_value",
    [
        ("annual_birth_rate", -0.1),
        ("annual_birth_rate", float("nan")),
        ("juvenile_mortality_rate", 1.1),
        ("adult_mortality_rate", -0.1),
        ("elder_mortality_rate", float("nan")),
        ("juvenile_maturation_rate", 1.1),
        ("adult_aging_rate", -0.1),
    ],
)
def test_age_structure_parameters_reject_invalid_values(
    field_name: str, bad_value: float
) -> None:
    """Invalid age-structure rates should raise validation errors."""
    with pytest.raises(ValueError):
        AgeStructureParameters(**{field_name: bad_value})


def test_advance_age_structure_projects_births_deaths_and_transitions() -> None:
    """Age projection should apply survival, maturation, aging, and births."""
    state = AgeStructuredState(
        {"britain": {"local": {JUVENILE: 100, ADULT: 100, ELDER: 50}}}
    )
    parameters = AgeStructureParameters(
        annual_birth_rate=0.1,
        juvenile_mortality_rate=0.01,
        adult_mortality_rate=0.02,
        elder_mortality_rate=0.04,
        juvenile_maturation_rate=0.1,
        adult_aging_rate=0.05,
    )

    projected = advance_age_structure(state, parameters, years=1)

    assert projected.total(region="britain", source="local", age_class=JUVENILE) == (
        pytest.approx(99 - 9.9 + 10)
    )
    assert projected.total(region="britain", source="local", age_class=ADULT) == (
        pytest.approx(98 - 4.9 + 9.9)
    )
    assert projected.total(region="britain", source="local", age_class=ELDER) == (
        pytest.approx(48 + 4.9)
    )


def test_advance_age_structure_caps_deaths_and_transitions() -> None:
    """Large rates over long steps should not create negative age classes."""
    state = AgeStructuredState(
        {"britain": {"local": {JUVENILE: 10, ADULT: 10, ELDER: 10}}}
    )
    parameters = AgeStructureParameters(
        annual_birth_rate=0,
        juvenile_mortality_rate=1,
        adult_mortality_rate=0,
        elder_mortality_rate=1,
        juvenile_maturation_rate=1,
        adult_aging_rate=1,
    )

    projected = advance_age_structure(state, parameters, years=2)

    assert projected.total(age_class=JUVENILE) == 0
    assert projected.total(age_class=ADULT) == 0
    assert projected.total(age_class=ELDER) == 10


def test_advance_age_structure_allows_zero_year_projection() -> None:
    """A zero-year projection should preserve age counts exactly."""
    state = AgeStructuredState(
        {"britain": {"local": {JUVENILE: 5, ADULT: 10, ELDER: 3}}}
    )

    projected = advance_age_structure(state, AgeStructureParameters(), years=0)

    assert projected == state


@pytest.mark.parametrize("bad_years", [-1.0, float("nan")])
def test_advance_age_structure_rejects_invalid_years(bad_years: float) -> None:
    """Projection length should be finite and non-negative."""
    state = AgeStructuredState({"britain": {"local": {ADULT: 10}}})

    with pytest.raises(ValueError):
        advance_age_structure(state, AgeStructureParameters(), years=bad_years)
