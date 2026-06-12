"""Tests for structural model-candidate reports."""

from __future__ import annotations

from pathlib import Path

from indoeuropop.analysis.fitting import ScoredSweepRun, score_target_fit
from indoeuropop.analysis.posterior_predictive import posterior_predictive_diagnostics
from indoeuropop.analysis.structural_candidates import (
    MigrationPulseCandidate,
    posterior_predictive_metric_delta,
)
from indoeuropop.analysis.summary import TrajectorySummary
from indoeuropop.data.targets import TargetComparison, TargetObservation
from indoeuropop.models import SimulationParameters
from indoeuropop.orchestration.sweeps import SweepRun
from indoeuropop.reporting.structural_candidates import (
    migration_pulse_candidate_markdown,
    write_migration_pulse_candidate_markdown,
)


def test_migration_pulse_candidate_markdown_summarizes_deltas(tmp_path: Path) -> None:
    """Structural-candidate reports should compare baseline and candidate fits."""
    candidate = MigrationPulseCandidate(
        name="early-central-europe",
        region="central_europe",
        start_bce=3000,
        end_bce=2600,
        annual_rate=0.00005,
    )
    baseline = posterior_predictive_diagnostics((_scored_run(0, 0.1),))
    candidate_diagnostics = posterior_predictive_diagnostics((_scored_run(1, 0.3),))
    delta = posterior_predictive_metric_delta(baseline, candidate_diagnostics)
    report_path = tmp_path / "reports" / "candidate.md"

    markdown = migration_pulse_candidate_markdown(
        candidate,
        baseline,
        candidate_diagnostics,
        delta,
    )
    returned_path = write_migration_pulse_candidate_markdown(
        candidate,
        baseline,
        candidate_diagnostics,
        delta,
        report_path,
    )

    assert "# Migration Pulse Candidate: early-central-europe" in markdown
    assert "requested_group_id: Germany_Tiefbrunn_CordedWare-1" in markdown
    assert "| root_mean_squared_error |" in markdown
    assert "absolute_residual_delta" in markdown
    assert returned_path == report_path
    assert report_path.read_text(encoding="utf-8") == markdown


def _scored_run(index: int, prediction: float) -> ScoredSweepRun:
    """Return one synthetic scored run for report tests."""
    observation = TargetObservation(
        status="synthetic",
        region="central_europe",
        source="steppe",
        time_bce=2699,
        mean=0.75,
        uncertainty=0.2,
        citation_key="synthetic",
        citation="Synthetic structural target",
        note=(
            "requested_group_id=Germany_Tiefbrunn_CordedWare-1; "
            "target_id=aadr-central-europe-steppe-germany-tiefbrunn-cordedware-1"
        ),
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
