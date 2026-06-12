"""Tests for child-region structural candidate workflows."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from indoeuropop.analysis.child_region_candidates import StructuralComparisonReference
from indoeuropop.analysis.inference import ABCRejectionOptions
from indoeuropop.data.targets import TargetDataset, TargetObservation
from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.orchestration.child_region_candidates import (
    ChildRegionCandidateOutputPaths,
    child_region_candidate_artifacts,
    child_region_candidate_manifest,
    load_structural_comparison_reference,
    run_child_region_candidate_workflow,
)
from indoeuropop.orchestration.child_region_overrides import ChildRegionOverrideSet
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec
from indoeuropop.simulation.events import MigrationPulse


def test_child_region_candidate_workflow_writes_artifacts(
    tmp_path: Path,
) -> None:
    """Child-region candidate workflows should write reports and a manifest."""
    config_path = tmp_path / "structured.toml"
    targets_path = tmp_path / "targets.csv"
    overrides_path = tmp_path / "overrides.toml"
    reference_path = tmp_path / "reference.json"
    output_dir = tmp_path / "outputs"
    config_path.write_text("[sweep]\nsample_count = 2\n", encoding="utf-8")
    targets_path.write_text("targets\n", encoding="utf-8")
    overrides_path.write_text("[counts.central_europe__tiefbrunn]\n", encoding="utf-8")
    reference_path.write_text(
        json.dumps(
            {
                "name": "reference-run",
                "metadata": {
                    "candidate_name": "broad-pulse",
                    "root_mean_squared_error_delta": "-0.01",
                    "coverage_rate_delta": "-0.2",
                    "focus_residual_delta": "-0.03",
                },
            }
        ),
        encoding="utf-8",
    )
    reference = load_structural_comparison_reference(reference_path)

    result = run_child_region_candidate_workflow(
        _spec(),
        _targets(),
        _overrides(),
        candidate_name="interaction-best",
        options=ABCRejectionOptions(acceptance_count=1),
        paths=ChildRegionCandidateOutputPaths(
            config=config_path,
            targets=targets_path,
            child_region_overrides=overrides_path,
            candidate_config_toml=output_dir / "candidate.toml",
            baseline_posterior_predictive_csv=output_dir / "baseline.csv",
            baseline_posterior_predictive_report_md=output_dir / "baseline.md",
            baseline_posterior_predictive_plot=output_dir / "baseline.png",
            candidate_posterior_predictive_csv=output_dir / "candidate.csv",
            candidate_posterior_predictive_report_md=output_dir / "candidate.md",
            candidate_posterior_predictive_plot=output_dir / "candidate.png",
            reference_manifest_json=reference_path,
            comparison_report_md=output_dir / "comparison.md",
            manifest_json=output_dir / "manifest.json",
        ),
        manifest_metadata={"scenario": "synthetic"},
        reference=reference,
    )
    manifest_payload = json.loads((output_dir / "manifest.json").read_text())

    assert result.candidate.name == "interaction-best"
    assert result.candidate.overridden_region_count == 1
    assert result.candidate.migration_pulse_count == 1
    assert result.reference == reference
    assert result.baseline.inference.accepted_count == 1
    assert result.candidate_result.inference.accepted_count == 1
    assert result.candidate_config_toml_path == output_dir / "candidate.toml"
    assert result.comparison_report_md_path == output_dir / "comparison.md"
    assert "central_europe__tiefbrunn" in (output_dir / "candidate.toml").read_text(
        encoding="utf-8"
    )
    assert "prediction_mean" in (output_dir / "baseline.csv").read_text(
        encoding="utf-8"
    )
    assert "# Posterior Predictive Diagnostics" in (
        output_dir / "candidate.md"
    ).read_text(encoding="utf-8")
    assert "# Child-Region Candidate" in (output_dir / "comparison.md").read_text(
        encoding="utf-8"
    )
    assert (output_dir / "baseline.png").exists()
    assert (output_dir / "candidate.png").exists()
    assert result.manifest is not None
    assert manifest_payload["metadata"]["candidate_name"] == "interaction-best"
    assert manifest_payload["metadata"]["reference_candidate_name"] == "broad-pulse"
    assert manifest_payload["metadata"]["scenario"] == "synthetic"
    assert {artifact["name"] for artifact in manifest_payload["artifacts"]} == {
        "config",
        "targets",
        "child_region_overrides",
        "candidate_config_toml",
        "baseline_posterior_predictive_csv",
        "baseline_posterior_predictive_report_md",
        "baseline_posterior_predictive_plot",
        "candidate_posterior_predictive_csv",
        "candidate_posterior_predictive_report_md",
        "candidate_posterior_predictive_plot",
        "reference_manifest_json",
        "comparison_report_md",
    }


def test_child_region_candidate_workflow_supports_in_memory_execution() -> None:
    """Child-region candidate comparison should not require output paths."""
    result = run_child_region_candidate_workflow(
        _spec(sample_count=2),
        _targets(),
        _overrides(),
        options=ABCRejectionOptions(acceptance_count=1),
    )

    assert result.artifacts == ()
    assert result.manifest is None
    assert result.candidate_config_toml_path is None
    assert result.baseline.posterior_predictive is not None
    assert result.candidate_result.posterior_predictive is not None


def test_child_region_candidate_artifacts_can_be_empty() -> None:
    """Artifact collection should support in-memory candidate checks."""
    assert child_region_candidate_artifacts(ChildRegionCandidateOutputPaths()) == ()


def test_child_region_candidate_manifest_records_reference_metadata() -> None:
    """Programmatic manifests should expose candidate and reference metadata."""
    result = run_child_region_candidate_workflow(
        _spec(sample_count=2),
        _targets(),
        _overrides(),
        options=ABCRejectionOptions(acceptance_count=1),
    )
    reference = StructuralComparisonReference("broad-pulse", -0.01, -0.2, -0.03)

    manifest = child_region_candidate_manifest(
        result.candidate,
        result.metric_delta,
        runs=tuple(scored.run for scored in result.baseline.inference.ranked_runs),
        metadata={"note": "manual"},
        reference=reference,
    )

    assert manifest.name == "child-region-candidate"
    assert manifest.metadata["candidate_name"] == "child-region-candidate"
    assert manifest.metadata["reference_candidate_name"] == "broad-pulse"
    assert manifest.metadata["note"] == "manual"


@pytest.mark.parametrize(
    "payload",
    [
        {"metadata": None},
        {"name": "bad", "metadata": {"root_mean_squared_error_delta": "nope"}},
    ],
)
def test_load_structural_reference_rejects_invalid_manifest(
    tmp_path: Path,
    payload: dict[str, object],
) -> None:
    """Reference manifests must contain parseable structural deltas."""
    path = tmp_path / "bad-reference.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="reference manifest"):
        load_structural_comparison_reference(path)


def _spec(sample_count: int = 3) -> SweepSpec:
    """Return one small structured central-Europe sweep spec."""
    return SweepSpec(
        initial_state=PopulationState(
            {"central_europe__tiefbrunn": {"local": 1000, "steppe": 5}}
        ),
        base_parameters=SimulationParameters(migration_rate=0.0),
        parameter_ranges=(ParameterRange("migration_rate", 0.0, 0.001),),
        start_bce=3100,
        end_bce=2900,
        step_years=50,
        sample_count=sample_count,
        seed=23,
        source="steppe",
        region="central_europe__tiefbrunn",
    )


def _targets() -> TargetDataset:
    """Return a synthetic target compatible with the workflow test spec."""
    return TargetDataset.from_rows(
        [
            TargetObservation(
                status="synthetic",
                region="central_europe__tiefbrunn",
                source="steppe",
                time_bce=2950,
                mean=0.2,
                uncertainty=0.1,
                citation_key="synthetic",
                citation="Synthetic child-region target",
                note="requested_group_id=Germany_Tiefbrunn_CordedWare-1",
            )
        ]
    )


def _overrides() -> ChildRegionOverrideSet:
    """Return a synthetic child-region override set."""
    return ChildRegionOverrideSet(
        counts={"central_europe__tiefbrunn": {"local": 760, "steppe": 38}},
        migration_pulses=(
            MigrationPulse(
                region="central_europe__tiefbrunn",
                start_bce=3050,
                end_bce=2925,
                annual_rate=0.0002,
            ),
        ),
    )
