"""Tests for same-baseline structural head-to-head workflows."""

from __future__ import annotations

import json
from pathlib import Path

from indoeuropop.analysis.inference import ABCRejectionOptions
from indoeuropop.analysis.structural_head_to_head import StructuredPulseCandidate
from indoeuropop.data.targets import TargetDataset, TargetObservation
from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.orchestration.child_region_overrides import ChildRegionOverrideSet
from indoeuropop.orchestration.structural_head_to_head import (
    run_structured_head_to_head_workflow,
)
from indoeuropop.orchestration.structural_head_to_head_outputs import (
    StructuredHeadToHeadOutputPaths,
    structured_head_to_head_artifacts,
    structured_head_to_head_manifest,
)
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec
from indoeuropop.simulation.events import MigrationPulse


def test_structured_head_to_head_workflow_writes_artifacts(
    tmp_path: Path,
) -> None:
    """Head-to-head workflows should write all requested comparison artifacts."""
    config_path = tmp_path / "structured.toml"
    targets_path = tmp_path / "targets.csv"
    overrides_path = tmp_path / "overrides.toml"
    output_dir = tmp_path / "head-to-head"
    config_path.write_text("[sweep]\nsample_count = 2\n", encoding="utf-8")
    targets_path.write_text("targets\n", encoding="utf-8")
    overrides_path.write_text("[counts.central_europe__a]\n", encoding="utf-8")

    result = run_structured_head_to_head_workflow(
        _spec(),
        _targets(),
        _overrides(),
        _structured_pulse_candidate(),
        child_candidate_name="child-best",
        options=ABCRejectionOptions(acceptance_count=1),
        paths=StructuredHeadToHeadOutputPaths(
            config=config_path,
            targets=targets_path,
            child_region_overrides=overrides_path,
            structured_pulse_config_toml=output_dir / "pulse.toml",
            child_candidate_config_toml=output_dir / "child.toml",
            baseline_posterior_predictive_csv=output_dir / "baseline.csv",
            baseline_posterior_predictive_report_md=output_dir / "baseline.md",
            baseline_posterior_predictive_plot=output_dir / "baseline.png",
            structured_pulse_posterior_predictive_csv=output_dir / "pulse.csv",
            structured_pulse_posterior_predictive_report_md=(output_dir / "pulse.md"),
            structured_pulse_posterior_predictive_plot=output_dir / "pulse.png",
            child_posterior_predictive_csv=output_dir / "child.csv",
            child_posterior_predictive_report_md=output_dir / "child.md",
            child_posterior_predictive_plot=output_dir / "child.png",
            head_to_head_report_md=output_dir / "head-to-head.md",
            manifest_json=output_dir / "manifest.json",
        ),
        focus_observation_index=0,
        manifest_metadata={"scenario": "synthetic"},
    )
    manifest_payload = json.loads((output_dir / "manifest.json").read_text())

    assert result.structured_pulse_candidate.name == "structured-pulse"
    assert result.structured_pulse_region_count == 2
    assert result.child_candidate.name == "child-best"
    assert result.child_candidate.overridden_region_count == 1
    assert result.baseline.inference.accepted_count == 1
    assert result.structured_pulse_result.inference.accepted_count == 1
    assert result.child_result.inference.accepted_count == 1
    assert result.structured_pulse_config_toml_path == output_dir / "pulse.toml"
    assert result.child_candidate_config_toml_path == output_dir / "child.toml"
    assert result.head_to_head_report_md_path == output_dir / "head-to-head.md"
    assert result.manifest is not None
    assert result.manifest_json_path == output_dir / "manifest.json"
    assert "central_europe__b" in (output_dir / "pulse.toml").read_text(
        encoding="utf-8"
    )
    assert "central_europe__a" in (output_dir / "child.toml").read_text(
        encoding="utf-8"
    )
    assert "prediction_mean" in (output_dir / "baseline.csv").read_text(
        encoding="utf-8"
    )
    assert "# Structured Candidate Head-To-Head" in (
        output_dir / "head-to-head.md"
    ).read_text(encoding="utf-8")
    assert (output_dir / "baseline.png").exists()
    assert (output_dir / "pulse.png").exists()
    assert (output_dir / "child.png").exists()
    assert manifest_payload["metadata"]["scenario"] == "synthetic"
    assert manifest_payload["metadata"]["structured_pulse_region_count"] == "2"
    assert manifest_payload["metadata"]["child_candidate_name"] == "child-best"
    assert (
        "child_minus_structured_pulse_root_mean_squared_error_delta"
        in manifest_payload["metadata"]
    )
    assert {artifact["name"] for artifact in manifest_payload["artifacts"]} == {
        "config",
        "targets",
        "child_region_overrides",
        "structured_pulse_config_toml",
        "child_candidate_config_toml",
        "baseline_posterior_predictive_csv",
        "baseline_posterior_predictive_report_md",
        "baseline_posterior_predictive_plot",
        "structured_pulse_posterior_predictive_csv",
        "structured_pulse_posterior_predictive_report_md",
        "structured_pulse_posterior_predictive_plot",
        "child_posterior_predictive_csv",
        "child_posterior_predictive_report_md",
        "child_posterior_predictive_plot",
        "head_to_head_report_md",
    }


def test_structured_head_to_head_workflow_supports_in_memory_execution() -> None:
    """Same-baseline comparisons should not require output paths."""
    result = run_structured_head_to_head_workflow(
        _spec(sample_count=2),
        _targets(),
        _overrides(),
        _structured_pulse_candidate(),
        options=ABCRejectionOptions(acceptance_count=1),
    )

    assert result.artifacts == ()
    assert result.manifest is None
    assert result.structured_pulse_config_toml_path is None
    assert result.child_candidate_config_toml_path is None
    assert result.baseline.posterior_predictive is not None
    assert result.structured_pulse_result.posterior_predictive is not None
    assert result.child_result.posterior_predictive is not None
    assert isinstance(result.child_minus_structured_pulse_rmse_delta, float)


def test_structured_head_to_head_artifacts_can_be_empty() -> None:
    """Artifact collection should support in-memory comparison checks."""
    assert structured_head_to_head_artifacts(StructuredHeadToHeadOutputPaths()) == ()


def test_structured_head_to_head_manifest_records_candidate_metadata() -> None:
    """Programmatic manifests should expose both candidate delta summaries."""
    result = run_structured_head_to_head_workflow(
        _spec(sample_count=2),
        _targets(),
        _overrides(),
        _structured_pulse_candidate(),
        options=ABCRejectionOptions(acceptance_count=1),
    )

    manifest = structured_head_to_head_manifest(
        _structured_pulse_candidate(),
        2,
        result.child_candidate,
        result.structured_pulse_delta,
        result.child_delta,
        runs=tuple(scored.run for scored in result.baseline.inference.ranked_runs),
        metadata={"note": "manual"},
    )

    assert manifest.name == "structured-candidate-head-to-head"
    assert manifest.metadata["structured_pulse_candidate_name"] == "structured-pulse"
    assert manifest.metadata["structured_pulse_region_prefix"] == "central_europe__"
    assert manifest.metadata["child_candidate_name"] == "child-region-candidate"
    assert manifest.metadata["note"] == "manual"


def _spec(sample_count: int = 3) -> SweepSpec:
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
        sample_count=sample_count,
        seed=37,
        source="steppe",
        region="central_europe__a",
    )


def _targets() -> TargetDataset:
    """Return synthetic targets compatible with the workflow test spec."""
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
                note="requested_group_id=Germany_A; parent_region=central_europe",
            ),
            TargetObservation(
                status="synthetic",
                region="central_europe__b",
                source="steppe",
                time_bce=2950,
                mean=0.1,
                uncertainty=0.1,
                citation_key="synthetic",
                citation="Synthetic child-region target",
                note="requested_group_id=Germany_B; parent_region=central_europe",
            ),
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
