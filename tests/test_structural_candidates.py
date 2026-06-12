"""Tests for structural model-candidate analysis helpers."""

from __future__ import annotations

from typing import Any, cast

import pytest

from indoeuropop.analysis.fitting import ScoredSweepRun, score_target_fit
from indoeuropop.analysis.posterior_predictive import posterior_predictive_diagnostics
from indoeuropop.analysis.structural_candidates import (
    MigrationPulseCandidate,
    PosteriorPredictiveMetricDelta,
    apply_migration_pulse_candidate,
    posterior_predictive_metric_delta,
)
from indoeuropop.analysis.summary import TrajectorySummary
from indoeuropop.data.targets import TargetComparison, TargetObservation
from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.orchestration.sweeps import ParameterRange, SweepRun, SweepSpec


def test_apply_migration_pulse_candidate_appends_valid_pulse() -> None:
    """A migration-pulse candidate should append a schedule pulse."""
    candidate = MigrationPulseCandidate(
        name="early central europe",
        region="central_europe",
        start_bce=3000,
        end_bce=2600,
        annual_rate=0.00005,
    )

    updated = apply_migration_pulse_candidate(_spec(), candidate)

    assert updated.schedule.migration_pulses[-1] == candidate.pulse()
    assert updated.schedule.migration_pulses[-1].annual_rate == pytest.approx(0.00005)


def test_apply_migration_pulse_candidate_rejects_unknown_region() -> None:
    """Candidates should target modeled regions in the sweep spec."""
    candidate = MigrationPulseCandidate(
        name="unknown",
        region="iberia",
        start_bce=3000,
        end_bce=2600,
        annual_rate=0.00005,
    )

    with pytest.raises(ValueError, match="candidate region"):
        apply_migration_pulse_candidate(_spec(), candidate)


@pytest.mark.parametrize(
    ("candidate_args", "match"),
    [
        ({"name": "", "region": "central_europe"}, "name"),
        ({"name": "x", "region": ""}, "region"),
        ({"name": "x", "region": "central_europe", "annual_rate": 2.0}, "between"),
    ],
)
def test_migration_pulse_candidate_validates_inputs(
    candidate_args: dict[str, object],
    match: str,
) -> None:
    """Malformed migration-pulse candidates should fail on construction."""
    defaults = {
        "name": "candidate",
        "region": "central_europe",
        "start_bce": 3000,
        "end_bce": 2600,
        "annual_rate": 0.00005,
    }
    defaults.update(candidate_args)

    with pytest.raises(ValueError, match=match):
        MigrationPulseCandidate(**cast(Any, defaults))


def test_posterior_predictive_metric_delta_uses_worst_baseline_by_default() -> None:
    """Metric deltas should compare candidate-minus-baseline diagnostics."""
    baseline = posterior_predictive_diagnostics(
        (_scored_run(0, (0.1, 0.3)), _scored_run(1, (0.2, 0.4)))
    )
    candidate = posterior_predictive_diagnostics(
        (_scored_run(2, (0.2, 0.5)), _scored_run(3, (0.25, 0.55)))
    )

    delta = posterior_predictive_metric_delta(
        baseline,
        candidate,
        candidate_label="early-pulse",
    )

    assert delta.baseline_label == "baseline"
    assert delta.candidate_label == "early-pulse"
    assert delta.focus_observation_index == baseline.worst_observation.observation_index
    assert delta.coverage_rate_delta == pytest.approx(0.0)
    assert delta.root_mean_squared_error_delta < 0
    assert delta.improves_root_mean_squared_error is True
    assert delta.improves_focus_residual is True


def test_posterior_predictive_metric_delta_validates_shapes() -> None:
    """Deltas require aligned diagnostic observation counts and focus indexes."""
    baseline = posterior_predictive_diagnostics((_scored_run(0, (0.1, 0.3)),))
    candidate = posterior_predictive_diagnostics((_scored_run(1, (0.1,)),))

    with pytest.raises(ValueError, match="same observation count"):
        posterior_predictive_metric_delta(baseline, candidate)
    with pytest.raises(ValueError, match="outside diagnostics"):
        posterior_predictive_metric_delta(baseline, baseline, focus_observation_index=2)


def test_posterior_predictive_metric_delta_validates_manual_construction() -> None:
    """Metric-delta dataclasses should validate labels, indexes, and finite values."""
    with pytest.raises(ValueError, match="baseline_label"):
        PosteriorPredictiveMetricDelta("", "candidate", 0, 0, 0, 0, 0, 0)
    with pytest.raises(ValueError, match="candidate_label"):
        PosteriorPredictiveMetricDelta("baseline", "", 0, 0, 0, 0, 0, 0)
    with pytest.raises(ValueError, match="focus_observation_index"):
        PosteriorPredictiveMetricDelta("baseline", "candidate", 0, 0, 0, 0, -1, 0)
    with pytest.raises(ValueError, match="finite"):
        PosteriorPredictiveMetricDelta(
            "baseline", "candidate", float("nan"), 0, 0, 0, 0, 0
        )
    non_improving = PosteriorPredictiveMetricDelta(
        "baseline",
        "candidate",
        0.0,
        0.0,
        0.1,
        0.0,
        0,
        0.1,
    )

    assert non_improving.improves_root_mean_squared_error is False
    assert non_improving.improves_focus_residual is False


def _spec() -> SweepSpec:
    """Return a two-region synthetic sweep spec."""
    return SweepSpec(
        initial_state=PopulationState(
            {
                "central_europe": {"local": 1000, "steppe": 10},
                "britain": {"local": 1000, "steppe": 5},
            }
        ),
        base_parameters=SimulationParameters(),
        parameter_ranges=(ParameterRange("migration_rate", 0.0, 0.001),),
        start_bce=3100,
        end_bce=2900,
        step_years=50,
    )


def _scored_run(index: int, predictions: tuple[float, ...]) -> ScoredSweepRun:
    """Return one synthetic scored run for structural-candidate tests."""
    observations = tuple(_observation(i) for i in range(len(predictions)))
    comparisons = tuple(
        TargetComparison(observation, prediction)
        for observation, prediction in zip(observations, predictions, strict=True)
    )
    return ScoredSweepRun(
        run=SweepRun(
            index=index,
            sampled_values={"migration_rate": 0.001 + index / 1000},
            parameters=SimulationParameters(),
            summary=TrajectorySummary(
                source="steppe",
                region="central_europe",
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
        fit=score_target_fit(comparisons),
    )


def _observation(index: int) -> TargetObservation:
    """Return one synthetic target observation."""
    return TargetObservation(
        status="synthetic",
        region="central_europe",
        source="steppe",
        time_bce=2900 - index * 25,
        mean=0.2 if index == 0 else 0.7,
        uncertainty=0.1,
        citation_key=f"synthetic-{index}",
        citation="Synthetic structural target",
    )
