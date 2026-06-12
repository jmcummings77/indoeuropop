"""Tests for structural SMC source-model sensitivity workflows."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
from pytest import CaptureFixture, MonkeyPatch

from indoeuropop.analysis.abc_smc import ABCSMCOptions
from indoeuropop.analysis.structural_head_to_head import StructuredPulseCandidate
from indoeuropop.data.targets import TargetDataset, TargetObservation
from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.orchestration.child_region_overrides import (
    ChildRegionOverrideSet,
)
from indoeuropop.orchestration.cli import main
from indoeuropop.orchestration.structural_smc_source_model_sensitivity import (
    _summary_path,
    _validation_folds,
    run_structural_smc_source_model_sensitivity,
    structural_smc_source_model_sensitivity_paths_from_dir,
)
from indoeuropop.orchestration.structural_smc_source_model_sensitivity_cli import (
    _parse_source_model_targets,
    _review_holdout_values,
    run_structural_smc_source_model_sensitivity_command,
)
from indoeuropop.orchestration.structural_smc_source_model_sensitivity_inputs import (
    common_target_ids,
    fragile_target_ids,
    restrict_child_region_overrides,
    source_model_tuple,
    target_ids,
)
from indoeuropop.orchestration.structural_smc_source_model_sensitivity_models import (
    StructuralSMCSourceModel,
    StructuralSMCSourceModelSensitivityResult,
)
from indoeuropop.orchestration.structural_smc_validation_models import (
    StructuralSMCValidationFoldSpec,
)
from indoeuropop.orchestration.sweep_config_export import write_sweep_spec_toml
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec
from indoeuropop.reporting.structural_smc_source_model_sensitivity import (
    structural_smc_source_model_sensitivity_markdown,
    structural_smc_source_model_sensitivity_rows,
    structural_smc_source_model_sensitivity_to_csv,
)


def test_source_model_sensitivity_aligns_and_writes_reports(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """The workflow should align targets and compare source-model surfaces."""
    monkeypatch.chdir(tmp_path)
    audit_path = tmp_path / "audit.csv"
    audit_path.write_text(_sample_audit_csv(), encoding="utf-8")

    result = run_structural_smc_source_model_sensitivity(
        _spec(),
        (
            StructuralSMCSourceModel("baseline", _targets(0.1, 0.15, "target-x")),
            StructuralSMCSourceModel("rerun", _targets(0.12, 0.18, "target-y")),
        ),
        _overrides(),
        _structured_pulse_candidate(),
        sample_audit_csv=audit_path,
        structure_regions=("central_europe",),
        include_default_folds=False,
        explicit_folds=_folds(),
        options=ABCSMCOptions(generation_count=1, sample_count=2, acceptance_count=1),
    )
    rows = structural_smc_source_model_sensitivity_rows(result)
    csv_text = structural_smc_source_model_sensitivity_to_csv(result)
    markdown = structural_smc_source_model_sensitivity_markdown(result)

    assert result.source_model_count == 2
    assert result.common_target_ids == ("target-a", "target-b", "target-c")
    assert result.excluded_fragile_target_ids == ("target-a",)
    assert result.retained_common_target_count == 2
    assert rows[0]["source_model"] == "baseline"
    assert rows[0]["prepared_target_count"] == "2"
    assert rows[0]["missing_override_region_count"] == "1"
    assert "source_model,original_target_count" in csv_text
    assert "Structural SMC Source-Model Sensitivity" in markdown
    assert result.paths.summary_csv.exists()
    assert result.paths.report_md.exists()
    assert (
        result.paths.source_models_output_dir / "baseline" / "prepared-targets.csv"
    ).exists()


def test_cli_source_model_sensitivity_writes_outputs(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should expose source-model sensitivity validation."""
    config_path, baseline_path, rerun_path, overrides_path, audit_path = (
        _write_cli_inputs(tmp_path)
    )
    output_dir = tmp_path / "source-model-sensitivity"

    exit_code = main(
        [
            "validate-structured-smc-source-model-sensitivity",
            "--config",
            str(config_path),
            "--source-model-targets",
            f"baseline={baseline_path}",
            "--source-model-targets",
            f"rerun={rerun_path}",
            "--child-region-overrides",
            str(overrides_path),
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
            "--validation-value",
            "central_europe__groupb",
            "--validation-value",
            "central_europe__groupc",
            "--source-model-structure-region",
            "central_europe",
            "--target-fragility-audit-csv",
            str(audit_path),
            "--source-model-sensitivity-output-dir",
            str(output_dir),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "source_model_sensitivity=true" in captured.out
    assert "source_model_sensitivity_model_count=2" in captured.out
    assert "source_model_sensitivity_retained_common_target_count=2" in captured.out
    assert (output_dir / "source-model-sensitivity-summary.csv").exists()
    assert (output_dir / "source-model-sensitivity.md").exists()


def test_source_model_sensitivity_rejects_bad_inputs(tmp_path: Path) -> None:
    """Helpers and CLI parser should fail clearly for invalid inputs."""
    parser = argparse.ArgumentParser()
    targets = _targets(0.1, 0.2, "target-x")
    model = StructuralSMCSourceModel("baseline", targets)
    with pytest.raises(ValueError, match="label"):
        StructuralSMCSourceModel(" ", targets)
    with pytest.raises(ValueError, match="at least two"):
        source_model_tuple((model,))
    with pytest.raises(ValueError, match="unique"):
        source_model_tuple((model, model))
    with pytest.raises(ValueError, match="share no target IDs"):
        common_target_ids(
            (
                StructuralSMCSourceModel(
                    "a",
                    TargetDataset.from_rows(
                        [_target("central_europe", "GroupA", "target-a", 0.1)]
                    ),
                ),
                StructuralSMCSourceModel(
                    "b",
                    TargetDataset.from_rows(
                        [_target("central_europe", "GroupB", "target-b", 0.2)]
                    ),
                ),
            ),
            align_common_targets=True,
        )
    assert common_target_ids((model, model), align_common_targets=False) == (
        "target-a",
        "target-b",
        "target-c",
        "target-x",
    )
    with pytest.raises(ValueError, match="target_id"):
        target_ids(
            TargetDataset.from_rows([_target("central_europe", "GroupA", "", 0.1)])
        )
    with pytest.raises(ValueError, match="unique target IDs"):
        target_ids(
            TargetDataset.from_rows(
                [
                    _target("central_europe", "GroupA", "target-a", 0.1),
                    _target("central_europe", "GroupB", "target-a", 0.2),
                ]
            )
        )
    with pytest.raises(ValueError, match="at least one run"):
        StructuralSMCSourceModelSensitivityResult(
            runs=(),
            common_target_ids=(),
            excluded_fragile_target_ids=(),
            paths=structural_smc_source_model_sensitivity_paths_from_dir(
                tmp_path / "empty"
            ),
        )
    assert (
        run_structural_smc_source_model_sensitivity_command(
            argparse.Namespace(command="demo"), parser
        )
        is None
    )
    assert (
        fragile_target_ids(
            None,
            excluded_flags=(),
            exclude_repeated_estimates=True,
            repeated_estimate_tolerance=0.0,
        )
        == frozenset()
    )
    with pytest.raises(ValueError, match="missing child override regions"):
        restrict_child_region_overrides(
            _overrides(),
            ("central_europe__groupb",),
            require_all=True,
        )
    with pytest.raises(ValueError, match="summary CSV"):
        _summary_path(None)
    with pytest.raises(ValueError, match="at least one fold"):
        _validation_folds(
            targets,
            include_default_folds=False,
            include_chronology=True,
            region_prefix="central_europe__",
            protected_values=(),
            priority_values=(),
            explicit_folds=(),
        )
    assert _validation_folds(
        targets,
        include_default_folds=True,
        include_chronology=False,
        region_prefix="central_europe",
        protected_values=(),
        priority_values=(),
        explicit_folds=(),
    )
    review_path = tmp_path / "review.toml"
    review_path.write_text(
        '[review]\nprotected_holdouts = "britain"\n', encoding="utf-8"
    )
    assert _review_holdout_values(review_path, "protected_holdouts") == ("britain",)
    all_fragile_audit = tmp_path / "all-fragile.csv"
    all_fragile_audit.write_text(_all_fragile_audit_csv(), encoding="utf-8")
    with pytest.raises(ValueError, match="retained no common target IDs"):
        run_structural_smc_source_model_sensitivity(
            _spec(),
            (
                StructuralSMCSourceModel("baseline", targets),
                StructuralSMCSourceModel("rerun", targets),
            ),
            _overrides(),
            _structured_pulse_candidate(),
            sample_audit_csv=all_fragile_audit,
            include_default_folds=False,
            explicit_folds=_folds(),
            options=ABCSMCOptions(
                generation_count=1,
                sample_count=2,
                acceptance_count=1,
            ),
        )
    with pytest.raises(ValueError, match="no usable validation folds"):
        run_structural_smc_source_model_sensitivity(
            _spec(),
            (
                StructuralSMCSourceModel("baseline", targets),
                StructuralSMCSourceModel("rerun", targets),
            ),
            _overrides(),
            _structured_pulse_candidate(),
            structure_regions=("central_europe",),
            include_default_folds=False,
            explicit_folds=(
                StructuralSMCValidationFoldSpec(
                    name="missing",
                    categories=("explicit",),
                    holdout_value="missing_region",
                ),
            ),
            options=ABCSMCOptions(
                generation_count=1,
                sample_count=2,
                acceptance_count=1,
            ),
        )
    with pytest.raises(SystemExit, match="2"):
        _parse_source_model_targets(None, parser)
    with pytest.raises(SystemExit, match="2"):
        _parse_source_model_targets(["baseline"], parser)
    with pytest.raises(SystemExit, match="2"):
        _parse_source_model_targets(["baseline", "rerun=missing.csv"], parser)
    with pytest.raises(SystemExit, match="2"):
        _parse_source_model_targets(
            ["baseline=missing.csv", "baseline=other.csv"], parser
        )
    with pytest.raises(SystemExit, match="2"):
        _parse_source_model_targets(["=missing.csv", "rerun=missing.csv"], parser)
    with pytest.raises(SystemExit, match="2"):
        main(["validate-structured-smc-source-model-sensitivity"])


def _write_cli_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    """Write tiny config, target, override, and audit files."""
    config_path = tmp_path / "structured.toml"
    baseline_path = tmp_path / "baseline-targets.csv"
    rerun_path = tmp_path / "rerun-targets.csv"
    overrides_path = tmp_path / "overrides.toml"
    audit_path = tmp_path / "audit.csv"
    write_sweep_spec_toml(_spec(), config_path)
    baseline_path.write_text(_targets_csv(0.1, 0.15, "target-x"), encoding="utf-8")
    rerun_path.write_text(_targets_csv(0.12, 0.18, "target-y"), encoding="utf-8")
    overrides_path.write_text(_overrides_toml(), encoding="utf-8")
    audit_path.write_text(_sample_audit_csv(), encoding="utf-8")
    return config_path, baseline_path, rerun_path, overrides_path, audit_path


def _spec() -> SweepSpec:
    """Return a tiny central-Europe sweep spec."""
    return SweepSpec(
        initial_state=PopulationState({"central_europe": {"local": 1000, "steppe": 5}}),
        base_parameters=SimulationParameters(migration_rate=0.0),
        parameter_ranges=(ParameterRange("migration_rate", 0.0, 0.001),),
        start_bce=3100,
        end_bce=2900,
        step_years=50,
        sample_count=2,
        seed=37,
        source="steppe",
        region="central_europe",
    )


def _targets(
    group_b_mean: float,
    group_c_mean: float,
    extra_target_id: str,
) -> TargetDataset:
    """Return one source-model target dataset."""
    return TargetDataset.from_rows(
        (
            _target("central_europe", "GroupA", "target-a", 0.2),
            _target("central_europe", "GroupB", "target-b", group_b_mean),
            _target("central_europe", "GroupC", "target-c", group_c_mean),
            _target("central_europe", "ModelSpecific", extra_target_id, 0.3),
        )
    )


def _target(
    region: str,
    requested_group_id: str,
    target_id: str,
    mean: float,
) -> TargetObservation:
    """Return one synthetic target with source-model metadata."""
    note = f"requested_group_id={requested_group_id}"
    if target_id:
        note = f"target_id={target_id}; {note}"
    return TargetObservation(
        status="synthetic",
        region=region,
        source="steppe",
        time_bce=2950,
        mean=mean,
        uncertainty=0.1,
        citation_key="synthetic",
        citation="Synthetic target",
        note=note,
    )


def _folds() -> tuple[StructuralSMCValidationFoldSpec, ...]:
    """Return explicit folds for retained source-model groups."""
    return tuple(
        StructuralSMCValidationFoldSpec(
            name=region,
            categories=("explicit",),
            holdout_value=region,
        )
        for region in ("central_europe__groupb", "central_europe__groupc")
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
    """Return overrides with one known and one missing child region."""
    return ChildRegionOverrideSet(
        counts={
            "central_europe__groupb": {"local": 820, "steppe": 32},
            "central_europe__missingoverride": {"local": 500, "steppe": 50},
        },
    )


def _targets_csv(group_b_mean: float, group_c_mean: float, extra_target_id: str) -> str:
    """Return source-model targets serialized as CSV."""
    rows = [
        ("GroupA", "target-a", 0.2),
        ("GroupB", "target-b", group_b_mean),
        ("GroupC", "target-c", group_c_mean),
        ("ModelSpecific", extra_target_id, 0.3),
    ]
    body = "".join(
        "synthetic,central_europe,steppe,2950,"
        f"{mean},0.1,synthetic,Synthetic target,"
        f"target_id={target_id}; requested_group_id={group}\n"
        for group, target_id, mean in rows
    )
    return (
        "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note\n"
        + body
    )


def _sample_audit_csv() -> str:
    """Return a sample audit excluding the shared GroupA target."""
    return (
        "target_id,requested_group_id,estimate,sample_flags,has_metadata,"
        "has_estimate,sample_metadata_note\n"
        "target-a,GroupA,0.2,high_se,true,true,\n"
        "target-b,GroupB,0.1,,true,true,\n"
        "target-c,GroupC,0.15,,true,true,\n"
    )


def _all_fragile_audit_csv() -> str:
    """Return a sample audit excluding all shared target IDs."""
    return (
        "target_id,requested_group_id,estimate,sample_flags,has_metadata,"
        "has_estimate,sample_metadata_note\n"
        "target-a,GroupA,0.2,high_se,true,true,\n"
        "target-b,GroupB,0.1,high_se,true,true,\n"
        "target-c,GroupC,0.15,high_se,true,true,\n"
        "target-x,ModelSpecific,0.3,high_se,true,true,\n"
    )


def _overrides_toml() -> str:
    """Return a tiny child-region override TOML file."""
    return (
        "[counts.central_europe__groupb]\n"
        "local = 820\n"
        "steppe = 32\n\n"
        "[counts.central_europe__missingoverride]\n"
        "local = 500\n"
        "steppe = 50\n"
    )
