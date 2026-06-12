"""Tests for posterior predictive report serializers and plots."""

from __future__ import annotations

from pathlib import Path

from matplotlib.figure import Figure

from indoeuropop.analysis.fitting import ScoredSweepRun, score_target_fit
from indoeuropop.analysis.posterior_predictive import posterior_predictive_diagnostics
from indoeuropop.analysis.summary import TrajectorySummary
from indoeuropop.data.targets import TargetComparison, TargetObservation
from indoeuropop.models import SimulationParameters
from indoeuropop.orchestration.sweeps import SweepRun
from indoeuropop.reporting.posterior_predictive import (
    POSTERIOR_PREDICTIVE_FIELDS,
    plot_posterior_predictive_diagnostics,
    posterior_predictive_markdown,
    posterior_predictive_rows,
    posterior_predictive_to_csv,
    write_posterior_predictive_csv,
    write_posterior_predictive_markdown,
    write_posterior_predictive_plot,
)


def test_posterior_predictive_exports_and_markdown(tmp_path: Path) -> None:
    """Posterior predictive reports should serialize rows and summaries."""
    diagnostics = posterior_predictive_diagnostics(
        (_scored_run(0, 0.1), _scored_run(1, 0.3)),
        interval_probability=0.5,
    )
    csv_path = tmp_path / "diagnostics" / "posterior.csv"
    markdown_path = tmp_path / "diagnostics" / "posterior.md"

    rows = posterior_predictive_rows(diagnostics)
    csv_text = posterior_predictive_to_csv(diagnostics)
    markdown = posterior_predictive_markdown(diagnostics, title="Calibration Check")

    assert POSTERIOR_PREDICTIVE_FIELDS[0] == "observation_index"
    assert rows[0]["observed_inside_interval"] == "true"
    assert rows[0]["prediction_mean"] == "0.2"
    assert csv_text.startswith("observation_index,region,source")
    assert "# Calibration Check" in markdown
    assert "coverage_rate: 1.000000" in markdown
    assert "| 0 | britain | steppe | 2900 |" in markdown
    assert write_posterior_predictive_csv(diagnostics, csv_path) == csv_path
    assert (
        write_posterior_predictive_markdown(
            diagnostics, markdown_path, title="Calibration Check"
        )
        == markdown_path
    )
    assert csv_path.read_text(encoding="utf-8") == csv_text
    assert markdown_path.read_text(encoding="utf-8") == markdown


def test_posterior_predictive_plot_returns_and_writes_figure(tmp_path: Path) -> None:
    """Posterior predictive plots should work without a display."""
    diagnostics = posterior_predictive_diagnostics(
        (_scored_run(0, 0.1), _scored_run(1, 0.3)),
    )
    plot_path = tmp_path / "diagnostics" / "posterior.png"

    figure = plot_posterior_predictive_diagnostics(diagnostics)
    returned_path = write_posterior_predictive_plot(diagnostics, plot_path)

    assert isinstance(figure, Figure)
    assert len(figure.axes) == 2
    assert returned_path == plot_path
    assert plot_path.exists()


def _scored_run(index: int, prediction: float) -> ScoredSweepRun:
    """Return one synthetic scored run for posterior predictive reports."""
    observation = TargetObservation(
        status="synthetic",
        region="britain",
        source="steppe",
        time_bce=2900,
        mean=0.2,
        uncertainty=0.1,
        citation_key="synthetic",
        citation="Synthetic posterior predictive target",
    )
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
                final_ancestry=prediction,
                ancestry_delta=prediction,
                ancestry_slope_per_century=prediction,
                min_total_population=100.0,
                final_total_population=100.0,
                is_extinct=False,
            ),
        ),
        fit=score_target_fit((TargetComparison(observation, prediction),)),
    )
