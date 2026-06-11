"""Tests for simulation output diagnostics."""

import pytest

from indoeuropop.analysis.diagnostics import has_errors, validate_simulation_result
from indoeuropop.models import PopulationState, SimulationResult


def test_validate_simulation_result_accepts_clean_result() -> None:
    """A stable result with decreasing BCE labels should have no diagnostics."""
    result = SimulationResult(
        (3000, 2950),
        (
            PopulationState({"britain": {"local": 100, "steppe": 0}}),
            PopulationState({"britain": {"local": 95, "steppe": 10}}),
        ),
    )

    issues = validate_simulation_result(result, sources=("local", "steppe"))

    assert issues == ()
    assert not has_errors(issues)


def test_validate_simulation_result_reports_core_sanity_issues() -> None:
    """Diagnostics should catch time, extinction, and runaway-growth issues."""
    result = SimulationResult(
        (3000, 3000),
        (
            PopulationState(
                {
                    "britain": {"local": 10, "steppe": 0},
                    "iberia": {"local": 0, "steppe": 0},
                }
            ),
            PopulationState(
                {
                    "britain": {"local": 250, "steppe": 0},
                    "iberia": {"local": 0, "steppe": 0},
                }
            ),
        ),
    )

    issues = validate_simulation_result(
        result,
        extinction_threshold=0.5,
        max_population_multiplier=20,
        sources=("local", "steppe"),
    )
    codes = [issue.code for issue in issues]

    assert "non_decreasing_time" in codes
    assert codes.count("extinction") == 2
    assert "runaway_growth" in codes
    assert has_errors(issues)


def test_validate_simulation_result_reports_missing_labels() -> None:
    """Diagnostics should flag inconsistent region and source labels."""
    result = SimulationResult(
        (3000, 2950),
        (
            PopulationState({"britain": {"local": 90, "steppe": 10}}),
            PopulationState({"iberia": {"local": 100}}),
        ),
    )

    issues = validate_simulation_result(result)
    issue_keys = {(issue.code, issue.region, issue.source) for issue in issues}

    assert ("missing_region", "iberia", None) in issue_keys
    assert ("missing_region", "britain", None) in issue_keys
    assert ("missing_source", "iberia", "steppe") in issue_keys
    assert has_errors(issues)


@pytest.mark.parametrize(
    "extinction_threshold,max_population_multiplier",
    [
        (-0.1, 20.0),
        (float("nan"), 20.0),
        (1.0, 0.5),
    ],
)
def test_validate_simulation_result_rejects_invalid_limits(
    extinction_threshold: float,
    max_population_multiplier: float,
) -> None:
    """Invalid diagnostic thresholds should fail before checking results."""
    result = SimulationResult(
        (3000,),
        (PopulationState({"britain": {"local": 100, "steppe": 0}}),),
    )

    with pytest.raises(ValueError):
        validate_simulation_result(
            result,
            extinction_threshold=extinction_threshold,
            max_population_multiplier=max_population_multiplier,
        )


def test_validate_simulation_result_rejects_empty_source_label() -> None:
    """Explicit source filters should contain real labels."""
    result = SimulationResult(
        (3000,),
        (PopulationState({"britain": {"local": 100, "steppe": 0}}),),
    )

    with pytest.raises(ValueError, match="empty"):
        validate_simulation_result(result, sources=("",))
