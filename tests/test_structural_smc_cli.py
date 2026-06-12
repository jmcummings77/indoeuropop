"""CLI tests for SMC-based structural candidate comparisons."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
from pytest import CaptureFixture

from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.orchestration.cli import main
from indoeuropop.orchestration.structural_smc_cli import (
    _target_datasets,
    run_structural_smc_command,
)
from indoeuropop.orchestration.sweep_config_export import write_sweep_spec_toml
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec


def test_cli_compare_structured_candidates_smc_writes_outputs(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should run a structural SMC comparison with holdout diagnostics."""
    config_path = tmp_path / "structured.toml"
    targets_path = tmp_path / "targets.csv"
    overrides_path = tmp_path / "overrides.toml"
    output_dir = tmp_path / "smc"
    write_sweep_spec_toml(_spec(), config_path)
    targets_path.write_text(_targets_csv(), encoding="utf-8")
    overrides_path.write_text(_overrides_toml(), encoding="utf-8")

    exit_code = main(
        [
            "compare-structured-candidates-smc",
            "--config",
            str(config_path),
            "--targets",
            str(targets_path),
            "--validation-field",
            "region",
            "--validation-value",
            "central_europe__b",
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
            "--smc-comparison-output-dir",
            str(output_dir),
        ]
    )
    captured = capsys.readouterr()
    expected_report_path = output_dir / "smc-structured-head-to-head.md"

    assert exit_code == 0
    assert "structured_smc_head_to_head=true" in captured.out
    assert "structured_pulse_candidate=structured-pulse" in captured.out
    assert "structured_pulse_region_count=2" in captured.out
    assert "child_region_candidate=child-best" in captured.out
    assert "child_minus_structured_pulse_holdout_rmse_delta=" in captured.out
    assert f"head_to_head_report_md={expected_report_path}" in captured.out
    assert (output_dir / "smc-baseline-generations.csv").exists()
    assert (output_dir / "smc-structured-pulse-report.md").exists()
    assert (output_dir / "smc-child-override-holdout-posterior-predictive.png").exists()
    assert (output_dir / "smc-structured-head-to-head-manifest.json").exists()


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["compare-structured-candidates-smc"], "requires --config"),
        (
            [
                "compare-structured-candidates-smc",
                "--config",
                "examples/sweep.example.toml",
            ],
            "requires --targets",
        ),
        (
            [
                "compare-structured-candidates-smc",
                "--config",
                "examples/sweep.example.toml",
                "--targets",
                "examples/target-observations.example.csv",
            ],
            "requires --child-region-overrides",
        ),
        (
            [
                "compare-structured-candidates-smc",
                "--config",
                "examples/sweep.example.toml",
                "--targets",
                "examples/target-observations.example.csv",
                "--child-region-overrides",
                "curation/aadr-v66-central-europe-child-overrides.toml",
            ],
            "requires --structured-pulse-region-prefix",
        ),
        (
            [
                "compare-structured-candidates-smc",
                "--config",
                "examples/sweep.example.toml",
                "--targets",
                "examples/target-observations.example.csv",
                "--child-region-overrides",
                "curation/aadr-v66-central-europe-child-overrides.toml",
                "--structured-pulse-region-prefix",
                "central_europe__",
                "--structured-pulse-start-bce",
                "3000",
                "--structured-pulse-end-bce",
                "2600",
                "--structured-pulse-annual-rate",
                "0.0001",
            ],
            "requires --smc-comparison-output-dir",
        ),
    ],
)
def test_cli_compare_structured_candidates_smc_requires_inputs(
    argv: list[str],
    expected: str,
    capsys: CaptureFixture[str],
) -> None:
    """Structural SMC CLI should reject missing required inputs."""
    with pytest.raises(SystemExit, match="2"):
        main(argv)
    captured = capsys.readouterr()

    assert expected in captured.err


def test_structural_smc_handler_ignores_unrelated_commands() -> None:
    """The delegated structural SMC handler should ignore other commands."""
    args = argparse.Namespace(command="demo")
    parser = argparse.ArgumentParser()

    assert run_structural_smc_command(args, parser) is None


def test_structural_smc_target_dataset_helper_supports_explicit_holdout(
    tmp_path: Path,
) -> None:
    """Structural SMC target helper should load explicit holdout target files."""
    targets_path = tmp_path / "targets.csv"
    holdout_path = tmp_path / "holdout.csv"
    targets_path.write_text(_targets_csv(), encoding="utf-8")
    holdout_path.write_text(_holdout_csv(), encoding="utf-8")

    calibration, holdout = _target_datasets(
        argparse.Namespace(
            targets=targets_path,
            holdout_targets=holdout_path,
            validation_field="region",
            validation_value=None,
        ),
        argparse.ArgumentParser(),
    )

    assert len(calibration.observations) == 2
    assert holdout is not None
    assert len(holdout.observations) == 1


def test_structural_smc_target_dataset_helper_allows_no_holdout(
    tmp_path: Path,
) -> None:
    """Structural SMC target helper should support calibration-only targets."""
    targets_path = tmp_path / "targets.csv"
    targets_path.write_text(_targets_csv(), encoding="utf-8")

    calibration, holdout = _target_datasets(
        argparse.Namespace(
            targets=targets_path,
            holdout_targets=None,
            validation_field="region",
            validation_value=None,
        ),
        argparse.ArgumentParser(),
    )

    assert len(calibration.observations) == 2
    assert holdout is None


@pytest.mark.parametrize(
    "args,expected",
    [
        (
            argparse.Namespace(
                targets=Path("examples/target-observations.example.csv"),
                holdout_targets=Path("examples/target-observations.example.csv"),
                validation_field="region",
                validation_value=["britain"],
            ),
            "cannot be combined",
        ),
        (
            argparse.Namespace(
                targets=Path("examples/target-observations.example.csv"),
                holdout_targets=None,
                validation_field="region",
                validation_value=["britain", "central_europe"],
            ),
            "requires one holdout value",
        ),
    ],
)
def test_structural_smc_target_dataset_helper_rejects_ambiguous_holdouts(
    args: argparse.Namespace,
    expected: str,
    capsys: CaptureFixture[str],
) -> None:
    """Structural SMC target helper should reject ambiguous holdout requests."""
    with pytest.raises(SystemExit, match="2"):
        _target_datasets(args, argparse.ArgumentParser())
    captured = capsys.readouterr()

    assert expected in captured.err


def _spec() -> SweepSpec:
    """Return a tiny structured sweep spec for CLI tests."""
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
        seed=41,
        source="steppe",
        region="central_europe__a",
    )


def _targets_csv() -> str:
    """Return target rows for structural SMC CLI tests."""
    return (
        "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note\n"
        "synthetic,central_europe__a,steppe,2950,0.2,0.1,synthetic,"
        "Synthetic target,requested_group_id=Germany_A\n"
        "synthetic,central_europe__b,steppe,2950,0.1,0.1,synthetic,"
        "Synthetic target,requested_group_id=Germany_B\n"
    )


def _holdout_csv() -> str:
    """Return holdout rows for structural SMC CLI tests."""
    return (
        "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note\n"
        "synthetic,central_europe__a,steppe,2900,0.22,0.1,synthetic,"
        "Synthetic holdout,requested_group_id=Germany_A\n"
    )


def _overrides_toml() -> str:
    """Return one loadable child-region override TOML payload."""
    return """
    [counts.central_europe__a]
    local = 760
    steppe = 38

    [[migration_pulses]]
    region = "central_europe__a"
    start_bce = 3050
    end_bce = 2925
    annual_rate = 0.0002
    """
