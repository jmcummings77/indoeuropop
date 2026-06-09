"""Visualization helpers for simulation outputs and debugging."""

from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from indoeuropop.models import SimulationResult


def plot_ancestry(
    result: SimulationResult,
    *,
    source: str = "steppe",
    region: str | None = None,
) -> Figure:
    """Create a Matplotlib figure for ancestry proportion over time."""
    figure, axis = plt.subplots()
    axis.plot(result.times_bce, result.ancestry_series(source, region), marker="o")
    axis.set_xlabel("Time (BCE)")
    axis.set_ylabel(f"{source} ancestry proportion")
    axis.set_ylim(0.0, 1.0)
    axis.invert_xaxis()
    axis.grid(alpha=0.3)
    return figure


def plot_population_total(
    result: SimulationResult,
    *,
    region: str | None = None,
) -> Figure:
    """Create a Matplotlib figure for total population over time."""
    figure, axis = plt.subplots()
    axis.plot(result.times_bce, result.total_series(region), marker="o")
    axis.set_xlabel("Time (BCE)")
    axis.set_ylabel("Population count")
    axis.invert_xaxis()
    axis.grid(alpha=0.3)
    return figure
