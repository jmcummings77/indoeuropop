"""Tests for SMC-based structural comparison workflows."""

from __future__ import annotations

import json
from pathlib import Path

from indoeuropop.analysis.abc_smc import ABCSMCOptions
from indoeuropop.analysis.structural_head_to_head import StructuredPulseCandidate
from indoeuropop.data.targets import TargetDataset, TargetObservation
from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.orchestration.child_region_overrides import ChildRegionOverrideSet
from indoeuropop.orchestration.structural_smc import (
    run_structural_smc_head_to_head_workflow,
)
from indoeuropop.orchestration.structural_smc_outputs import (
    StructuralSMCOutputPaths,
    structural_smc_artifacts,
    structural_smc_manifest,
    structural_smc_output_paths_from_dir,
    structural_smc_scored_runs,
)
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec
from indoeuropop.simulation.events import MigrationPulse


def test_structural_smc_workflow_writes_artifacts_and_holdouts(
    tmp_path: Path,
) -> None:
    """Structural SMC workflow should compare all candidates with holdouts."""
    config_path = tmp_path / "structured.toml"
    targets_path = tmp_path / "targets.csv"
    holdout_path = tmp_path / "holdout.csv"
    overrides_path = tmp_path / "overrides.toml"
    output_dir = tmp_path / "smc"
    config_path.write_text("[sweep]\nsample_count = 3\n", encoding="utf-8")
    targets_path.write_text("targets\n", encoding="utf-8")
    holdout_path.write_text("holdout\n", encoding="utf-8")
    overrides_path.write_text("[counts.central_europe__a]\n", encoding="utf-8")

    paths = structural_smc_output_paths_from_dir(
        output_dir,
        config=config_path,
        targets=targets_path,
        holdout_targets=holdout_path,
        child_region_overrides=overrides_path,
    )
    result = run_structural_smc_head_to_head_workflow(
        _spec(),
        _targets(),
        _overrides(),
        _structured_pulse_candidate(),
        child_candidate_name="child-best",
        options=ABCSMCOptions(generation_count=2, acceptance_count=1),
        paths=paths,
        focus_observation_index=0,
        holdout_targets=_holdout_targets(),
        manifest_metadata={"scenario": "synthetic-structural-smc"},
    )
    assert paths.manifest_json is not None
    assert paths.head_to_head_report_md is not None
    assert paths.baseline.generations_csv is not None
    assert paths.structured_pulse.inference_report_md is not None
    assert paths.child.holdout_posterior_predictive_plot is not None
    manifest_payload = json.loads(paths.manifest_json.read_text(encoding="utf-8"))

    assert result.structured_pulse_region_count == 2
    assert result.child_candidate.name == "child-best"
    assert result.baseline.inference.total_candidate_count == 6
    assert result.structured_pulse_result.inference.final_inference.accepted_count == 1
    assert result.child_result.holdout_posterior_predictive is not None
    assert result.child_minus_structured_pulse_holdout_rmse_delta is not None
    assert result.head_to_head_report_md_path == paths.head_to_head_report_md
    assert result.manifest is not None
    assert "Structural ABC-SMC Head-To-Head" in paths.head_to_head_report_md.read_text(
        encoding="utf-8"
    )
    assert paths.baseline.generations_csv.exists()
    assert paths.structured_pulse.inference_report_md.exists()
    assert paths.child.holdout_posterior_predictive_plot.exists()
    assert manifest_payload["metadata"]["scenario"] == "synthetic-structural-smc"
    assert manifest_payload["metadata"]["structured_pulse_region_count"] == "2"
    assert "holdout_child_minus_structured_pulse_rmse_delta" in (
        manifest_payload["metadata"]
    )
    assert "baseline_generations_csv" in {
        artifact["name"] for artifact in manifest_payload["artifacts"]
    }


def test_structural_smc_workflow_supports_in_memory_execution() -> None:
    """Programmatic structural SMC comparison should not require output paths."""
    result = run_structural_smc_head_to_head_workflow(
        _spec(sample_count=2),
        _targets(),
        _overrides(),
        _structured_pulse_candidate(),
        options=ABCSMCOptions(generation_count=1, acceptance_count=1),
    )

    assert result.artifacts == ()
    assert result.manifest is None
    assert result.structured_pulse_holdout_delta is None
    assert isinstance(result.child_minus_structured_pulse_rmse_delta, float)


def test_structural_smc_manifest_records_candidate_metadata() -> None:
    """Programmatic structural SMC manifests should summarize SMC comparison."""
    result = run_structural_smc_head_to_head_workflow(
        _spec(sample_count=2),
        _targets(),
        _overrides(),
        _structured_pulse_candidate(),
        options=ABCSMCOptions(generation_count=1, acceptance_count=1),
    )
    manifest = structural_smc_manifest(
        result,
        runs=structural_smc_scored_runs(
            (result.baseline, result.structured_pulse_result, result.child_result)
        ),
        metadata={"note": "manual"},
    )

    assert structural_smc_artifacts(StructuralSMCOutputPaths()) == ()
    assert manifest.name == "structured-smc-head-to-head"
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
            ),
        ]
    )


def _holdout_targets() -> TargetDataset:
    """Return synthetic holdout targets compatible with the workflow spec."""
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
