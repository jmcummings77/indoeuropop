"""Tests for trajectory summary statistics."""

import pytest

from indoeuropop.models import PopulationState, SimulationResult
from indoeuropop.summary import summarize_trajectory


def test_summarize_trajectory_reports_ancestry_and_population_metrics() -> None:
    """Trajectory summaries should expose compact deterministic statistics."""
    result = SimulationResult(
        (3000, 2900),
        (
            PopulationState({"britain": {"local": 100, "steppe": 0}}),
            PopulationState({"britain": {"local": 50, "steppe": 50}}),
        ),
    )

    summary = summarize_trajectory(result, source="steppe", region="britain")

    assert summary.source == "steppe"
    assert summary.region == "britain"
    assert summary.start_bce == 3000
    assert summary.end_bce == 2900
    assert summary.initial_ancestry == 0
    assert summary.final_ancestry == 0.5
    assert summary.ancestry_delta == 0.5
    assert summary.ancestry_slope_per_century == pytest.approx(0.5)
    assert summary.min_total_population == 100
    assert summary.final_total_population == 100
    assert not summary.is_extinct


def test_summarize_trajectory_handles_zero_elapsed_time() -> None:
    """A single-state result should have a zero slope instead of dividing by zero."""
    result = SimulationResult(
        (3000,),
        (PopulationState({"britain": {"local": 0, "steppe": 0}}),),
    )

    summary = summarize_trajectory(result, source="steppe", region="britain")

    assert summary.ancestry_slope_per_century == 0
    assert summary.is_extinct
