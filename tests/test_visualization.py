"""Tests for plotting helpers."""

from matplotlib.figure import Figure

from indoeuropop.models import PopulationState, SimulationResult
from indoeuropop.visualization import plot_ancestry, plot_population_total


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
