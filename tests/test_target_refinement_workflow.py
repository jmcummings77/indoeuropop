"""Tests for validation-guided target-parameter refinement."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from indoeuropop.analysis.refinement import (
    ParameterRefinementCandidate,
    TargetRefinementScenario,
    baseline_refinement_candidate,
    centered_refinement_candidate,
    mean_best_sampled_values,
)
from indoeuropop.analysis.validation import TargetValidationFold
from indoeuropop.data.targets import TargetDataset, TargetObservation
from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec
from indoeuropop.orchestration.target_refinement import (
    TargetRefinementOutputPaths,
    run_target_refinement_workflow,
    target_refinement_artifacts,
    target_refinement_experiment_manifest,
)
from indoeuropop.reporting.target_refinement import (
    target_refinement_markdown,
    target_refinement_ranges_rows,
    target_refinement_ranges_to_csv,
    target_refinement_summary_rows,
    target_refinement_summary_to_csv,
)


def _spec(sample_count: int = 3) -> SweepSpec:
    """Return one small two-region sweep spec for refinement tests."""
    return SweepSpec(
        initial_state=PopulationState(
            {
                "britain": {"local": 1000, "steppe": 20},
                "central_europe": {"local": 1000, "steppe": 40},
            }
        ),
        base_parameters=SimulationParameters(migration_rate=0.0),
        parameter_ranges=(
            ParameterRange("migration_rate", 0.001, 0.003),
            ParameterRange("elite_reproductive_advantage", 1.0, 1.08),
        ),
        start_bce=3000,
        end_bce=2900,
        step_years=50,
        sample_count=sample_count,
        seed=17,
        source="steppe",
        region="britain",
    )


def _target(region: str, mean: float) -> TargetObservation:
    """Return a synthetic target with target-note metadata."""
    return TargetObservation(
        status="synthetic",
        region=region,
        source="steppe",
        time_bce=2900,
        mean=mean,
        uncertainty=0.05,
        citation_key="synthetic",
        citation="Synthetic refinement target",
        note=f"requested_group_id={region}_group",
    )


def _targets() -> TargetDataset:
    """Return targets with two validation regions."""
    return TargetDataset.from_rows(
        [
            _target("britain", 0.05),
            _target("central_europe", 0.06),
            _target("central_europe", 0.07),
        ]
    )


def test_run_target_refinement_workflow_writes_outputs_and_manifest(
    tmp_path: Path,
) -> None:
    """The workflow should compare baseline, narrowed, and expanded candidates."""
    config_path = tmp_path / "sweep.toml"
    target_path = tmp_path / "targets.csv"
    output_dir = tmp_path / "outputs"
    config_path.write_text("[sweep]\nsample_count = 3\n", encoding="utf-8")
    target_path.write_text("targets\n", encoding="utf-8")

    result = run_target_refinement_workflow(
        _spec(),
        _targets(),
        priority_values=("central_europe",),
        protected_values=("britain",),
        paths=TargetRefinementOutputPaths(
            config=config_path,
            targets=target_path,
            refinement_summary_csv=output_dir / "refinement-summary.csv",
            refinement_ranges_csv=output_dir / "refinement-ranges.csv",
            refinement_report_md=output_dir / "refinement.md",
            manifest_json=output_dir / "refinement-manifest.json",
        ),
        fit_metric="root_mean_squared_error",
        manifest_metadata={"scenario": "synthetic"},
    )
    manifest_payload = json.loads(
        (output_dir / "refinement-manifest.json").read_text(encoding="utf-8")
    )

    assert tuple(scenario.name for scenario in result.scenarios) == (
        "baseline",
        "narrowed",
        "expanded",
    )
    assert result.refinement_summary_csv_path == output_dir / "refinement-summary.csv"
    assert "priority_mean_delta" in (output_dir / "refinement-summary.csv").read_text(
        encoding="utf-8"
    )
    assert "elite_reproductive_advantage" in (
        output_dir / "refinement-ranges.csv"
    ).read_text(encoding="utf-8")
    assert "Validation-Guided" in (output_dir / "refinement.md").read_text(
        encoding="utf-8"
    )
    assert manifest_payload["name"] == "target-parameter-refinement"
    assert manifest_payload["metadata"]["scenario"] == "synthetic"
    assert manifest_payload["metadata"]["candidate_count"] == "3"


def test_refinement_report_helpers_return_stable_rows() -> None:
    """Reporting helpers should serialize refinement scenarios consistently."""
    result = run_target_refinement_workflow(
        _spec(sample_count=2),
        _targets(),
        priority_values=("central_europe",),
        protected_values=("britain",),
        fit_metric="root_mean_squared_error",
    )
    summary_rows = target_refinement_summary_rows(result.scenarios)
    range_rows = target_refinement_ranges_rows(result.scenarios)

    assert summary_rows[0]["candidate"] == "baseline"
    assert summary_rows[0]["protected_values"] == "britain"
    assert range_rows[0]["candidate"] == "baseline"
    assert target_refinement_summary_to_csv(result.scenarios).startswith("candidate")
    assert target_refinement_ranges_to_csv(result.scenarios).startswith("candidate")
    assert "| candidate | mean_validation |" in target_refinement_markdown(
        result.scenarios
    )


def test_refinement_candidates_center_and_clip_ranges() -> None:
    """Candidate range helpers should narrow, expand, and clip scalar bounds."""
    spec = _spec()
    baseline = baseline_refinement_candidate(spec)
    centered = centered_refinement_candidate(
        spec,
        name="narrowed",
        kind="narrowed",
        center_values={
            "migration_rate": 0.001,
            "elite_reproductive_advantage": 1.0,
        },
        scale=0.5,
    )

    assert baseline.range_changes[0].original_width == pytest.approx(0.002)
    assert centered.spec.parameter_ranges[0].low == pytest.approx(0.0005)
    assert centered.spec.parameter_ranges[1].low == pytest.approx(1.0)
    with pytest.raises(ValueError, match="baseline kind"):
        centered_refinement_candidate(
            spec,
            name="bad",
            kind="baseline",
            center_values={},
            scale=0.5,
        )
    with pytest.raises(ValueError, match="scale"):
        centered_refinement_candidate(
            spec,
            name="bad",
            kind="narrowed",
            center_values={},
            scale=0.0,
        )


def test_refinement_scenario_metrics_and_guards() -> None:
    """Scenario helpers should expose deltas and validate selectors."""
    result = run_target_refinement_workflow(
        _spec(sample_count=2),
        _targets(),
        priority_values=("central_europe",),
        protected_values=("britain",),
    )
    baseline, narrowed = result.scenarios[:2]

    assert baseline.mean_delta_for(baseline, ()) == 0
    assert narrowed.delta_for(baseline, "britain") == pytest.approx(
        narrowed.validation_metric_for("britain")
        - baseline.validation_metric_for("britain")
    )
    assert isinstance(narrowed.priority_improved(baseline), bool)
    assert isinstance(narrowed.protected_degraded(baseline), bool)
    with pytest.raises(ValueError, match="unknown holdout value"):
        baseline.validation_metric_for("unknown")
    with pytest.raises(ValueError, match="duplicate holdout value"):
        TargetRefinementScenario(
            candidate=baseline.candidate,
            folds=(baseline.folds[0], baseline.folds[0]),
            metric="chi_square",
        ).validation_metric_for(baseline.folds[0].holdout_value)
    with pytest.raises(ValueError, match="tolerance"):
        baseline.priority_improved(baseline, tolerance=-0.1)
    with pytest.raises(ValueError, match="tolerance"):
        baseline.protected_degraded(baseline, tolerance=-0.1)
    with pytest.raises(ValueError, match="at least one"):
        TargetRefinementScenario(
            candidate=baseline.candidate,
            folds=(),
            metric="chi_square",
        )


def test_mean_best_sampled_values_validates_fold_shapes() -> None:
    """Best-run center extraction should require compatible sampled parameters."""
    result = run_target_refinement_workflow(_spec(sample_count=2), _targets())
    fold = result.scenarios[0].folds[0]
    empty_sample_run = replace(
        fold.best_run,
        run=replace(fold.best_run.run, sampled_values={}),
    )
    mismatched_sample_run = replace(
        fold.best_run,
        run=replace(fold.best_run.run, sampled_values={"other_rate": 0.1}),
    )

    assert set(mean_best_sampled_values(result.scenarios[0].folds)) == {
        "migration_rate",
        "elite_reproductive_advantage",
    }
    with pytest.raises(ValueError, match="at least one"):
        mean_best_sampled_values(())
    with pytest.raises(ValueError, match="sampled parameter"):
        mean_best_sampled_values(
            (
                TargetValidationFold(
                    "region",
                    "britain",
                    fold.target_split,
                    (empty_sample_run,),
                ),
            )
        )
    with pytest.raises(ValueError, match="share sampled parameter"):
        mean_best_sampled_values(
            (
                fold,
                TargetValidationFold(
                    "region",
                    "central_europe",
                    fold.target_split,
                    (mismatched_sample_run,),
                ),
            )
        )


def test_refinement_workflow_and_reporting_validate_inputs() -> None:
    """Workflow and report helpers should reject malformed refinement inputs."""
    with pytest.raises(ValueError, match="narrow_fraction"):
        run_target_refinement_workflow(_spec(), _targets(), narrow_fraction=0.0)
    with pytest.raises(ValueError, match="expand_factor"):
        run_target_refinement_workflow(_spec(), _targets(), expand_factor=0.9)
    with pytest.raises(ValueError, match="tolerance"):
        run_target_refinement_workflow(_spec(), _targets(), tolerance=-0.1)
    with pytest.raises(ValueError, match="at least one refinement scenario"):
        target_refinement_summary_to_csv(())
    no_baseline = run_target_refinement_workflow(_spec(sample_count=2), _targets())
    assert (
        target_refinement_summary_rows(no_baseline.scenarios)[0]["protected_max_delta"]
        == "0"
    )
    no_baseline_scenarios = tuple(
        TargetRefinementScenario(
            candidate=ParameterRefinementCandidate(
                name=scenario.name,
                kind="narrowed",
                spec=scenario.candidate.spec,
                range_changes=scenario.candidate.range_changes,
            ),
            folds=scenario.folds,
            metric=scenario.metric,
        )
        for scenario in no_baseline.scenarios
    )
    with pytest.raises(ValueError, match="exactly one baseline"):
        target_refinement_summary_to_csv(no_baseline_scenarios)
    with pytest.raises(ValueError, match="at least one refinement scenario"):
        target_refinement_experiment_manifest(())


def test_target_refinement_artifacts_can_be_empty() -> None:
    """Artifact collection should support in-memory refinement workflows."""
    assert target_refinement_artifacts(TargetRefinementOutputPaths()) == ()


def test_refinement_manifest_records_metadata() -> None:
    """Programmatic manifests should expose refinement metadata."""
    result = run_target_refinement_workflow(_spec(sample_count=2), _targets())
    manifest = target_refinement_experiment_manifest(
        result.scenarios,
        fit_metric="root_mean_squared_error",
        metadata={"note": "review"},
    )

    assert manifest.metadata["candidate_count"] == "3"
    assert manifest.metadata["note"] == "review"
