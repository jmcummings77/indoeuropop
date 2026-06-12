"""Tests for structural SMC comparison report serializers."""

from __future__ import annotations

from pathlib import Path

from indoeuropop.analysis.abc_smc import ABCSMCOptions
from indoeuropop.analysis.structural_candidates import PosteriorPredictiveMetricDelta
from indoeuropop.analysis.structural_head_to_head import StructuredPulseCandidate
from indoeuropop.data.targets import TargetDataset, TargetObservation
from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.orchestration.child_region_overrides import ChildRegionOverrideSet
from indoeuropop.orchestration.structural_smc import (
    run_structural_smc_head_to_head_workflow,
)
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec
from indoeuropop.reporting.structural_smc import (
    structural_smc_markdown,
    write_structural_smc_markdown,
)
from indoeuropop.simulation.events import MigrationPulse


def test_structural_smc_markdown_includes_calibration_and_holdout(
    tmp_path: Path,
) -> None:
    """Structural SMC reports should summarize calibration and holdout deltas."""
    result = run_structural_smc_head_to_head_workflow(
        _spec(),
        _targets(),
        _overrides(),
        _structured_pulse_candidate(),
        options=ABCSMCOptions(generation_count=1, acceptance_count=1),
        holdout_targets=_holdout_targets(),
    )
    report_path = tmp_path / "reports" / "structural-smc.md"

    markdown = structural_smc_markdown(
        result.structured_pulse_candidate,
        result.structured_pulse_region_count,
        result.child_candidate,
        result.baseline,
        result.structured_pulse_result,
        result.child_result,
        result.structured_pulse_delta,
        result.child_delta,
        result.structured_pulse_holdout_delta,
        result.child_holdout_delta,
    )

    assert "Structural ABC-SMC Head-To-Head" in markdown
    assert "SMC Calibration" in markdown
    assert "Calibration Posterior Predictive" in markdown
    assert "Holdout Posterior Predictive" in markdown
    assert "holdout_rmse_preferred_candidate" in markdown
    assert (
        write_structural_smc_markdown(
            result.structured_pulse_candidate,
            result.structured_pulse_region_count,
            result.child_candidate,
            result.baseline,
            result.structured_pulse_result,
            result.child_result,
            result.structured_pulse_delta,
            result.child_delta,
            result.structured_pulse_holdout_delta,
            result.child_holdout_delta,
            report_path,
        )
        == report_path
    )
    assert report_path.read_text(encoding="utf-8") == markdown


def test_structural_smc_markdown_can_report_tied_calibration_delta() -> None:
    """Structural SMC reports should render equal RMSE deltas as a tie."""
    result = run_structural_smc_head_to_head_workflow(
        _spec(),
        _targets(),
        _overrides(),
        _structured_pulse_candidate(),
        options=ABCSMCOptions(generation_count=1, acceptance_count=1),
    )
    tie_delta = PosteriorPredictiveMetricDelta(
        baseline_label="baseline",
        candidate_label="tied",
        coverage_rate_delta=0.0,
        mean_absolute_error_delta=0.0,
        root_mean_squared_error_delta=0.0,
        max_abs_z_score_delta=0.0,
        focus_observation_index=0,
        focus_residual_delta=0.0,
    )

    markdown = structural_smc_markdown(
        result.structured_pulse_candidate,
        result.structured_pulse_region_count,
        result.child_candidate,
        result.baseline,
        result.structured_pulse_result,
        result.child_result,
        tie_delta,
        tie_delta,
    )

    assert "calibration_rmse_preferred_candidate: tie" in markdown


def _spec() -> SweepSpec:
    """Return one small structured central-Europe sweep spec."""
    return SweepSpec(
        initial_state=PopulationState(
            {
                "central_europe__a": {"local": 1000, "steppe": 5},
                "central_europe__b": {"local": 900, "steppe": 10},
            }
        ),
        base_parameters=SimulationParameters(migration_rate=0.0),
        parameter_ranges=(ParameterRange("migration_rate", 0.0, 0.001),),
        start_bce=3100,
        end_bce=2900,
        step_years=50,
        sample_count=2,
        seed=37,
        source="steppe",
        region="central_europe__a",
    )


def _targets() -> TargetDataset:
    """Return synthetic targets compatible with the report test spec."""
    return TargetDataset.from_rows(
        [
            TargetObservation(
                status="synthetic",
                region="central_europe__a",
                source="steppe",
                time_bce=2950,
                mean=0.2,
                uncertainty=0.1,
                citation_key="synthetic",
                citation="Synthetic child-region target",
            )
        ]
    )


def _holdout_targets() -> TargetDataset:
    """Return synthetic holdout targets compatible with the report spec."""
    return TargetDataset.from_rows(
        [
            TargetObservation(
                status="synthetic",
                region="central_europe__a",
                source="steppe",
                time_bce=2900,
                mean=0.22,
                uncertainty=0.1,
                citation_key="synthetic-holdout",
                citation="Synthetic child-region holdout",
            )
        ]
    )


def _overrides() -> ChildRegionOverrideSet:
    """Return a synthetic child-region override set."""
    return ChildRegionOverrideSet(
        counts={"central_europe__a": {"local": 760, "steppe": 38}},
        migration_pulses=(
            MigrationPulse(
                region="central_europe__a",
                start_bce=3050,
                end_bce=2925,
                annual_rate=0.0002,
            ),
        ),
    )


def _structured_pulse_candidate() -> StructuredPulseCandidate:
    """Return a structured pulse copied across child regions."""
    return StructuredPulseCandidate(
        name="structured-pulse",
        region_prefix="central_europe__",
        start_bce=3050,
        end_bce=2925,
        annual_rate=0.0002,
    )
