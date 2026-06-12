"""Tests for ABC rejection inference report serializers."""

from __future__ import annotations

from pathlib import Path

from indoeuropop.analysis.fitting import ScoredSweepRun, score_target_fit
from indoeuropop.analysis.inference import (
    ABCRejectionOptions,
    run_abc_rejection_inference,
)
from indoeuropop.analysis.summary import TrajectorySummary
from indoeuropop.data.targets import TargetComparison, TargetObservation
from indoeuropop.models import SimulationParameters
from indoeuropop.orchestration.sweeps import SweepRun
from indoeuropop.reporting.inference import (
    POSTERIOR_SUMMARY_FIELDS,
    abc_rejection_markdown,
    accepted_sample_fieldnames,
    accepted_sample_rows,
    accepted_samples_to_csv,
    posterior_summaries_to_csv,
    posterior_summary_rows,
    write_abc_rejection_markdown,
    write_accepted_samples_csv,
    write_posterior_summaries_csv,
)


def test_accepted_sample_exports_use_stable_dynamic_schema(tmp_path: Path) -> None:
    """Accepted inference samples should serialize with sampled parameter fields."""
    result = run_abc_rejection_inference(
        (_scored_run(0, 0.3), _scored_run(1, 0.1)),
        ABCRejectionOptions(acceptance_count=1),
    )
    samples_path = tmp_path / "reports" / "samples.csv"

    assert accepted_sample_fieldnames(result) == (
        "accepted_rank",
        "run_index",
        "fit_metric",
        "fit_metric_value",
        "fit_observation_count",
        "sampled_climate_stress",
        "sampled_migration_rate",
    )
    rows = accepted_sample_rows(result)
    csv_text = accepted_samples_to_csv(result)
    returned_path = write_accepted_samples_csv(result, samples_path)

    assert rows[0]["accepted_rank"] == "1"
    assert rows[0]["run_index"] == "1"
    assert rows[0]["fit_metric_value"] == "0.1"
    assert csv_text.startswith("accepted_rank,run_index,fit_metric")
    assert returned_path == samples_path
    assert samples_path.read_text(encoding="utf-8") == csv_text


def test_posterior_summary_exports_and_markdown(tmp_path: Path) -> None:
    """Posterior summaries and Markdown reports should be human-readable."""
    result = run_abc_rejection_inference(
        (_scored_run(1, 0.1), _scored_run(2, 0.2)),
        ABCRejectionOptions(acceptance_count=2),
    )
    summary_path = tmp_path / "reports" / "summary.csv"
    report_path = tmp_path / "reports" / "inference.md"

    rows = posterior_summary_rows(result.parameter_summaries)
    summary_csv = posterior_summaries_to_csv(result.parameter_summaries)
    markdown = abc_rejection_markdown(result)

    assert POSTERIOR_SUMMARY_FIELDS[0] == "parameter"
    assert rows[0]["accepted_count"] == "2"
    assert summary_csv.startswith("parameter,accepted_count,mean")
    assert "engineering inference scaffold" in markdown
    assert "best_run_index: 1" in markdown
    assert (
        write_posterior_summaries_csv(result.parameter_summaries, summary_path)
        == summary_path
    )
    assert write_abc_rejection_markdown(result, report_path) == report_path
    assert summary_path.read_text(encoding="utf-8") == summary_csv
    assert report_path.read_text(encoding="utf-8") == markdown


def _scored_run(index: int, residual: float) -> ScoredSweepRun:
    """Return one synthetic scored run for reporting tests."""
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
            sampled_values={
                "migration_rate": index / 1000,
                "climate_stress": index / 100,
            },
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
