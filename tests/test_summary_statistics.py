"""Tests for reusable summary-statistic vectors."""

import pytest

from indoeuropop.analysis.summary import TrajectorySummary
from indoeuropop.analysis.summary_statistics import (
    SummaryStatistic,
    SummaryVector,
    trajectory_summary_vector,
)


def _trajectory_summary(*, extinct: bool = False) -> TrajectorySummary:
    """Return a compact trajectory summary for vector tests."""
    return TrajectorySummary(
        source="steppe",
        region="britain",
        start_bce=3000,
        end_bce=2900,
        initial_ancestry=0.1,
        final_ancestry=0.4,
        ancestry_delta=0.3,
        ancestry_slope_per_century=0.3,
        min_total_population=80,
        final_total_population=100,
        is_extinct=extinct,
    )


def test_summary_statistic_normalizes_value_by_scale() -> None:
    """Individual statistics should expose scaled values."""
    statistic = SummaryStatistic("ancestry_delta", value=0.4, scale=0.2)

    assert statistic.value == 0.4
    assert statistic.scale == 0.2
    assert statistic.normalized_value == pytest.approx(2.0)


@pytest.mark.parametrize(
    "name,value,scale",
    [
        ("", 1.0, 1.0),
        ("metric", float("nan"), 1.0),
        ("metric", 1.0, 0.0),
        ("metric", 1.0, -1.0),
        ("metric", 1.0, float("inf")),
    ],
)
def test_summary_statistic_rejects_invalid_fields(
    name: str, value: float, scale: float
) -> None:
    """Invalid statistic metadata should fail at construction."""
    with pytest.raises(ValueError):
        SummaryStatistic(name, value=value, scale=scale)


def test_summary_vector_from_mapping_exposes_values_and_names() -> None:
    """Summary vectors should preserve mapping order and expose raw values."""
    vector = SummaryVector.from_mapping(
        {"a": 2, "b": 6},
        scales={"b": 3},
    )

    assert vector.names() == ("a", "b")
    assert vector.as_dict() == {"a": 2, "b": 6}
    assert vector.value("a") == 2
    assert vector.statistic("b") == SummaryStatistic("b", 6, 3)
    assert vector.normalized_values() == pytest.approx((2, 2))
    assert vector.normalized_values(("b",)) == pytest.approx((2,))


def test_summary_vector_rejects_empty_or_duplicate_statistics() -> None:
    """Summary vectors should require at least one unique statistic name."""
    with pytest.raises(ValueError):
        SummaryVector(())
    with pytest.raises(ValueError):
        SummaryVector(
            (
                SummaryStatistic("a", 1),
                SummaryStatistic("a", 2),
            )
        )


def test_summary_vector_rejects_unknown_or_empty_selections() -> None:
    """Selected statistic names should be known and non-empty."""
    vector = SummaryVector.from_mapping({"a": 1})

    with pytest.raises(KeyError):
        vector.value("missing")
    with pytest.raises(KeyError):
        vector.normalized_values(("missing",))
    with pytest.raises(ValueError):
        vector.normalized_values(())


def test_summary_vector_distance_uses_selected_scaled_statistics() -> None:
    """Distance comparisons should use the left vector's statistic scales."""
    left = SummaryVector.from_mapping({"a": 2, "b": 10}, scales={"a": 2, "b": 5})
    right = SummaryVector.from_mapping({"a": 4, "b": 0})

    assert left.root_mean_square_distance(right, names=("a",)) == pytest.approx(1)
    assert left.root_mean_square_distance(right) == pytest.approx(
        ((1**2 + 2**2) / 2) ** 0.5
    )


def test_summary_vector_distance_rejects_bad_selections_or_other_vector() -> None:
    """Distance comparisons should fail clearly for invalid statistic selections."""
    left = SummaryVector.from_mapping({"a": 1})
    right = SummaryVector.from_mapping({"b": 1})

    with pytest.raises(KeyError):
        left.root_mean_square_distance(right)
    with pytest.raises(KeyError):
        left.root_mean_square_distance(right, names=("missing",))
    with pytest.raises(ValueError):
        left.root_mean_square_distance(right, names=())


def test_trajectory_summary_vector_converts_supported_summary_fields() -> None:
    """Trajectory summaries should convert to named reusable summary vectors."""
    vector = trajectory_summary_vector(
        _trajectory_summary(extinct=True),
        scales={"final_total_population": 100},
    )

    assert vector.names() == (
        "initial_ancestry",
        "final_ancestry",
        "ancestry_delta",
        "ancestry_slope_per_century",
        "min_total_population",
        "final_total_population",
        "is_extinct",
    )
    assert vector.value("initial_ancestry") == 0.1
    assert vector.value("final_total_population") == 100
    assert vector.statistic("final_total_population").normalized_value == 1
    assert vector.value("is_extinct") == 1


def test_trajectory_summary_vector_can_omit_extinction_indicator() -> None:
    """The extinction indicator should be optional for purely continuous vectors."""
    vector = trajectory_summary_vector(_trajectory_summary(), include_extinction=False)

    assert "is_extinct" not in vector.names()
