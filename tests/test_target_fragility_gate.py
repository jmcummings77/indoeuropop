"""Tests for target-fragility structural SMC sensitivity gates."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import pytest
from pytest import CaptureFixture

from indoeuropop.analysis.abc_smc import ABCSMCOptions
from indoeuropop.analysis.structural_head_to_head import StructuredPulseCandidate
from indoeuropop.data.targets import (
    TargetDataset,
    TargetObservation,
    load_target_dataset,
)
from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.orchestration.child_region_overrides import ChildRegionOverrideSet
from indoeuropop.orchestration.cli import main
from indoeuropop.orchestration.structural_smc_validation_cli import (
    _target_fragility_flags,
)
from indoeuropop.orchestration.structural_smc_validation_models import (
    StructuralSMCValidationFoldSpec,
)
from indoeuropop.orchestration.sweep_config_export import write_sweep_spec_toml
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec
from indoeuropop.orchestration.target_fragility import (
    filter_targets_by_fragility,
    load_target_fragility_decisions,
    run_structural_smc_target_fragility_gate,
    target_fragility_gate_paths_from_dir,
    usable_structural_smc_validation_folds,
)
from indoeuropop.orchestration.target_fragility_models import (
    DEFAULT_TARGET_FRAGILITY_FLAGS,
    TargetFragilityDecision,
    repeated_estimates,
)
from indoeuropop.reporting.target_fragility import (
    target_fragility_decisions_to_csv,
    target_fragility_gate_markdown,
)


def test_target_fragility_decisions_filter_targets_and_folds(tmp_path: Path) -> None:
    """Sample audit rows should drive target filtering and usable fold selection."""
    audit_path = tmp_path / "audit.csv"
    audit_path.write_text(_sample_audit_csv(include_critical=True), encoding="utf-8")
    decisions = load_target_fragility_decisions(audit_path)
    filtered = filter_targets_by_fragility(_targets(), decisions)
    usable_folds = usable_structural_smc_validation_folds(filtered, _folds())
    by_target_id = {decision.target_id: decision for decision in decisions}

    assert repeated_estimates((0.2, 0.2))
    assert not repeated_estimates((0.2,))
    assert by_target_id["target-a"].excluded
    assert by_target_id["target-a"].reasons == (
        "sample_flag:high_se",
        "repeated_identical_estimates",
    )
    assert by_target_id["target-c"].reasons == ("sample_flag:critical",)
    assert [target.region for target in filtered.observations] == ["central_europe__b"]
    assert usable_folds == ()


def test_target_fragility_decisions_validate_edge_cases(tmp_path: Path) -> None:
    """Fragility helpers should reject malformed decisions and audit inputs."""
    empty_audit = tmp_path / "empty.csv"
    missing_column_audit = tmp_path / "missing-column.csv"
    missing_cell_audit = tmp_path / "missing-cell.csv"
    missing_flags_audit = tmp_path / "missing-flags.csv"
    empty_audit.write_text("", encoding="utf-8")
    missing_column_audit.write_text(
        "target_id,requested_group_id,estimate\n", encoding="utf-8"
    )
    missing_cell_audit.write_text(
        "target_id,requested_group_id,estimate,sample_flags\n" ",GroupA,0.1,high_se\n",
        encoding="utf-8",
    )
    missing_flags_audit.write_text(
        "target_id,requested_group_id,estimate,sample_flags,has_metadata,"
        "has_estimate,sample_metadata_note\n"
        "target-d,GroupD,, ,false,false,\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="header"):
        load_target_fragility_decisions(empty_audit)
    with pytest.raises(ValueError, match="missing columns"):
        load_target_fragility_decisions(missing_column_audit)
    with pytest.raises(ValueError, match="missing target_id"):
        load_target_fragility_decisions(missing_cell_audit)
    with pytest.raises(ValueError, match="requested_group_id"):
        TargetFragilityDecision("target-a", "", 1, 1, 1)
    with pytest.raises(ValueError, match="sample_count"):
        TargetFragilityDecision("target-a", "GroupA", -1, 0, 0)
    with pytest.raises(ValueError, match="available_estimate_count"):
        TargetFragilityDecision("target-a", "GroupA", 1, 2, 1)
    with pytest.raises(ValueError, match="unique_estimate_count"):
        TargetFragilityDecision("target-a", "GroupA", 1, 1, 2)
    with pytest.raises(ValueError, match="tolerance"):
        repeated_estimates((0.1, 0.1), tolerance=-1.0)

    decision = load_target_fragility_decisions(missing_flags_audit)[0]

    assert decision.reasons == (
        "sample_flag:missing_metadata",
        "sample_flag:missing_estimate",
    )
    assert (
        _target_fragility_flags(argparse.Namespace(target_fragility_flags=None))
        == DEFAULT_TARGET_FRAGILITY_FLAGS
    )


def test_target_fragility_time_window_folds_are_skipped_safely() -> None:
    """Usable-fold checks should handle time-window folds without split errors."""
    fold = StructuralSMCValidationFoldSpec(
        name="early",
        categories=("time",),
        holdout_field="time_bce",
        start_bce=3000,
        end_bce=2900,
    )
    unusable_fold = StructuralSMCValidationFoldSpec(
        name="all-targets",
        categories=("time",),
        holdout_field="time_bce",
        start_bce=3000,
        end_bce=2300,
    )

    assert usable_structural_smc_validation_folds(_time_targets(), (fold,)) == (fold,)
    assert (
        usable_structural_smc_validation_folds(_time_targets(), (unusable_fold,)) == ()
    )


def test_target_fragility_reporting_serializes_decisions(tmp_path: Path) -> None:
    """Decision CSV and gate Markdown should expose exclusion reasons."""
    decision = TargetFragilityDecision(
        target_id="target-a",
        requested_group_id="GroupA",
        sample_count=2,
        available_estimate_count=2,
        unique_estimate_count=1,
        sample_flags=("high_se",),
        reasons=("sample_flag:high_se", "repeated_identical_estimates"),
    )
    csv_text = target_fragility_decisions_to_csv((decision,))

    assert "target_id,requested_group_id,excluded" in csv_text
    assert "sample_flag:high_se;repeated_identical_estimates" in csv_text
    with pytest.raises(ValueError, match="target_id"):
        TargetFragilityDecision("", "GroupA", 1, 1, 1)


def test_target_fragility_gate_workflow_writes_filtered_validation(
    tmp_path: Path,
) -> None:
    """The gate should rerun validation on retained targets and skip empty folds."""
    audit_path = tmp_path / "audit.csv"
    output_dir = tmp_path / "fragility"
    audit_path.write_text(_sample_audit_csv(include_critical=False), encoding="utf-8")
    result = run_structural_smc_target_fragility_gate(
        _spec(),
        _targets(),
        _overrides(),
        _structured_pulse_candidate(),
        sample_audit_csv=audit_path,
        folds=_folds(),
        options=ABCSMCOptions(generation_count=1, sample_count=2, acceptance_count=1),
        paths=target_fragility_gate_paths_from_dir(output_dir),
    )
    markdown = target_fragility_gate_markdown(result)
    no_exclusions_markdown = target_fragility_gate_markdown(
        replace(
            result,
            decisions=(TargetFragilityDecision("target-b", "GroupB", 1, 1, 1),),
            skipped_folds=(),
        )
    )

    assert result.excluded_target_count == 1
    assert result.filtered_target_count == 2
    assert result.skipped_fold_count == 1
    assert len(result.validation_result.folds) == 2
    assert "Target-Fragility Sensitivity Gate" in markdown
    assert "No targets were excluded." in no_exclusions_markdown
    assert "No folds were skipped" in no_exclusions_markdown
    assert (output_dir / "filtered-targets.csv").exists()
    assert (output_dir / "target-fragility-decisions.csv").exists()
    assert (
        output_dir / "validation" / "structural-smc-validation-summary.csv"
    ).exists()


def test_cli_validate_structured_smc_target_fragility_writes_outputs(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should expose the target-fragility sensitivity gate."""
    config_path, targets_path, overrides_path, audit_path = _write_cli_inputs(tmp_path)
    output_dir = tmp_path / "cli-fragility"

    exit_code = main(
        [
            "validate-structured-smc-target-fragility",
            "--config",
            str(config_path),
            "--targets",
            str(targets_path),
            "--validation-field",
            "region",
            "--validation-value",
            "central_europe__a",
            "--validation-value",
            "central_europe__b",
            "--validation-value",
            "central_europe__c",
            "--child-region-overrides",
            str(overrides_path),
            "--fit-metric",
            "root_mean_squared_error",
            "--acceptance-count",
            "1",
            "--smc-generations",
            "1",
            "--smc-sample-count",
            "2",
            "--structured-pulse-candidate-name",
            "structured-pulse",
            "--structured-pulse-region-prefix",
            "central_europe__",
            "--structured-pulse-start-bce",
            "3050",
            "--structured-pulse-end-bce",
            "2925",
            "--structured-pulse-annual-rate",
            "0.0002",
            "--child-region-candidate-name",
            "child-best",
            "--smc-validation-no-default-folds",
            "--target-fragility-audit-csv",
            str(audit_path),
            "--target-fragility-output-dir",
            str(output_dir),
            "--target-fragility-flag",
            "high_se",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "target_fragility_gate=true" in captured.out
    assert "target_fragility_excluded_target_count=1" in captured.out
    assert "target_fragility_skipped_fold_count=1" in captured.out
    assert load_target_dataset(output_dir / "filtered-targets.csv").regions() == (
        "central_europe__b",
        "central_europe__c",
    )
    assert (output_dir / "target-fragility-gate.md").exists()


def test_cli_target_fragility_requires_gate_inputs(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The fragility CLI should require its audit CSV and output directory."""
    config_path, targets_path, overrides_path, _ = _write_cli_inputs(tmp_path)
    with pytest.raises(SystemExit, match="2"):
        main(
            [
                "validate-structured-smc-target-fragility",
                "--config",
                str(config_path),
                "--targets",
                str(targets_path),
                "--child-region-overrides",
                str(overrides_path),
                "--structured-pulse-region-prefix",
                "central_europe__",
                "--structured-pulse-start-bce",
                "3050",
                "--structured-pulse-end-bce",
                "2925",
                "--structured-pulse-annual-rate",
                "0.0002",
                "--smc-validation-no-default-folds",
                "--validation-value",
                "central_europe__a",
            ]
        )
    captured = capsys.readouterr()

    assert "requires --target-fragility-audit-csv" in captured.err


def test_target_fragility_gate_rejects_no_usable_folds(tmp_path: Path) -> None:
    """The workflow should fail clearly when filtering leaves no usable folds."""
    audit_path = tmp_path / "audit.csv"
    audit_path.write_text(_sample_audit_csv(include_critical=True), encoding="utf-8")

    with pytest.raises(ValueError, match="no usable validation folds"):
        run_structural_smc_target_fragility_gate(
            _spec(),
            _targets(),
            _overrides(),
            _structured_pulse_candidate(),
            sample_audit_csv=audit_path,
            folds=_folds(),
            options=ABCSMCOptions(
                generation_count=1, sample_count=2, acceptance_count=1
            ),
            paths=target_fragility_gate_paths_from_dir(tmp_path / "empty"),
        )


def _write_cli_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Write tiny config, targets, overrides, and sample audit CSV files."""
    config_path = tmp_path / "structured.toml"
    targets_path = tmp_path / "targets.csv"
    overrides_path = tmp_path / "overrides.toml"
    audit_path = tmp_path / "audit.csv"
    write_sweep_spec_toml(_spec(), config_path)
    targets_path.write_text(_targets_csv(), encoding="utf-8")
    overrides_path.write_text(_overrides_toml(), encoding="utf-8")
    audit_path.write_text(_sample_audit_csv(include_critical=False), encoding="utf-8")
    return config_path, targets_path, overrides_path, audit_path


def _spec() -> SweepSpec:
    """Return a tiny structured central-Europe sweep spec."""
    return SweepSpec(
        initial_state=PopulationState(
            {
                "central_europe__a": {"local": 1000, "steppe": 5},
                "central_europe__b": {"local": 900, "steppe": 10},
                "central_europe__c": {"local": 950, "steppe": 8},
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
    """Return three target rows with target IDs encoded in notes."""
    rows = [
        ("central_europe__a", "target-a", "GroupA", 0.2),
        ("central_europe__b", "target-b", "GroupB", 0.1),
        ("central_europe__c", "target-c", "GroupC", 0.15),
    ]
    return TargetDataset.from_rows(
        TargetObservation(
            status="synthetic",
            region=region,
            source="steppe",
            time_bce=2950,
            mean=mean,
            uncertainty=0.1,
            citation_key="synthetic",
            citation="Synthetic target",
            note=f"target_id={target_id}; requested_group_id={group_id}",
        )
        for region, target_id, group_id, mean in rows
    )


def _time_targets() -> TargetDataset:
    """Return two targets split by chronology for fold-usability tests."""
    return TargetDataset.from_rows(
        (
            TargetObservation(
                status="synthetic",
                region="central_europe__early",
                source="steppe",
                time_bce=2950,
                mean=0.2,
                uncertainty=0.1,
                citation_key="synthetic",
                citation="Synthetic early target",
                note="target_id=target-early; requested_group_id=Early",
            ),
            TargetObservation(
                status="synthetic",
                region="central_europe__late",
                source="steppe",
                time_bce=2400,
                mean=0.1,
                uncertainty=0.1,
                citation_key="synthetic",
                citation="Synthetic late target",
                note="target_id=target-late; requested_group_id=Late",
            ),
        )
    )


def _folds() -> tuple[StructuralSMCValidationFoldSpec, ...]:
    """Return one explicit fold per target region."""
    return tuple(
        StructuralSMCValidationFoldSpec(
            name=region,
            categories=("explicit",),
            holdout_value=region,
        )
        for region in ("central_europe__a", "central_europe__b", "central_europe__c")
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


def _overrides() -> ChildRegionOverrideSet:
    """Return a tiny child-region override set for validation tests."""
    return ChildRegionOverrideSet(
        counts={"central_europe__b": {"local": 820, "steppe": 32}},
    )


def _targets_csv() -> str:
    """Return a CSV serialization of the synthetic targets."""
    return (
        "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note\n"
        "synthetic,central_europe__a,steppe,2950,0.2,0.1,synthetic,"
        "Synthetic target,target_id=target-a; requested_group_id=GroupA\n"
        "synthetic,central_europe__b,steppe,2950,0.1,0.1,synthetic,"
        "Synthetic target,target_id=target-b; requested_group_id=GroupB\n"
        "synthetic,central_europe__c,steppe,2950,0.15,0.1,synthetic,"
        "Synthetic target,target_id=target-c; requested_group_id=GroupC\n"
    )


def _sample_audit_csv(*, include_critical: bool) -> str:
    """Return sample-audit rows with one repeated/high-SE target."""
    critical_row = (
        "target-c,GroupC,0.15,,true,true,assessment=CRITICAL\n"
        if include_critical
        else "target-c,GroupC,0.15,,true,true,\n"
    )
    return (
        "target_id,requested_group_id,estimate,sample_flags,has_metadata,"
        "has_estimate,sample_metadata_note\n"
        "target-a,GroupA,0.2,high_se,true,true,\n"
        "target-a,GroupA,0.2,high_se,true,true,\n"
        "target-b,GroupB,0.1,,true,true,\n"
        f"{critical_row}"
    )


def _overrides_toml() -> str:
    """Return a tiny child-region override TOML file."""
    return "[review]\n\n" "[counts.central_europe__b]\n" "local = 820\n" "steppe = 32\n"
