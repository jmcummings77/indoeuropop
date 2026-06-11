"""Summary statistics for simulated population trajectories."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from indoeuropop.models import SimulationResult


@dataclass(frozen=True)
class TrajectorySummary:
    """Compact statistics for one source trajectory in a simulation result."""

    source: str
    region: str | None
    start_bce: float
    end_bce: float
    initial_ancestry: float
    final_ancestry: float
    ancestry_delta: float
    ancestry_slope_per_century: float
    min_total_population: float
    final_total_population: float
    is_extinct: bool


def summarize_trajectory(
    result: SimulationResult, *, source: str = "steppe", region: str | None = None
) -> TrajectorySummary:
    """Return summary statistics for a simulated ancestry trajectory.

    `ancestry_slope_per_century` is measured over elapsed time, not over the
    numerically decreasing BCE axis. Positive values therefore mean the selected
    source increased as the simulation moved forward through time.
    """
    ancestry = result.ancestry_series(source, region)
    totals = result.total_series(region)
    elapsed_years = result.times_bce[0] - result.times_bce[-1]
    ancestry_delta = float(ancestry[-1] - ancestry[0])
    slope = 0.0 if elapsed_years == 0 else ancestry_delta / elapsed_years * 100.0

    return TrajectorySummary(
        source=source,
        region=region,
        start_bce=result.times_bce[0],
        end_bce=result.times_bce[-1],
        initial_ancestry=float(ancestry[0]),
        final_ancestry=float(ancestry[-1]),
        ancestry_delta=ancestry_delta,
        ancestry_slope_per_century=slope,
        min_total_population=float(np.min(totals)),
        final_total_population=float(totals[-1]),
        is_extinct=bool(totals[-1] == 0),
    )
