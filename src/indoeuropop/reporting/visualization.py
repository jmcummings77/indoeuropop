"""Visualization helpers for simulation outputs and debugging."""

from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from indoeuropop.analysis.debugging import AncestryComparison
from indoeuropop.data.targets import TargetDataset, TargetObservation
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


def plot_ancestry_comparison(comparison: AncestryComparison) -> Figure:
    """Create a Matplotlib figure comparing two ancestry trajectories."""
    figure, axis = plt.subplots()
    axis.plot(
        comparison.times_bce,
        comparison.first_ancestry,
        marker="o",
        label=comparison.first_label,
    )
    axis.plot(
        comparison.times_bce,
        comparison.second_ancestry,
        marker="s",
        label=comparison.second_label,
    )
    axis.set_xlabel("Time (BCE)")
    axis.set_ylabel(f"{comparison.source} ancestry proportion")
    axis.set_ylim(0.0, 1.0)
    axis.invert_xaxis()
    axis.grid(alpha=0.3)
    axis.legend()
    return figure


def plot_target_comparison(
    result: SimulationResult,
    targets: TargetDataset,
    *,
    source: str | None = None,
    region: str | None = None,
) -> Figure:
    """Create a figure comparing simulated ancestry to target observations.

    The optional `source` and `region` arguments filter which target points are
    drawn. They do not change the simulation result; they only keep crowded
    diagnostic plots focused on one source or region when needed.
    """
    observations = _selected_observations(targets, source=source, region=region)
    figure, axis = plt.subplots()
    for observation_region, observation_source in _observation_pairs(observations):
        pair_observations = tuple(
            observation
            for observation in observations
            if observation.region == observation_region
            and observation.source == observation_source
        )
        axis.plot(
            result.times_bce,
            result.ancestry_series(observation_source, observation_region),
            marker="o",
            label=f"simulated {observation_region} {observation_source}",
        )
        axis.errorbar(
            [observation.time_bce for observation in pair_observations],
            [observation.mean for observation in pair_observations],
            yerr=_target_error_bars(pair_observations),
            fmt="s",
            capsize=3,
            label=f"target {observation_region} {observation_source}",
        )
    axis.set_xlabel("Time (BCE)")
    axis.set_ylabel("Ancestry proportion")
    axis.set_ylim(0.0, 1.0)
    axis.invert_xaxis()
    axis.grid(alpha=0.3)
    axis.legend()
    return figure


def _selected_observations(
    targets: TargetDataset,
    *,
    source: str | None,
    region: str | None,
) -> tuple[TargetObservation, ...]:
    """Return target observations matching optional plot filters."""
    observations = tuple(
        observation
        for observation in targets.observations
        if (source is None or observation.source == source)
        and (region is None or observation.region == region)
    )
    if not observations:
        raise ValueError("target dataset has no observations matching plot filters")
    return observations


def _observation_pairs(
    observations: tuple[TargetObservation, ...],
) -> tuple[tuple[str, str], ...]:
    """Return unique region/source pairs in observation order."""
    pairs: list[tuple[str, str]] = []
    for observation in observations:
        pair = (observation.region, observation.source)
        if pair not in pairs:
            pairs.append(pair)
    return tuple(pairs)


def _target_error_bars(
    observations: tuple[TargetObservation, ...],
) -> list[list[float]]:
    """Return asymmetric target errors clipped to valid ancestry bounds."""
    lower_errors = [
        observation.mean - observation.lower_bound for observation in observations
    ]
    upper_errors = [
        observation.upper_bound - observation.mean for observation in observations
    ]
    return [lower_errors, upper_errors]
