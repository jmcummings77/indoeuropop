"""Tests for ABC-style rejection inference helpers."""

from __future__ import annotations

from typing import Any, cast

import pytest

from indoeuropop.analysis.fitting import ScoredSweepRun, score_target_fit
from indoeuropop.analysis.inference import (
    ABCRejectionOptions,
    ABCRejectionResult,
    PosteriorParameterSummary,
    posterior_parameter_summaries,
    run_abc_rejection_inference,
)
from indoeuropop.analysis.summary import TrajectorySummary
from indoeuropop.data.targets import TargetComparison, TargetObservation
from indoeuropop.models import SimulationParameters
from indoeuropop.orchestration.sweeps import SweepRun


def test_abc_rejection_accepts_best_count_and_summarizes_parameters() -> None:
    """Count-based rejection should retain the best-ranked parameter samples."""
    result = run_abc_rejection_inference(
        (
            _scored_run(0, 0.3),
            _scored_run(1, 0.1),
            _scored_run(2, 0.2),
            _scored_run(3, 0.4),
        ),
        ABCRejectionOptions(acceptance_count=2),
    )

    assert result.candidate_count == 4
    assert result.accepted_count == 2
    assert result.acceptance_rate == 0.5
    assert result.acceptance_threshold == pytest.approx(0.2)
    assert result.best_run.run.index == 1
    assert tuple(run.run.index for run in result.accepted_runs) == (1, 2)
    summary_by_name = {
        summary.parameter: summary for summary in result.parameter_summaries
    }
    assert summary_by_name["migration_rate"].mean == pytest.approx(0.0015)
    assert summary_by_name["climate_stress"].accepted_count == 2


def test_abc_rejection_supports_quantile_and_threshold_criteria() -> None:
    """Quantile and threshold criteria should expose clear criterion labels."""
    scored_runs = (_scored_run(0, 0.3), _scored_run(1, 0.1), _scored_run(2, 0.2))

    quantile = run_abc_rejection_inference(
        scored_runs,
        ABCRejectionOptions(acceptance_quantile=0.5),
    )
    threshold = run_abc_rejection_inference(
        scored_runs,
        ABCRejectionOptions(acceptance_threshold=0.2),
    )

    assert quantile.options.criterion == "quantile"
    assert tuple(run.run.index for run in quantile.accepted_runs) == (1, 2)
    assert threshold.options.criterion == "threshold"
    assert tuple(run.run.index for run in threshold.accepted_runs) == (1, 2)


@pytest.mark.parametrize(
    ("options", "match"),
    [
        (ABCRejectionOptions(acceptance_count=3), "cannot exceed"),
        (ABCRejectionOptions(acceptance_threshold=0.01), "accepted no runs"),
    ],
)
def test_abc_rejection_reports_impossible_acceptance(
    options: ABCRejectionOptions, match: str
) -> None:
    """Impossible acceptance requests should fail before summaries are built."""
    with pytest.raises(ValueError, match=match):
        run_abc_rejection_inference((_scored_run(0, 0.2),), options)


def test_abc_rejection_rejects_empty_scored_runs() -> None:
    """At least one scored run is required for rejection inference."""
    with pytest.raises(ValueError, match="at least one"):
        run_abc_rejection_inference(())


@pytest.mark.parametrize(
    ("options", "match"),
    [
        ({"fit_metric": "unknown"}, "unsupported"),
        ({"acceptance_count": 0}, "acceptance_count"),
        ({"acceptance_threshold": float("nan")}, "finite"),
        ({"acceptance_threshold": -0.1}, "non-negative"),
        ({"acceptance_quantile": 0.0}, "acceptance_quantile"),
        ({"acceptance_quantile": 1.1}, "acceptance_quantile"),
    ],
)
def test_abc_rejection_options_validate_inputs(
    options: dict[str, object], match: str
) -> None:
    """Malformed inference controls should fail explicitly."""
    with pytest.raises(ValueError, match=match):
        ABCRejectionOptions(**cast(Any, options))


def test_posterior_parameter_summaries_validate_run_shapes() -> None:
    """Accepted runs must share non-empty sampled parameter keys."""
    with pytest.raises(ValueError, match="at least one"):
        posterior_parameter_summaries(())
    with pytest.raises(ValueError, match="sampled parameter"):
        posterior_parameter_summaries((_scored_run(0, 0.2, sampled_values={}),))
    with pytest.raises(ValueError, match="same sampled"):
        posterior_parameter_summaries(
            (
                _scored_run(0, 0.2, sampled_values={"migration_rate": 0.1}),
                _scored_run(1, 0.1, sampled_values={"climate_stress": 0.2}),
            )
        )


@pytest.mark.parametrize(
    ("summary_args", "match"),
    [
        (
            ("", 1, 1, 1, 1, 1, 1, 1),
            "parameter",
        ),
        (
            ("x", 0, 1, 1, 1, 1, 1, 1),
            "accepted_count",
        ),
        (
            ("x", 1, float("inf"), 1, 1, 1, 1, 1),
            "finite",
        ),
        (
            ("x", 1, 1, 1, 2, 1, 1, 1),
            "minimum",
        ),
        (
            ("x", 1, 1, 1, 1, 1, 2, 1),
            "lower_interval",
        ),
    ],
)
def test_posterior_parameter_summary_validates_fields(
    summary_args: tuple[object, ...], match: str
) -> None:
    """Posterior summary fields should be validated on construction."""
    with pytest.raises(ValueError, match=match):
        PosteriorParameterSummary(*cast(Any, summary_args))


def test_abc_rejection_result_validates_consistency() -> None:
    """Inference result objects should reject inconsistent manual construction."""
    options = ABCRejectionOptions()
    run = _scored_run(1, 0.1)
    summary = PosteriorParameterSummary("migration_rate", 1, 1, 1, 1, 1, 1, 1)

    with pytest.raises(ValueError, match="ranked_runs"):
        ABCRejectionResult(options, (), (run,), (summary,), 0.1)
    with pytest.raises(ValueError, match="accepted_runs"):
        ABCRejectionResult(options, (run,), (), (summary,), 0.1)
    with pytest.raises(ValueError, match="cannot exceed"):
        ABCRejectionResult(options, (run,), (run, run), (summary,), 0.1)
    with pytest.raises(ValueError, match="acceptance_threshold"):
        ABCRejectionResult(options, (run,), (run,), (summary,), -0.1)
    with pytest.raises(ValueError, match="parameter_summaries"):
        ABCRejectionResult(options, (run,), (run,), (), 0.1)


def _scored_run(
    index: int,
    residual: float,
    *,
    sampled_values: dict[str, float] | None = None,
) -> ScoredSweepRun:
    """Return one synthetic scored run for inference tests."""
    observation = TargetObservation(
        status="synthetic",
        region="britain",
        source="steppe",
        time_bce=2900,
        mean=0.0,
        uncertainty=1.0,
        citation_key="synthetic",
        citation="Synthetic target",
    )
    return ScoredSweepRun(
        run=SweepRun(
            index=index,
            sampled_values=(
                {
                    "migration_rate": index / 1000,
                    "climate_stress": index / 100,
                }
                if sampled_values is None
                else sampled_values
            ),
            parameters=SimulationParameters(),
            summary=TrajectorySummary(
                source="steppe",
                region="britain",
                start_bce=3000,
                end_bce=2900,
                initial_ancestry=0.0,
                final_ancestry=residual,
                ancestry_delta=residual,
                ancestry_slope_per_century=residual,
                min_total_population=100.0,
                final_total_population=100.0,
                is_extinct=False,
            ),
        ),
        fit=score_target_fit((TargetComparison(observation, residual),)),
    )
