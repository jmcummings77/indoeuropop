"""Posterior predictive diagnostics for accepted target-fit samples."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite

import numpy as np

from indoeuropop.analysis.fitting import ScoredSweepRun
from indoeuropop.data.targets import TargetComparison, TargetObservation


@dataclass(frozen=True)
class PosteriorPredictiveObservation:
    """Predictive summary for one target observation across accepted samples."""

    observation_index: int
    observation: TargetObservation
    accepted_count: int
    prediction_mean: float
    prediction_median: float
    prediction_minimum: float
    prediction_maximum: float
    lower_interval: float
    upper_interval: float

    def __post_init__(self) -> None:
        """Validate finite prediction summaries and interval ordering."""
        if self.observation_index < 0:
            raise ValueError("observation_index must be non-negative")
        if self.accepted_count <= 0:
            raise ValueError("accepted_count must be positive")
        values = (
            self.prediction_mean,
            self.prediction_median,
            self.prediction_minimum,
            self.prediction_maximum,
            self.lower_interval,
            self.upper_interval,
        )
        if any(not isfinite(value) for value in values):
            raise ValueError("posterior predictive values must be finite")
        if self.prediction_minimum > self.prediction_maximum:
            raise ValueError("prediction_minimum must be less than prediction_maximum")
        if self.lower_interval > self.upper_interval:
            raise ValueError("lower_interval must be less than upper_interval")

    @property
    def mean_residual(self) -> float:
        """Return predictive mean minus observed mean."""
        return self.prediction_mean - self.observation.mean

    @property
    def absolute_mean_residual(self) -> float:
        """Return absolute residual for the predictive mean."""
        return abs(self.mean_residual)

    @property
    def mean_z_score(self) -> float:
        """Return mean residual scaled by observation uncertainty."""
        return self.mean_residual / self.observation.uncertainty

    @property
    def observed_inside_interval(self) -> bool:
        """Return whether the observed mean lies inside the predictive interval."""
        return self.lower_interval <= self.observation.mean <= self.upper_interval


@dataclass(frozen=True)
class PosteriorPredictiveDiagnostics:
    """Collection-level posterior predictive fit diagnostics."""

    observations: tuple[PosteriorPredictiveObservation, ...]
    interval_probability: float = 0.9

    def __post_init__(self) -> None:
        """Validate diagnostics shape and interval probability."""
        if not self.observations:
            raise ValueError("observations must not be empty")
        if not 0 < self.interval_probability < 1:
            raise ValueError("interval_probability must be in (0, 1)")

    @property
    def observation_count(self) -> int:
        """Return the number of target observations summarized."""
        return len(self.observations)

    @property
    def accepted_count(self) -> int:
        """Return the accepted sample count used for each observation."""
        return self.observations[0].accepted_count

    @property
    def coverage_count(self) -> int:
        """Return the number of observed means inside predictive intervals."""
        return sum(
            observation.observed_inside_interval for observation in self.observations
        )

    @property
    def coverage_rate(self) -> float:
        """Return the fraction of observed means inside predictive intervals."""
        return self.coverage_count / self.observation_count

    @property
    def mean_absolute_error(self) -> float:
        """Return mean absolute residual for predictive means."""
        return float(
            np.mean(
                [
                    observation.absolute_mean_residual
                    for observation in self.observations
                ]
            )
        )

    @property
    def root_mean_squared_error(self) -> float:
        """Return root mean squared residual for predictive means."""
        return float(
            np.sqrt(
                np.mean(
                    [observation.mean_residual**2 for observation in self.observations]
                )
            )
        )

    @property
    def max_abs_z_score(self) -> float:
        """Return the maximum absolute predictive-mean z-score."""
        return max(abs(observation.mean_z_score) for observation in self.observations)

    @property
    def worst_observation(self) -> PosteriorPredictiveObservation:
        """Return the observation with the largest absolute predictive residual."""
        return max(
            self.observations,
            key=lambda observation: observation.absolute_mean_residual,
        )


def posterior_predictive_diagnostics(
    accepted_runs: Iterable[ScoredSweepRun],
    *,
    interval_probability: float = 0.9,
) -> PosteriorPredictiveDiagnostics:
    """Summarize accepted predictions against each target observation."""
    if not 0 < interval_probability < 1:
        raise ValueError("interval_probability must be in (0, 1)")
    runs = tuple(accepted_runs)
    if not runs:
        raise ValueError("accepted_runs must contain at least one run")
    comparison_matrix = _comparison_matrix(runs)
    lower_quantile = (1 - interval_probability) / 2
    upper_quantile = 1 - lower_quantile
    observations = tuple(
        _predictive_observation(
            index,
            tuple(
                run_comparisons[index].predicted
                for run_comparisons in comparison_matrix
            ),
            comparison_matrix[0][index].observation,
            interval_quantiles=(lower_quantile, upper_quantile),
        )
        for index in range(len(comparison_matrix[0]))
    )
    return PosteriorPredictiveDiagnostics(
        observations=observations,
        interval_probability=interval_probability,
    )


def _comparison_matrix(
    accepted_runs: tuple[ScoredSweepRun, ...],
) -> tuple[tuple[TargetComparison, ...], ...]:
    """Return accepted fit comparisons after validating target alignment."""
    comparisons = tuple(scored_run.fit.comparisons for scored_run in accepted_runs)
    if not comparisons[0]:
        raise ValueError("accepted runs must contain target comparisons")
    expected_observations = tuple(
        comparison.observation for comparison in comparisons[0]
    )
    for run_comparisons in comparisons[1:]:
        observed = tuple(comparison.observation for comparison in run_comparisons)
        if observed != expected_observations:
            raise ValueError("accepted runs must compare the same observations")
    return comparisons


def _predictive_observation(
    observation_index: int,
    predictions: tuple[float, ...],
    observation: TargetObservation,
    *,
    interval_quantiles: tuple[float, float],
) -> PosteriorPredictiveObservation:
    """Return one target-level posterior predictive summary."""
    values = np.array(predictions, dtype=np.float64)
    lower_interval, upper_interval = np.quantile(values, interval_quantiles)
    return PosteriorPredictiveObservation(
        observation_index=observation_index,
        observation=observation,
        accepted_count=len(predictions),
        prediction_mean=float(np.mean(values)),
        prediction_median=float(np.median(values)),
        prediction_minimum=float(np.min(values)),
        prediction_maximum=float(np.max(values)),
        lower_interval=float(lower_interval),
        upper_interval=float(upper_interval),
    )
