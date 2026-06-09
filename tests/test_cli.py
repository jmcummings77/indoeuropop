"""Tests for the command-line interface."""

from pathlib import Path

from pytest import CaptureFixture

from indoeuropop.cli import main


def test_cli_demo_prints_summary(capsys: CaptureFixture[str]) -> None:
    """The default demo command should print a final ancestry summary."""
    exit_code = main(["demo"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "final_steppe_ancestry=" in captured.out


def test_cli_demo_can_write_plot_and_use_config(tmp_path: Path) -> None:
    """The CLI should load config files and write optional plots."""
    config_path = tmp_path / "scenario.toml"
    plot_path = tmp_path / "plots" / "ancestry.png"
    config_path.write_text(
        """
        [simulation]
        start_bce = 3000
        end_bce = 2950
        step_years = 25

        [parameters]
        migration_rate = 0.001

        [counts.britain]
        local = 100
        steppe = 5
        """,
        encoding="utf-8",
    )

    exit_code = main(
        [
            "demo",
            "--config",
            str(config_path),
            "--plot",
            str(plot_path),
            "--region",
            "britain",
            "--stochastic",
            "--seed",
            "11",
        ]
    )

    assert exit_code == 0
    assert plot_path.exists()
