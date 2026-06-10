"""Target-fit scoring for simulation results and parameter sweeps."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

from indoeuropop.models import SimulationResult
from indoeuropop.simulation import run_deterministic
from indoeuropop.summary import summarize_trajectory
from indoeuropop.sweeps import (
    SweepRun,
    SweepSpec,
    latin_hypercube_samples,
    parameters_with_overrides,
)
from indoeuropop.targets import TargetComparison, TargetDataset

FIT_METRICS = frozenset(
    {
        "chi_square",
        "reduced_chi_square",
        "root_mean_squared_error",
        "mean_absolute_error",
        "max_abs_z_score",
    }
)


@dataclass(frozen=True)
class TargetFit:
    """Aggregate fit statistics for target comparisons."""

    comparisons: tuple[TargetComparison, ...]
    mean_absolute_error: float
    root_mean_squared_error: float
    chi_square: float
    reduced_chi_square: float
    max_abs_z_score: float

    @property
    def observation_count(self) -> int:
        """Return the number of target observations included in this fit."""
        return len(self.comparisons)


@dataclass(frozen=True)
class ScoredSweepRun:
    """A sweep run paired with its target-fit statistics."""

    run: SweepRun
    fit: TargetFit

    def metric_value(self, metric: str) -> float:
        """Return one supported fit metric value."""
        if metric not in FIT_METRICS:
            raise ValueError(f"unsupported fit metric: {metric}")
        return float(getattr(self.fit, metric))


def score_target_fit(comparisons: Iterable[TargetComparison]) -> TargetFit:
    """Aggregate residual-based fit metrics from target comparisons."""
    comparison_tuple = tuple(comparisons)
    if not comparison_tuple:
        raise ValueError("comparisons must contain at least one target comparison")

    residuals = np.array(
        [comparison.residual for comparison in comparison_tuple], dtype=np.float64
    )
    z_scores = np.array(
        [comparison.z_score for comparison in comparison_tuple], dtype=np.float64
    )
    chi_square = float(np.sum(z_scores**2))
    return TargetFit(
        comparisons=comparison_tuple,
        mean_absolute_error=float(np.mean(np.abs(residuals))),
        root_mean_squared_error=float(np.sqrt(np.mean(residuals**2))),
        chi_square=chi_square,
        reduced_chi_square=chi_square / len(comparison_tuple),
        max_abs_z_score=float(np.max(np.abs(z_scores))),
    )


def score_result_against_targets(
    result: SimulationResult, targets: TargetDataset
) -> TargetFit:
    """Compare a simulation result to targets and return aggregate fit metrics."""
    return score_target_fit(targets.compare(result))


def rank_scored_runs(
    scored_runs: Iterable[ScoredSweepRun], *, metric: str = "chi_square"
) -> tuple[ScoredSweepRun, ...]:
    """Return scored sweep runs sorted from best to worst by a fit metric."""
    if metric not in FIT_METRICS:
        raise ValueError(f"unsupported fit metric: {metric}")
    return tuple(
        sorted(scored_runs, key=lambda scored_run: scored_run.metric_value(metric))
    )


def run_scored_parameter_sweep(
    spec: SweepSpec, targets: TargetDataset, *, metric: str = "chi_square"
) -> tuple[ScoredSweepRun, ...]:
    """Run a deterministic parameter sweep and rank samples by target fit."""
    sampled_values = latin_hypercube_samples(
        spec.parameter_ranges, sample_count=spec.sample_count, seed=spec.seed
    )
    scored_runs: list[ScoredSweepRun] = []
    for index, values in enumerate(sampled_values):
        parameters = parameters_with_overrides(spec.base_parameters, values)
        result = run_deterministic(
            spec.initial_state,
            parameters,
            start_bce=spec.start_bce,
            end_bce=spec.end_bce,
            step_years=spec.step_years,
            schedule=spec.schedule,
            parameter_set=spec.parameter_set,
        )
        sweep_run = SweepRun(
            index=index,
            sampled_values=values,
            parameters=parameters,
            summary=summarize_trajectory(
                result, source=spec.source, region=spec.region
            ),
        )
        scored_runs.append(
            ScoredSweepRun(
                run=sweep_run,
                fit=score_result_against_targets(result, targets),
            )
        )
    return rank_scored_runs(scored_runs, metric=metric)
