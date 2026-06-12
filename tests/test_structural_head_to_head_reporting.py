"""Tests for same-baseline structural head-to-head reports."""

from __future__ import annotations

from pathlib import Path

from indoeuropop.analysis.child_region_candidates import ChildRegionCandidate
from indoeuropop.analysis.fitting import ScoredSweepRun, score_target_fit
from indoeuropop.analysis.posterior_predictive import posterior_predictive_diagnostics
from indoeuropop.analysis.structural_candidates import posterior_predictive_metric_delta
from indoeuropop.analysis.structural_head_to_head import StructuredPulseCandidate
from indoeuropop.analysis.summary import TrajectorySummary
from indoeuropop.data.targets import TargetComparison, TargetObservation
from indoeuropop.models import SimulationParameters
from indoeuropop.orchestration.sweeps import SweepRun
from indoeuropop.reporting.structural_head_to_head import (
    structured_head_to_head_markdown,
    write_structured_head_to_head_markdown,
)


def test_structured_head_to_head_markdown_names_same_baseline_winner(
    tmp_path: Path,
) -> None:
    """Head-to-head reports should identify candidates and the RMSE winner."""
    pulse_candidate = StructuredPulseCandidate(
        name="structured-pulse",
        region_prefix="central_europe__",
        start_bce=3000,
        end_bce=2600,
        annual_rate=0.00005,
    )
    child_candidate = ChildRegionCandidate(
        name="child-best",
        override_path="curation/overrides.toml",
        overridden_region_count=2,
        migration_pulse_count=2,
    )
    baseline = posterior_predictive_diagnostics((_scored_run(0, 0.1),))
    pulse = posterior_predictive_diagnostics((_scored_run(1, 0.3),))
    child = posterior_predictive_diagnostics((_scored_run(2, 0.6),))
    pulse_delta = posterior_predictive_metric_delta(
        baseline, pulse, candidate_label="structured-pulse"
    )
    child_delta = posterior_predictive_metric_delta(
        baseline, child, candidate_label="child-best"
    )
    report_path = tmp_path / "reports" / "head-to-head.md"

    markdown = structured_head_to_head_markdown(
        pulse_candidate,
        2,
        child_candidate,
        baseline,
        pulse,
        child,
        pulse_delta,
        child_delta,
    )
    returned_path = write_structured_head_to_head_markdown(
        pulse_candidate,
        2,
        child_candidate,
        baseline,
        pulse,
        child,
        pulse_delta,
        child_delta,
        report_path,
    )

    assert "# Structured Candidate Head-To-Head" in markdown
    assert "same_baseline: true" in markdown
    assert "structured_pulse_name: structured-pulse" in markdown
    assert "child_candidate_name: child-best" in markdown
    assert "rmse_preferred_candidate: child_override" in markdown
    assert "requested_group_id: Germany_Tiefbrunn_CordedWare-1" in markdown
    assert "parent_region: central_europe" in markdown
    assert returned_path == report_path
    assert report_path.read_text(encoding="utf-8") == markdown


def test_structured_head_to_head_markdown_names_pulse_and_tie_winners() -> None:
    """Report winner labels should cover pulse, child, and tie outcomes."""
    pulse_candidate = StructuredPulseCandidate(
        name="structured-pulse",
        region_prefix="central_europe__",
        start_bce=3000,
        end_bce=2600,
        annual_rate=0.00005,
    )
    child_candidate = ChildRegionCandidate(
        name="child-best",
        override_path="curation/overrides.toml",
        overridden_region_count=2,
        migration_pulse_count=2,
    )
    baseline = posterior_predictive_diagnostics((_scored_run(0, 0.1),))
    pulse_best = posterior_predictive_diagnostics((_scored_run(1, 0.6),))
    child_other = posterior_predictive_diagnostics((_scored_run(2, 0.3),))
    pulse_best_delta = posterior_predictive_metric_delta(baseline, pulse_best)
    child_other_delta = posterior_predictive_metric_delta(baseline, child_other)
    pulse_report = structured_head_to_head_markdown(
        pulse_candidate,
        2,
        child_candidate,
        baseline,
        pulse_best,
        child_other,
        pulse_best_delta,
        child_other_delta,
    )
    tie_report = structured_head_to_head_markdown(
        pulse_candidate,
        2,
        child_candidate,
        baseline,
        child_other,
        child_other,
        child_other_delta,
        child_other_delta,
    )

    assert "rmse_preferred_candidate: structured_pulse" in pulse_report
    assert "rmse_preferred_candidate: tie" in tie_report


def _scored_run(index: int, prediction: float) -> ScoredSweepRun:
    """Return one synthetic scored run for report tests."""
    observation = TargetObservation(
        status="synthetic",
        region="central_europe__germany_tiefbrunn_cordedware_1",
        source="steppe",
        time_bce=2699,
        mean=0.75,
        uncertainty=0.2,
        citation_key="synthetic",
        citation="Synthetic child-region target",
        note=(
            "requested_group_id=Germany_Tiefbrunn_CordedWare-1; "
            "target_id=aadr-central-europe-steppe-germany-tiefbrunn-cordedware-1; "
            "parent_region=central_europe"
        ),
    )
    return ScoredSweepRun(
        run=SweepRun(
            index=index,
            sampled_values={"migration_rate": 0.001 + index / 1000},
            parameters=SimulationParameters(),
            summary=TrajectorySummary(
                source="steppe",
                region="central_europe__germany_tiefbrunn_cordedware_1",
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
