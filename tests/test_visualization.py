"""Tests for plotting helpers."""

import pytest
from matplotlib.figure import Figure

from indoeuropop.analysis.debugging import compare_ancestry_trajectories
from indoeuropop.data.targets import TargetDataset, TargetObservation
from indoeuropop.models import PopulationState, SimulationResult
from indoeuropop.reporting.visualization import (
    plot_ancestry,
    plot_ancestry_comparison,
    plot_population_total,
    plot_target_comparison,
)


def test_plot_helpers_return_figures() -> None:
    """Plot helpers should work in headless test environments."""
    result = SimulationResult(
        (3000, 2950),
        (
            PopulationState({"britain": {"local": 100, "steppe": 0}}),
            PopulationState({"britain": {"local": 90, "steppe": 10}}),
        ),
    )

    ancestry_figure = plot_ancestry(result, source="steppe", region="britain")
    total_figure = plot_population_total(result, region="britain")

    assert isinstance(ancestry_figure, Figure)
    assert isinstance(total_figure, Figure)


def test_plot_ancestry_comparison_returns_figure() -> None:
    """Comparison plots should work in headless test environments."""
    first = SimulationResult(
        (3000, 2950),
        (
            PopulationState({"britain": {"local": 100, "steppe": 0}}),
            PopulationState({"britain": {"local": 90, "steppe": 10}}),
        ),
    )
    second = SimulationResult(
        (3000, 2950),
        (
            PopulationState({"britain": {"local": 95, "steppe": 5}}),
            PopulationState({"britain": {"local": 80, "steppe": 20}}),
        ),
    )
    comparison = compare_ancestry_trajectories(
        first,
        second,
        source="steppe",
        region="britain",
        first_label="first",
        second_label="second",
    )

    figure = plot_ancestry_comparison(comparison)

    assert isinstance(figure, Figure)


def test_plot_target_comparison_returns_figure() -> None:
    """Target overlay plots should work in headless test environments."""
    result = SimulationResult(
        (3000, 2950),
        (
            PopulationState({"britain": {"local": 100, "steppe": 0}}),
            PopulationState({"britain": {"local": 90, "steppe": 10}}),
        ),
    )
    targets = TargetDataset.from_rows(
        [
            TargetObservation(
                status="synthetic",
                region="britain",
                source="steppe",
                time_bce=2950,
                mean=0.1,
                uncertainty=0.03,
                citation_key="synthetic",
                citation="Synthetic target",
            )
        ]
    )

    figure = plot_target_comparison(result, targets, source="steppe")

    assert isinstance(figure, Figure)


def test_plot_target_comparison_rejects_empty_filter() -> None:
    """Target overlay plots should fail clearly when filters remove all rows."""
    result = SimulationResult(
        (3000, 2950),
        (
            PopulationState({"britain": {"local": 100, "steppe": 0}}),
            PopulationState({"britain": {"local": 90, "steppe": 10}}),
        ),
    )
    targets = TargetDataset.from_rows(
        [
            TargetObservation(
                status="synthetic",
                region="britain",
                source="steppe",
                time_bce=2950,
                mean=0.1,
                uncertainty=0.03,
                citation_key="synthetic",
                citation="Synthetic target",
            )
        ]
    )

    with pytest.raises(ValueError, match="no observations"):
        plot_target_comparison(result, targets, region="iberia")
