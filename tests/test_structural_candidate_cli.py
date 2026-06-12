"""CLI tests for migration-pulse structural candidate workflows."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
from pytest import CaptureFixture

from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.orchestration.cli import main
from indoeuropop.orchestration.structural_candidate_cli import (
    run_structural_candidate_command,
)
from indoeuropop.orchestration.sweep_config_export import write_sweep_spec_toml
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec


def test_cli_evaluate_migration_pulse_candidate_writes_outputs(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should evaluate and report a migration-pulse candidate."""
    targets_path = tmp_path / "targets.csv"
    output_dir = tmp_path / "candidate"
    targets_path.write_text(
        (
            "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note\n"
            "synthetic,britain,steppe,2950,0.05,0.03,synthetic,Synthetic target,note\n"
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "evaluate-migration-pulse-candidate",
            "--config",
            "examples/sweep.example.toml",
            "--targets",
            str(targets_path),
            "--fit-metric",
            "root_mean_squared_error",
            "--acceptance-count",
            "1",
            "--pulse-candidate-name",
            "britain-early-pulse",
            "--pulse-region",
            "britain",
            "--pulse-start-bce",
            "3000",
            "--pulse-end-bce",
            "2900",
            "--pulse-annual-rate",
            "0.0001",
            "--candidate-config-out",
            str(output_dir / "candidate.toml"),
            "--posterior-predictive-report-md",
            str(output_dir / "baseline.md"),
            "--candidate-posterior-predictive-report-md",
            str(output_dir / "candidate.md"),
            "--candidate-comparison-report-md",
            str(output_dir / "comparison.md"),
            "--manifest-json",
            str(output_dir / "manifest.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "migration_pulse_candidate=britain-early-pulse" in captured.out
    assert "candidate_region=britain" in captured.out
    assert "candidate_rmse_delta=" in captured.out
    assert f"candidate_config={output_dir / 'candidate.toml'}" in captured.out
    assert f"candidate_comparison_report_md={output_dir / 'comparison.md'}" in (
        captured.out
    )
    assert (output_dir / "candidate.toml").exists()
    assert (output_dir / "baseline.md").exists()
    assert (output_dir / "candidate.md").exists()
    assert (output_dir / "comparison.md").exists()
    assert (output_dir / "manifest.json").exists()


def test_cli_evaluate_child_region_candidate_writes_outputs(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should evaluate and report a child-region candidate."""
    config_path = tmp_path / "structured.toml"
    targets_path = tmp_path / "targets.csv"
    overrides_path = tmp_path / "overrides.toml"
    reference_path = tmp_path / "reference.json"
    output_dir = tmp_path / "candidate"
    write_sweep_spec_toml(_child_spec(), config_path)
    targets_path.write_text(_child_targets_csv(), encoding="utf-8")
    overrides_path.write_text(_child_overrides_toml(), encoding="utf-8")
    reference_path.write_text(
        (
            '{"name":"reference","metadata":{"candidate_name":"broad-pulse",'
            '"root_mean_squared_error_delta":"-0.01",'
            '"coverage_rate_delta":"-0.2","focus_residual_delta":"-0.03"}}'
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "evaluate-child-region-candidate",
            "--config",
            str(config_path),
            "--targets",
            str(targets_path),
            "--child-region-overrides",
            str(overrides_path),
            "--fit-metric",
            "root_mean_squared_error",
            "--acceptance-count",
            "1",
            "--child-region-candidate-name",
            "interaction-best",
            "--candidate-config-out",
            str(output_dir / "candidate.toml"),
            "--posterior-predictive-report-md",
            str(output_dir / "baseline.md"),
            "--candidate-posterior-predictive-report-md",
            str(output_dir / "candidate.md"),
            "--candidate-comparison-report-md",
            str(output_dir / "comparison.md"),
            "--reference-comparison-manifest",
            str(reference_path),
            "--manifest-json",
            str(output_dir / "manifest.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "child_region_candidate=interaction-best" in captured.out
    assert "candidate_overridden_region_count=1" in captured.out
    assert "reference_candidate=broad-pulse" in captured.out
    assert "candidate_minus_reference_rmse_delta=" in captured.out
    assert f"candidate_config={output_dir / 'candidate.toml'}" in captured.out
    assert f"candidate_comparison_report_md={output_dir / 'comparison.md'}" in (
        captured.out
    )
    assert (output_dir / "candidate.toml").exists()
    assert (output_dir / "baseline.md").exists()
    assert (output_dir / "candidate.md").exists()
    assert (output_dir / "comparison.md").exists()
    assert (output_dir / "manifest.json").exists()


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["evaluate-migration-pulse-candidate"], "requires --config"),
        (
            [
                "evaluate-migration-pulse-candidate",
                "--config",
                "examples/sweep.example.toml",
            ],
            "requires --targets",
        ),
        (
            [
                "evaluate-migration-pulse-candidate",
                "--config",
                "examples/sweep.example.toml",
                "--targets",
                "examples/target-observations.example.csv",
            ],
            "requires --pulse-region",
        ),
        (
            [
                "evaluate-migration-pulse-candidate",
                "--config",
                "examples/sweep.example.toml",
                "--targets",
                "examples/target-observations.example.csv",
                "--pulse-region",
                "britain",
                "--pulse-start-bce",
                "3000",
                "--pulse-end-bce",
                "2900",
            ],
            "requires --pulse-annual-rate",
        ),
    ],
)
def test_cli_evaluate_migration_pulse_candidate_requires_inputs(
    argv: list[str],
    expected: str,
    capsys: CaptureFixture[str],
) -> None:
    """Structural candidate CLI should reject missing required arguments."""
    with pytest.raises(SystemExit, match="2"):
        main(argv)
    captured = capsys.readouterr()

    assert expected in captured.err


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["evaluate-child-region-candidate"], "requires --config"),
        (
            [
                "evaluate-child-region-candidate",
                "--config",
                "examples/sweep.example.toml",
            ],
            "requires --targets",
        ),
        (
            [
                "evaluate-child-region-candidate",
                "--config",
                "examples/sweep.example.toml",
                "--targets",
                "examples/target-observations.example.csv",
            ],
            "requires --child-region-overrides",
        ),
    ],
)
def test_cli_evaluate_child_region_candidate_requires_inputs(
    argv: list[str],
    expected: str,
    capsys: CaptureFixture[str],
) -> None:
    """Child-region candidate CLI should reject missing required arguments."""
    with pytest.raises(SystemExit, match="2"):
        main(argv)
    captured = capsys.readouterr()

    assert expected in captured.err


def test_structural_candidate_handler_ignores_unrelated_commands() -> None:
    """The delegated structural candidate handler should ignore other commands."""
    args = argparse.Namespace(command="demo")
    parser = argparse.ArgumentParser()

    assert run_structural_candidate_command(args, parser) is None


def _child_spec() -> SweepSpec:
    """Return a tiny structured sweep spec for CLI tests."""
    return SweepSpec(
        initial_state=PopulationState(
            {"central_europe__tiefbrunn": {"local": 1000, "steppe": 5}}
        ),
        base_parameters=SimulationParameters(migration_rate=0.0),
        parameter_ranges=(ParameterRange("migration_rate", 0.0, 0.001),),
        start_bce=3100,
        end_bce=2900,
        step_years=50,
        sample_count=2,
        seed=29,
        source="steppe",
        region="central_europe__tiefbrunn",
    )


def _child_targets_csv() -> str:
    """Return one target row for child-region CLI tests."""
    return (
        "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note\n"
        "synthetic,central_europe__tiefbrunn,steppe,2950,0.2,0.1,"
        "synthetic,Synthetic target,requested_group_id=Germany_Tiefbrunn\n"
    )


def _child_overrides_toml() -> str:
    """Return one loadable child-region override TOML payload."""
    return """
    [counts.central_europe__tiefbrunn]
    local = 760
    steppe = 38

    [[migration_pulses]]
    region = "central_europe__tiefbrunn"
    start_bce = 3050
    end_bce = 2925
    annual_rate = 0.0002
    """
