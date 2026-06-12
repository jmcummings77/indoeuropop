"""CLI tests for same-baseline structural candidate comparisons."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
from pytest import CaptureFixture

from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.orchestration.cli import main
from indoeuropop.orchestration.structural_head_to_head_cli import (
    run_structural_head_to_head_command,
)
from indoeuropop.orchestration.sweep_config_export import write_sweep_spec_toml
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec


def test_cli_compare_structured_candidates_writes_outputs(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should compare structured candidates on the same baseline."""
    config_path = tmp_path / "structured.toml"
    targets_path = tmp_path / "targets.csv"
    overrides_path = tmp_path / "overrides.toml"
    output_dir = tmp_path / "head-to-head"
    write_sweep_spec_toml(_spec(), config_path)
    targets_path.write_text(_targets_csv(), encoding="utf-8")
    overrides_path.write_text(_overrides_toml(), encoding="utf-8")

    exit_code = main(
        [
            "compare-structured-candidates",
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
            "--structured-pulse-config-out",
            str(output_dir / "pulse.toml"),
            "--child-candidate-config-out",
            str(output_dir / "child.toml"),
            "--posterior-predictive-report-md",
            str(output_dir / "baseline.md"),
            "--structured-pulse-posterior-predictive-report-md",
            str(output_dir / "pulse.md"),
            "--child-posterior-predictive-report-md",
            str(output_dir / "child.md"),
            "--head-to-head-report-md",
            str(output_dir / "head-to-head.md"),
            "--manifest-json",
            str(output_dir / "manifest.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "structured_head_to_head=true" in captured.out
    assert "structured_pulse_candidate=structured-pulse" in captured.out
    assert "structured_pulse_region_count=2" in captured.out
    assert "child_region_candidate=child-best" in captured.out
    assert "child_minus_structured_pulse_rmse_delta=" in captured.out
    assert f"structured_pulse_config={output_dir / 'pulse.toml'}" in captured.out
    assert f"child_candidate_config={output_dir / 'child.toml'}" in captured.out
    assert f"head_to_head_report_md={output_dir / 'head-to-head.md'}" in captured.out
    assert (output_dir / "pulse.toml").exists()
    assert (output_dir / "child.toml").exists()
    assert (output_dir / "baseline.md").exists()
    assert (output_dir / "pulse.md").exists()
    assert (output_dir / "child.md").exists()
    assert (output_dir / "head-to-head.md").exists()
    assert (output_dir / "manifest.json").exists()


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["compare-structured-candidates"], "requires --config"),
        (
            [
                "compare-structured-candidates",
                "--config",
                "examples/sweep.example.toml",
            ],
            "requires --targets",
        ),
        (
            [
                "compare-structured-candidates",
                "--config",
                "examples/sweep.example.toml",
                "--targets",
                "examples/target-observations.example.csv",
            ],
            "requires --child-region-overrides",
        ),
        (
            [
                "compare-structured-candidates",
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
                "compare-structured-candidates",
                "--config",
                "examples/sweep.example.toml",
                "--targets",
                "examples/target-observations.example.csv",
                "--child-region-overrides",
                "curation/aadr-v66-central-europe-child-overrides.toml",
                "--structured-pulse-region-prefix",
                "central_europe__",
            ],
            "requires --structured-pulse-start-bce",
        ),
        (
            [
                "compare-structured-candidates",
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
            ],
            "requires --structured-pulse-annual-rate",
        ),
    ],
)
def test_cli_compare_structured_candidates_requires_inputs(
    argv: list[str],
    expected: str,
    capsys: CaptureFixture[str],
) -> None:
    """Same-baseline comparison CLI should reject missing required inputs."""
    with pytest.raises(SystemExit, match="2"):
        main(argv)
    captured = capsys.readouterr()

    assert expected in captured.err


def test_structural_head_to_head_handler_ignores_unrelated_commands() -> None:
    """The delegated head-to-head handler should ignore other commands."""
    args = argparse.Namespace(command="demo")
    parser = argparse.ArgumentParser()

    assert run_structural_head_to_head_command(args, parser) is None


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
    """Return two target rows for same-baseline CLI tests."""
    return (
        "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note\n"
        "synthetic,central_europe__a,steppe,2950,0.2,0.1,synthetic,"
        "Synthetic target,requested_group_id=Germany_A\n"
        "synthetic,central_europe__b,steppe,2950,0.1,0.1,synthetic,"
        "Synthetic target,requested_group_id=Germany_B\n"
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
