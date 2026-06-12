"""Tests for posterior predictive diagnostic summaries."""

from __future__ import annotations

from typing import Any, cast

import pytest

from indoeuropop.analysis.fitting import ScoredSweepRun, TargetFit, score_target_fit
from indoeuropop.analysis.posterior_predictive import (
    PosteriorPredictiveDiagnostics,
    PosteriorPredictiveObservation,
    posterior_predictive_diagnostics,
)
from indoeuropop.analysis.summary import TrajectorySummary
from indoeuropop.data.targets import TargetComparison, TargetObservation
from indoeuropop.models import SimulationParameters
from indoeuropop.orchestration.sweeps import SweepRun

TEST_OBSERVATION = TargetObservation(
    status="synthetic",
    region="britain",
    source="steppe",
    time_bce=2900,
    mean=0.2,
    uncertainty=0.1,
    citation_key="synthetic-constant",
    citation="Synthetic posterior predictive target",
)


def test_posterior_predictive_diagnostics_summarize_accepted_predictions() -> None:
    """Accepted predictions should become target-level residual diagnostics."""
    diagnostics = posterior_predictive_diagnostics(
        (
            _scored_run(0, (0.1, 0.4)),
            _scored_run(1, (0.3, 0.5)),
        ),
        interval_probability=0.5,
    )

    assert diagnostics.observation_count == 2
    assert diagnostics.accepted_count == 2
    assert diagnostics.coverage_count == 1
    assert diagnostics.coverage_rate == pytest.approx(0.5)
    assert diagnostics.mean_absolute_error == pytest.approx(0.225)
    assert diagnostics.root_mean_squared_error == pytest.approx(0.3181980515)
    assert diagnostics.max_abs_z_score == pytest.approx(4.5)
    assert diagnostics.worst_observation.observation_index == 1

    first = diagnostics.observations[0]
    assert first.prediction_mean == pytest.approx(0.2)
    assert first.prediction_median == pytest.approx(0.2)
    assert first.prediction_minimum == pytest.approx(0.1)
    assert first.prediction_maximum == pytest.approx(0.3)
    assert first.lower_interval == pytest.approx(0.15)
    assert first.upper_interval == pytest.approx(0.25)
    assert first.mean_residual == pytest.approx(0.0)
    assert first.absolute_mean_residual == pytest.approx(0.0)
    assert first.mean_z_score == pytest.approx(0.0)
    assert first.observed_inside_interval is True
    assert diagnostics.observations[1].observed_inside_interval is False


@pytest.mark.parametrize("interval_probability", [0.0, 1.0])
def test_posterior_predictive_diagnostics_reject_invalid_interval(
    interval_probability: float,
) -> None:
    """Predictive interval probabilities should be open-interval proportions."""
    with pytest.raises(ValueError, match="interval_probability"):
        posterior_predictive_diagnostics(
            (_scored_run(0, (0.1,)),),
            interval_probability=interval_probability,
        )


def test_posterior_predictive_diagnostics_reject_invalid_run_shapes() -> None:
    """Accepted runs must be non-empty and compare identical observations."""
    with pytest.raises(ValueError, match="at least one"):
        posterior_predictive_diagnostics(())
    with pytest.raises(ValueError, match="target comparisons"):
        posterior_predictive_diagnostics((_scored_run_without_comparisons(),))
    with pytest.raises(ValueError, match="same observations"):
        posterior_predictive_diagnostics(
            (
                _scored_run(0, (0.1,)),
                _scored_run(1, (0.2,), observations=(_observation(1),)),
            )
        )


@pytest.mark.parametrize(
    ("args", "match"),
    [
        ((-1, TEST_OBSERVATION, 1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1), "index"),
        ((0, TEST_OBSERVATION, 0, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1), "accepted_count"),
        (
            (0, TEST_OBSERVATION, 1, float("nan"), 0.1, 0.1, 0.1, 0.1, 0.1),
            "finite",
        ),
        ((0, TEST_OBSERVATION, 1, 0.1, 0.1, 0.2, 0.1, 0.1, 0.1), "minimum"),
        ((0, TEST_OBSERVATION, 1, 0.1, 0.1, 0.1, 0.1, 0.2, 0.1), "lower"),
    ],
)
def test_posterior_predictive_observation_validates_fields(
    args: tuple[object, ...],
    match: str,
) -> None:
    """Manual posterior predictive rows should validate scalar fields."""
    with pytest.raises(ValueError, match=match):
        PosteriorPredictiveObservation(*cast(Any, args))


def test_posterior_predictive_diagnostics_validate_manual_construction() -> None:
    """Diagnostics containers should reject empty rows and invalid intervals."""
    observation = PosteriorPredictiveObservation(
        observation_index=0,
        observation=_observation(0),
        accepted_count=1,
        prediction_mean=0.1,
        prediction_median=0.1,
        prediction_minimum=0.1,
        prediction_maximum=0.1,
        lower_interval=0.1,
        upper_interval=0.1,
    )

    with pytest.raises(ValueError, match="must not be empty"):
        PosteriorPredictiveDiagnostics(())
    with pytest.raises(ValueError, match="interval_probability"):
        PosteriorPredictiveDiagnostics((observation,), interval_probability=1.0)


def _scored_run(
    index: int,
    predictions: tuple[float, ...],
    *,
    observations: tuple[TargetObservation, ...] | None = None,
) -> ScoredSweepRun:
    """Return one accepted scored run with target comparisons."""
    target_observations = (
        tuple(
            _observation(observation_index)
            for observation_index in range(len(predictions))
        )
        if observations is None
        else observations
    )
    comparisons = tuple(
        TargetComparison(observation, prediction)
        for observation, prediction in zip(
            target_observations, predictions, strict=True
        )
    )
    return _scored_run_with_fit(index, score_target_fit(comparisons))


def _scored_run_without_comparisons() -> ScoredSweepRun:
    """Return a scored run whose fit has no target comparisons."""
    return _scored_run_with_fit(
        0,
        TargetFit((), 0.0, 0.0, 0.0, 0.0, 0.0),
    )


def _scored_run_with_fit(index: int, fit: TargetFit) -> ScoredSweepRun:
    """Return one scored run with shared synthetic metadata."""
    return ScoredSweepRun(
        run=SweepRun(
            index=index,
            sampled_values={"migration_rate": 0.001 + index / 1000},
            parameters=SimulationParameters(),
            summary=TrajectorySummary(
                source="steppe",
                region="britain",
                start_bce=3000,
                end_bce=2900,
                initial_ancestry=0.0,
                final_ancestry=0.1,
                ancestry_delta=0.1,
                ancestry_slope_per_century=0.1,
                min_total_population=100.0,
                final_total_population=100.0,
                is_extinct=False,
            ),
        ),
        fit=fit,
    )


def _observation(index: int) -> TargetObservation:
    """Return a synthetic target observation by index."""
    return TargetObservation(
        status="synthetic",
        region="britain",
        source="steppe",
        time_bce=2900 - index * 50,
        mean=0.2 if index == 0 else 0.9,
        uncertainty=0.1,
        citation_key=f"synthetic-{index}",
        citation="Synthetic posterior predictive target",
    )
