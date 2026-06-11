"""Tests for sex-structured reproduction helpers."""

import pytest

from indoeuropop.models import PopulationState
from indoeuropop.models.sex_bias import (
    FEMALE,
    MALE,
    SexBiasParameters,
    SexStructuredState,
    expected_births_by_source,
)


def test_sex_structured_state_derives_totals_and_proportions() -> None:
    """Sex-structured states should expose filtered counts and proportions."""
    state = SexStructuredState(
        {
            "britain": {
                "local": {FEMALE: 80, MALE: 70},
                "steppe": {FEMALE: 20, MALE: 30},
            },
            "iberia": {
                "local": {FEMALE: 60, MALE: 40},
            },
        }
    )

    assert state.regions() == ("britain", "iberia")
    assert state.sources() == ("local", "steppe")
    assert state.sources("britain") == ("local", "steppe")
    assert state.total() == 300
    assert state.total(region="britain") == 200
    assert state.total(region="britain", source="steppe") == 50
    assert state.total(sex=FEMALE) == 160
    assert state.total(region="britain", source="steppe", sex=MALE) == 30
    assert state.source_proportion_by_sex("steppe", FEMALE, "britain") == 0.2
    assert state.source_proportion_by_sex("steppe", MALE, "britain") == 0.3
    assert state.to_population_state() == PopulationState(
        {
            "britain": {"local": 150, "steppe": 50},
            "iberia": {"local": 100},
        }
    )


def test_sex_structured_state_fills_missing_standard_labels() -> None:
    """Missing standard sex labels should be treated as zero counts."""
    state = SexStructuredState({"britain": {"local": {FEMALE: 10}}})

    assert state.total(sex=FEMALE) == 10
    assert state.total(sex=MALE) == 0


def test_zero_sex_filtered_population_has_zero_source_proportion() -> None:
    """A zero denominator should produce a zero source proportion."""
    state = SexStructuredState({"britain": {"local": {FEMALE: 0}}})

    assert state.source_proportion_by_sex("steppe", MALE, "britain") == 0


@pytest.mark.parametrize(
    "bad_counts",
    [
        {},
        {"": {"local": {FEMALE: 1}}},
        {"britain": {}},
        {"britain": {"": {FEMALE: 1}}},
        {"britain": {"local": {}}},
        {"britain": {"local": {FEMALE: -1}}},
        {"britain": {"local": {FEMALE: float("inf")}}},
        {"britain": {"local": {"unknown": 1}}},
    ],
)
def test_sex_structured_state_rejects_invalid_counts(
    bad_counts: dict[str, dict[str, dict[str, float]]],
) -> None:
    """Invalid sex-structured count mappings should fail at construction."""
    with pytest.raises(ValueError):
        SexStructuredState(bad_counts)


@pytest.mark.parametrize("method_name", ["total", "source_proportion_by_sex"])
def test_sex_structured_state_rejects_invalid_filter_sex(method_name: str) -> None:
    """Sex filters should only accept modeled labels."""
    state = SexStructuredState({"britain": {"local": {FEMALE: 10, MALE: 10}}})

    with pytest.raises(ValueError):
        if method_name == "total":
            state.total(sex="unknown")
        else:
            state.source_proportion_by_sex("local", "unknown", "britain")


def test_default_sex_bias_parameters_construct_successfully() -> None:
    """Default sex-bias parameters should be valid."""
    parameters = SexBiasParameters()

    assert parameters.annual_birth_rate > 0
    assert parameters.maternal_autosomal_share == 0.5
    assert parameters.female_reproductive_multipliers == {}
    assert parameters.male_reproductive_multipliers == {}


@pytest.mark.parametrize(
    "field_name,bad_value",
    [
        ("annual_birth_rate", -0.1),
        ("annual_birth_rate", float("nan")),
        ("maternal_autosomal_share", 1.1),
        ("maternal_autosomal_share", -0.1),
    ],
)
def test_sex_bias_parameters_reject_invalid_scalar_values(
    field_name: str, bad_value: float
) -> None:
    """Invalid scalar sex-bias parameters should raise validation errors."""
    with pytest.raises(ValueError):
        if field_name == "annual_birth_rate":
            SexBiasParameters(annual_birth_rate=bad_value)
        else:
            SexBiasParameters(maternal_autosomal_share=bad_value)


@pytest.mark.parametrize(
    "multipliers",
    [
        {"": 1.0},
        {"steppe": -1.0},
        {"steppe": float("inf")},
    ],
)
def test_sex_bias_parameters_reject_invalid_multipliers(
    multipliers: dict[str, float],
) -> None:
    """Source-specific reproductive multipliers must be valid counts."""
    with pytest.raises(ValueError):
        SexBiasParameters(male_reproductive_multipliers=multipliers)


def test_expected_births_by_source_uses_sex_specific_weights() -> None:
    """Birth expectations should blend maternal and paternal source weights."""
    state = SexStructuredState(
        {
            "britain": {
                "local": {FEMALE: 80, MALE: 80},
                "steppe": {FEMALE: 20, MALE: 20},
            }
        }
    )
    parameters = SexBiasParameters(
        annual_birth_rate=0.1,
        maternal_autosomal_share=0.5,
        male_reproductive_multipliers={"steppe": 3.0},
    )

    births = expected_births_by_source(state, parameters, years=1)

    assert births.total("britain") == pytest.approx(10)
    assert births.source_total("local", "britain") == pytest.approx(
        10 * (0.5 * 0.8 + 0.5 * (80 / 140))
    )
    assert births.source_total("steppe", "britain") == pytest.approx(
        10 * (0.5 * 0.2 + 0.5 * (60 / 140))
    )


def test_expected_births_supports_female_multipliers_and_region_filter() -> None:
    """Region filters should project births for only the requested region."""
    state = SexStructuredState(
        {
            "britain": {
                "local": {FEMALE: 10, MALE: 10},
                "steppe": {FEMALE: 10, MALE: 10},
            },
            "iberia": {
                "local": {FEMALE: 50, MALE: 50},
            },
        }
    )
    parameters = SexBiasParameters(
        annual_birth_rate=0.2,
        maternal_autosomal_share=1.0,
        female_reproductive_multipliers={"steppe": 3.0},
    )

    births = expected_births_by_source(state, parameters, years=2, region="britain")

    assert births.regions() == ("britain",)
    assert births.total("britain") == pytest.approx(16)
    assert births.source_total("local", "britain") == pytest.approx(4)
    assert births.source_total("steppe", "britain") == pytest.approx(12)


def test_expected_births_by_source_returns_zero_without_both_sexes() -> None:
    """Birth expectations require non-zero female and male reproductive weights."""
    state = SexStructuredState(
        {"britain": {"local": {FEMALE: 10, MALE: 0}, "steppe": {FEMALE: 5}}}
    )

    births = expected_births_by_source(state, SexBiasParameters(), years=1)

    assert births.total("britain") == 0
    assert births.source_total("local", "britain") == 0
    assert births.source_total("steppe", "britain") == 0


@pytest.mark.parametrize("bad_years", [-1.0, float("nan")])
def test_expected_births_by_source_rejects_invalid_years(bad_years: float) -> None:
    """Projection length should be finite and non-negative."""
    state = SexStructuredState({"britain": {"local": {FEMALE: 10, MALE: 10}}})

    with pytest.raises(ValueError):
        expected_births_by_source(state, SexBiasParameters(), years=bad_years)


def test_expected_births_by_source_rejects_unknown_region() -> None:
    """Region filters should refer to a modeled region."""
    state = SexStructuredState({"britain": {"local": {FEMALE: 10, MALE: 10}}})

    with pytest.raises(KeyError):
        expected_births_by_source(state, SexBiasParameters(), years=1, region="iberia")
