"""Tests for target-fit scoring utilities."""

import pytest

from indoeuropop.fitting import (
    ScoredSweepRun,
    rank_scored_runs,
    run_scored_parameter_sweep,
    score_result_against_targets,
    score_target_fit,
)
from indoeuropop.models import PopulationState, SimulationParameters, SimulationResult
from indoeuropop.summary import TrajectorySummary
from indoeuropop.sweeps import ParameterRange, SweepRun, SweepSpec
from indoeuropop.targets import TargetDataset, TargetObservation


def _target(mean: float, uncertainty: float = 0.1) -> TargetObservation:
    """Build one synthetic target observation for tests."""
    return TargetObservation(
        status="synthetic",
        region="britain",
        source="steppe",
        time_bce=2900,
        mean=mean,
        uncertainty=uncertainty,
        citation_key="synthetic",
        citation="Synthetic test target",
    )


def _result(steppe_count: float) -> SimulationResult:
    """Build a two-point simulation result with a final steppe proportion."""
    return SimulationResult(
        (3000, 2900),
        (
            PopulationState({"britain": {"local": 100, "steppe": 0}}),
            PopulationState(
                {"britain": {"local": 100 - steppe_count, "steppe": steppe_count}}
            ),
        ),
    )


def _scored_run(index: int, chi_square: float) -> ScoredSweepRun:
    """Build a scored run by comparing a synthetic result to a target."""
    result = _result(steppe_count=chi_square)
    fit = score_result_against_targets(result, TargetDataset.from_rows([_target(0.0)]))
    run = SweepRun(
        index=index,
        sampled_values={"migration_rate": float(index)},
        parameters=SimulationParameters(),
        summary=_summary_for_index(index),
    )
    return ScoredSweepRun(run=run, fit=fit)


def _summary_for_index(index: int) -> TrajectorySummary:
    """Return a minimal trajectory summary for a synthetic scored run."""
    return TrajectorySummary(
        source="steppe",
        region="britain",
        start_bce=3000,
        end_bce=2900,
        initial_ancestry=0.0,
        final_ancestry=float(index) / 100,
        ancestry_delta=float(index) / 100,
        ancestry_slope_per_century=float(index) / 100,
        min_total_population=100.0,
        final_total_population=100.0,
        is_extinct=False,
    )


def test_score_result_against_targets_aggregates_residual_metrics() -> None:
    """Target fit scoring should aggregate residual and z-score metrics."""
    fit = score_result_against_targets(
        _result(steppe_count=30),
        TargetDataset.from_rows([_target(0.2), _target(0.4, uncertainty=0.2)]),
    )

    assert fit.observation_count == 2
    assert fit.mean_absolute_error == pytest.approx(0.1)
    assert fit.root_mean_squared_error == pytest.approx(0.1)
    assert fit.chi_square == pytest.approx(1.25)
    assert fit.reduced_chi_square == pytest.approx(0.625)
    assert fit.max_abs_z_score == pytest.approx(1.0)


def test_score_target_fit_rejects_empty_comparisons() -> None:
    """Empty comparison collections should fail clearly."""
    with pytest.raises(ValueError, match="at least one"):
        score_target_fit(())


def test_scored_sweep_run_metric_value_validation() -> None:
    """ScoredSweepRun should expose supported metric values by name."""
    scored = _scored_run(index=1, chi_square=10)

    assert scored.metric_value("chi_square") == scored.fit.chi_square
    with pytest.raises(ValueError, match="unsupported"):
        scored.metric_value("unknown")


def test_rank_scored_runs_sorts_by_selected_metric() -> None:
    """Scored runs should sort from best to worst by fit metric."""
    worse = _scored_run(index=1, chi_square=20)
    better = _scored_run(index=2, chi_square=5)

    ranked = rank_scored_runs((worse, better), metric="root_mean_squared_error")

    assert tuple(scored.run.index for scored in ranked) == (2, 1)


def test_rank_scored_runs_rejects_unknown_metric() -> None:
    """Unsupported ranking metrics should fail explicitly."""
    with pytest.raises(ValueError, match="unsupported"):
        rank_scored_runs((), metric="unknown")


def test_run_scored_parameter_sweep_ranks_samples_by_fit() -> None:
    """A scored deterministic sweep should return ranked parameter samples."""
    targets = TargetDataset.from_rows([_target(0.2, uncertainty=0.05)])
    scored_runs = run_scored_parameter_sweep(
        SweepSpec(
            initial_state=PopulationState({"britain": {"local": 1000, "steppe": 0}}),
            base_parameters=SimulationParameters(
                fertility_rate=0,
                local_mortality_rate=0,
                steppe_mortality_rate=0,
            ),
            parameter_ranges=(ParameterRange("migration_rate", 0.001, 0.003),),
            start_bce=3000,
            end_bce=2900,
            step_years=100,
            sample_count=4,
            seed=3,
            region="britain",
        ),
        targets,
    )

    assert len(scored_runs) == 4
    assert scored_runs[0].fit.chi_square <= scored_runs[-1].fit.chi_square
    assert scored_runs[0].fit.observation_count == 1


def test_run_scored_parameter_sweep_rejects_unknown_metric() -> None:
    """The scored sweep runner should validate ranking metric names."""
    with pytest.raises(ValueError, match="unsupported"):
        run_scored_parameter_sweep(
            SweepSpec(
                initial_state=PopulationState({"britain": {"local": 100, "steppe": 0}}),
                base_parameters=SimulationParameters(),
                parameter_ranges=(ParameterRange("migration_rate", 0.0, 0.0),),
            ),
            TargetDataset.from_rows([_target(0.0)]),
            metric="unknown",
        )
