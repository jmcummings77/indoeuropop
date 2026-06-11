"""Tests for child-override sensitivity sweeps."""

import json
from math import inf
from pathlib import Path

import pytest

from indoeuropop.analysis.override_sensitivity import (
    OverrideSensitivityCandidate,
    OverrideSensitivityScenario,
    rank_override_sensitivity_scenarios,
    validation_metric_for,
)
from indoeuropop.analysis.override_sensitivity_candidates import (
    child_override_count_reproduction_interaction_candidates,
    child_override_sensitivity_candidates,
)
from indoeuropop.analysis.validation import TargetValidationFold
from indoeuropop.data.targets import TargetDataset, TargetObservation
from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.models.parameterization import SourceParameters
from indoeuropop.orchestration.child_region_overrides import ChildRegionOverrideSet
from indoeuropop.orchestration.override_sensitivity import (
    OverrideSensitivityOutputPaths,
    override_sensitivity_artifacts,
    override_sensitivity_experiment_manifest,
    run_child_override_sensitivity_workflow,
)
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec
from indoeuropop.reporting.override_sensitivity import (
    override_sensitivity_markdown,
    override_sensitivity_summary_rows,
    override_sensitivity_summary_to_csv,
)
from indoeuropop.simulation.events import MigrationPulse


def test_child_override_sensitivity_candidates_cover_one_factor_surface() -> None:
    """Candidate generation should vary counts, pulses, and reproduction."""
    candidates = child_override_sensitivity_candidates(
        _overrides(),
        count_factors=(0.5, 1.0, 1.5),
        pulse_rate_factors=(0.8,),
        pulse_window_shifts=(-25, 0, 25),
        reproductive_multiplier_factors=(0.9,),
    )
    by_parameter = {candidate.parameter: candidate for candidate in candidates}

    assert len(candidates) == 9
    assert candidates[0].name == "curated"
    assert by_parameter["local_count"].candidate_value in {500.0, 1500.0}
    assert by_parameter["pulse_rate"].candidate_value == pytest.approx(0.00008)
    assert by_parameter["pulse_window_shift"].candidate_value in {-25.0, 25.0}
    assert by_parameter["steppe_reproductive_multiplier"].candidate_value == (
        pytest.approx(0.99)
    )


def test_child_override_interaction_candidates_vary_count_and_reproduction() -> None:
    """Interaction candidates should vary Steppe counts and reproduction together."""
    candidates = child_override_count_reproduction_interaction_candidates(
        _overrides(),
        regions=("central_europe__child",),
        count_factors=(0.9, 1.0),
        reproductive_multiplier_factors=(0.95, 1.0),
    )

    assert len(candidates) == 4
    assert candidates[0].name == "curated"
    assert {
        (candidate.parameter, round(candidate.candidate_value, 3))
        for candidate in candidates[1:]
    } == {
        ("steppe_count_x_steppe_reproductive_multiplier", 0.855),
        ("steppe_count_x_steppe_reproductive_multiplier", 0.9),
        ("steppe_count_x_steppe_reproductive_multiplier", 0.95),
    }
    assert "steppe_count__0_9" in candidates[1].name


def test_child_override_sensitivity_workflow_writes_reports_and_manifest(
    tmp_path: Path,
) -> None:
    """The workflow should rank candidates and write requested artifacts."""
    config_path = tmp_path / "structured.toml"
    target_path = tmp_path / "targets.csv"
    override_path = tmp_path / "overrides.toml"
    output_dir = tmp_path / "outputs"
    config_path.write_text("[sweep]\nsample_count = 2\n", encoding="utf-8")
    target_path.write_text("targets\n", encoding="utf-8")
    override_path.write_text("overrides\n", encoding="utf-8")

    result = run_child_override_sensitivity_workflow(
        _spec(),
        _targets(),
        _overrides(),
        priority_values=("central_europe__child",),
        protected_values=("britain",),
        tolerance=0.1,
        count_factors=(1.0,),
        pulse_rate_factors=(1.0,),
        pulse_window_shifts=(0,),
        reproductive_multiplier_factors=(1.0,),
        paths=OverrideSensitivityOutputPaths(
            config=config_path,
            targets=target_path,
            child_region_overrides=override_path,
            sensitivity_summary_csv=output_dir / "sensitivity.csv",
            sensitivity_report_md=output_dir / "sensitivity.md",
            manifest_json=output_dir / "manifest.json",
        ),
        manifest_metadata={"scenario": "synthetic"},
    )
    manifest_payload = json.loads((output_dir / "manifest.json").read_text())

    assert len(result.baseline_folds) == 2
    assert tuple(scenario.name for scenario in result.scenarios) == ("curated",)
    assert result.best_scenario(tolerance=0.1).name == "curated"
    assert result.sensitivity_summary_csv_path == output_dir / "sensitivity.csv"
    assert "accepted" in (output_dir / "sensitivity.csv").read_text()
    assert "Child-Override Sensitivity" in (output_dir / "sensitivity.md").read_text()
    assert manifest_payload["name"] == "child-override-sensitivity"
    assert manifest_payload["metadata"]["scenario"] == "synthetic"
    assert manifest_payload["metadata"]["candidate_mode"] == "one_factor"
    assert manifest_payload["metadata"]["candidate_count"] == "1"
    assert all(artifact.checksum_sha256 for artifact in result.artifacts)


def test_child_override_interaction_workflow_runs_grid_candidates() -> None:
    """The workflow should support count-by-reproduction interaction grids."""
    result = run_child_override_sensitivity_workflow(
        _spec(sample_count=2),
        _targets(),
        _overrides(),
        priority_values=("central_europe__child",),
        protected_values=("britain",),
        candidate_mode="count_reproduction_interaction",
        interaction_regions=("central_europe__child",),
        count_factors=(1.0,),
        reproductive_multiplier_factors=(0.95, 1.0),
    )

    assert tuple(scenario.candidate.parameter for scenario in result.scenarios) == (
        "baseline",
        "steppe_count_x_steppe_reproductive_multiplier",
    )


def test_override_sensitivity_reporting_helpers_return_ranked_rows() -> None:
    """Report helpers should serialize scenarios in constrained rank order."""
    result = run_child_override_sensitivity_workflow(
        _spec(sample_count=2),
        _targets(),
        _overrides(),
        priority_values=("central_europe__child",),
        protected_values=("britain",),
        tolerance=0.1,
        count_factors=(0.9, 1.1),
        pulse_rate_factors=(1.0,),
        pulse_window_shifts=(0,),
        reproductive_multiplier_factors=(1.0,),
    )
    rows = override_sensitivity_summary_rows(
        result.scenarios,
        result.baseline_folds,
        tolerance=0.1,
    )

    assert rows[0]["rank"] == "1"
    assert rows[0]["candidate"]
    assert override_sensitivity_summary_to_csv(
        result.scenarios, result.baseline_folds, tolerance=0.1
    ).startswith("rank,candidate")
    assert "top_candidate" in override_sensitivity_markdown(
        result.scenarios,
        result.baseline_folds,
        tolerance=0.1,
    )
    assert override_sensitivity_experiment_manifest(
        result.baseline_folds,
        result.scenarios,
        tolerance=0.1,
    ).metadata["candidate_count"] == str(len(result.scenarios))
    assert override_sensitivity_artifacts(OverrideSensitivityOutputPaths()) == ()


def test_override_sensitivity_workflow_supports_in_memory_outputs() -> None:
    """In-memory sensitivity runs should skip optional files and manifests."""
    result = run_child_override_sensitivity_workflow(
        _spec(sample_count=2),
        _targets(),
        _overrides(),
        count_factors=(1.0,),
        pulse_rate_factors=(1.0,),
        pulse_window_shifts=(0,),
        reproductive_multiplier_factors=(1.0,),
    )

    assert result.artifacts == ()
    assert result.manifest is None
    assert result.sensitivity_summary_csv_path is None


def test_override_sensitivity_dataclasses_and_rankers_validate_inputs() -> None:
    """Dataclasses and ranking helpers should reject malformed inputs."""
    result = run_child_override_sensitivity_workflow(
        _spec(sample_count=2),
        _targets(),
        _overrides(),
        count_factors=(1.0,),
        pulse_rate_factors=(1.0,),
        pulse_window_shifts=(0,),
        reproductive_multiplier_factors=(1.0,),
    )
    scenario = result.scenarios[0]
    fold = scenario.folds[0]

    with pytest.raises(ValueError, match="candidate name"):
        OverrideSensitivityCandidate("", _overrides(), "region", "parameter", 0, 0)
    with pytest.raises(ValueError, match="candidate region"):
        OverrideSensitivityCandidate("name", _overrides(), "", "parameter", 0, 0)
    with pytest.raises(ValueError, match="candidate parameter"):
        OverrideSensitivityCandidate("name", _overrides(), "region", "", 0, 0)
    with pytest.raises(ValueError, match="finite"):
        OverrideSensitivityCandidate("name", _overrides(), "region", "x", inf, 0)
    with pytest.raises(ValueError, match="at least one"):
        OverrideSensitivityScenario(scenario.candidate, (), "root_mean_squared_error")
    with pytest.raises(ValueError, match="unsupported fit metric"):
        OverrideSensitivityScenario(scenario.candidate, scenario.folds, "unknown")
    with pytest.raises(ValueError, match="at least one scenario"):
        rank_override_sensitivity_scenarios((), result.baseline_folds, tolerance=0)
    with pytest.raises(ValueError, match="tolerance"):
        scenario.protected_degraded(result.baseline_folds, tolerance=-0.1)
    with pytest.raises(ValueError, match="tolerance"):
        rank_override_sensitivity_scenarios(
            result.scenarios,
            result.baseline_folds,
            tolerance=-0.1,
        )
    with pytest.raises(ValueError, match="unsupported child-override"):
        run_child_override_sensitivity_workflow(
            _spec(sample_count=2),
            _targets(),
            _overrides(),
            candidate_mode="bad",
        )
    with pytest.raises(ValueError, match="unknown holdout"):
        validation_metric_for(scenario.folds, "root_mean_squared_error", "unknown")
    with pytest.raises(ValueError, match="duplicate holdout"):
        validation_metric_for(
            (
                fold,
                TargetValidationFold(
                    fold.holdout_field,
                    fold.holdout_value,
                    fold.target_split,
                    fold.runs,
                ),
            ),
            "root_mean_squared_error",
            fold.holdout_value,
        )


def test_child_override_sensitivity_candidate_generation_validates_controls() -> None:
    """Candidate generation should reject malformed sensitivity controls."""
    with pytest.raises(ValueError, match="source"):
        child_override_sensitivity_candidates(_overrides(), source="")
    with pytest.raises(ValueError, match="factors"):
        child_override_sensitivity_candidates(_overrides(), count_factors=(-1,))
    with pytest.raises(ValueError, match="pulse window"):
        child_override_sensitivity_candidates(_overrides(), pulse_window_shifts=(inf,))
    with pytest.raises(ValueError, match="source"):
        child_override_count_reproduction_interaction_candidates(
            _overrides(), source=""
        )
    with pytest.raises(ValueError, match="interaction factors"):
        child_override_count_reproduction_interaction_candidates(
            _overrides(), count_factors=(0,)
        )
    with pytest.raises(ValueError, match="at least one region"):
        child_override_count_reproduction_interaction_candidates(
            ChildRegionOverrideSet(
                source_parameters={
                    "central_europe__child": {
                        "steppe": SourceParameters(reproductive_multiplier=1.1)
                    }
                }
            )
        )
    with pytest.raises(ValueError, match="source count"):
        child_override_count_reproduction_interaction_candidates(
            _overrides(), regions=("unknown",)
        )
    with pytest.raises(ValueError, match="multiplier"):
        child_override_count_reproduction_interaction_candidates(
            ChildRegionOverrideSet(counts={"central_europe__child": {"steppe": 20}})
        )

    count_only = child_override_sensitivity_candidates(
        ChildRegionOverrideSet(
            counts={"central_europe__child": {"local": 1000, "steppe": 20}}
        ),
        count_factors=(1.1,),
        pulse_rate_factors=(1.1,),
        pulse_window_shifts=(25,),
        reproductive_multiplier_factors=(1.1,),
    )

    assert {candidate.parameter for candidate in count_only} == {
        "baseline",
        "local_count",
        "steppe_count",
    }


def test_override_sensitivity_scenario_metric_helpers() -> None:
    """Scenario helpers should expose validation metrics and acceptance flags."""
    result = run_child_override_sensitivity_workflow(
        _spec(sample_count=2),
        _targets(),
        _overrides(),
        priority_values=("central_europe__child",),
        protected_values=("britain",),
        count_factors=(1.0,),
        pulse_rate_factors=(1.0,),
        pulse_window_shifts=(0,),
        reproductive_multiplier_factors=(1.0,),
    )
    scenario = result.scenarios[0]

    assert scenario.mean_validation_metric() >= 0
    assert scenario.worst_validation_metric() >= scenario.mean_validation_metric()
    assert scenario.validation_metric_for("britain") >= 0
    assert isinstance(scenario.accepted(result.baseline_folds, tolerance=1.0), bool)


def _spec(sample_count: int = 2) -> SweepSpec:
    """Return a tiny structured sweep spec for sensitivity tests."""
    return SweepSpec(
        initial_state=PopulationState(
            {
                "britain": {"local": 1000, "steppe": 20},
                "central_europe__child": {"local": 1000, "steppe": 20},
            }
        ),
        base_parameters=SimulationParameters(migration_rate=0.0),
        parameter_ranges=(ParameterRange("migration_rate", 0.001, 0.003),),
        start_bce=3000,
        end_bce=2900,
        step_years=50,
        sample_count=sample_count,
        seed=17,
        source="steppe",
    )


def _targets() -> TargetDataset:
    """Return synthetic targets with one priority and one protected region."""
    return TargetDataset.from_rows(
        [
            _target("britain", 0.05),
            _target("central_europe__child", 0.08),
        ]
    )


def _target(region: str, mean: float) -> TargetObservation:
    """Return one synthetic target observation."""
    return TargetObservation(
        status="synthetic",
        region=region,
        source="steppe",
        time_bce=2900,
        mean=mean,
        uncertainty=0.04,
        citation_key="synthetic",
        citation="Synthetic override sensitivity target",
    )


def _overrides() -> ChildRegionOverrideSet:
    """Return one curated child-region override set for tests."""
    return ChildRegionOverrideSet(
        counts={"central_europe__child": {"local": 1000, "steppe": 20}},
        migration_pulses=(
            MigrationPulse(
                region="central_europe__child",
                start_bce=3000,
                end_bce=2900,
                annual_rate=0.0001,
            ),
        ),
        source_parameters={
            "central_europe__child": {
                "steppe": SourceParameters(reproductive_multiplier=1.1)
            }
        },
    )
