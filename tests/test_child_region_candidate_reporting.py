"""Tests for child-region structural candidate reports."""

from __future__ import annotations

from pathlib import Path

from indoeuropop.analysis.child_region_candidates import (
    ChildRegionCandidate,
    StructuralComparisonReference,
)
from indoeuropop.analysis.fitting import ScoredSweepRun, score_target_fit
from indoeuropop.analysis.posterior_predictive import posterior_predictive_diagnostics
from indoeuropop.analysis.structural_candidates import posterior_predictive_metric_delta
from indoeuropop.analysis.summary import TrajectorySummary
from indoeuropop.data.targets import TargetComparison, TargetObservation
from indoeuropop.models import SimulationParameters
from indoeuropop.orchestration.sweeps import SweepRun
from indoeuropop.reporting.child_region_candidates import (
    child_region_candidate_markdown,
    write_child_region_candidate_markdown,
)


def test_child_region_candidate_markdown_summarizes_reference(
    tmp_path: Path,
) -> None:
    """Reports should compare child-region diagnostics with a reference run."""
    baseline = posterior_predictive_diagnostics((_scored_run(0, 0.1),))
    candidate_diagnostics = posterior_predictive_diagnostics((_scored_run(1, 0.4),))
    delta = posterior_predictive_metric_delta(baseline, candidate_diagnostics)
    candidate = ChildRegionCandidate(
        name="interaction-best",
        override_path="curation/overrides.toml",
        overridden_region_count=2,
        migration_pulse_count=2,
    )
    reference = StructuralComparisonReference("broad-pulse", -0.02, -0.1, -0.03)
    report_path = tmp_path / "reports" / "child.md"

    markdown = child_region_candidate_markdown(
        candidate,
        baseline,
        candidate_diagnostics,
        delta,
        reference=reference,
    )
    returned_path = write_child_region_candidate_markdown(
        candidate,
        baseline,
        candidate_diagnostics,
        delta,
        report_path,
        reference=reference,
    )

    assert "# Child-Region Candidate: interaction-best" in markdown
    assert "requested_group_id: Germany_Tiefbrunn_CordedWare-1" in markdown
    assert "parent_region: central_europe" in markdown
    assert "reference_name: broad-pulse" in markdown
    assert "child_minus_reference_root_mean_squared_error_delta" in markdown
    assert returned_path == report_path
    assert report_path.read_text(encoding="utf-8") == markdown


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
