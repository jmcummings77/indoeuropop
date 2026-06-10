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


def test_cli_demo_can_compare_targets(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    """The CLI should print target comparisons when a target CSV is supplied."""
    target_path = tmp_path / "targets.csv"
    target_path.write_text(
        "\n".join(
            [
                "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note",
                'synthetic,britain,steppe,2750,0.1,0.05,key,"Synthetic",Example',
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(["demo", "--targets", str(target_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "target_comparison=britain,steppe,2750.0" in captured.out


def test_cli_demo_can_write_provenance_csv(tmp_path: Path) -> None:
    """The CLI should write a provenance report for smoke runs."""
    target_path = tmp_path / "targets.csv"
    report_path = tmp_path / "reports" / "provenance.csv"
    target_path.write_text(
        "\n".join(
            [
                "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note",
                'synthetic,britain,steppe,2750,0.1,0.05,key,"Synthetic",Example',
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "demo",
            "--targets",
            str(target_path),
            "--provenance-csv",
            str(report_path),
        ]
    )
    report_text = report_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert "final_ancestry" in report_text
    assert "target_mean" in report_text
    assert "chi_square" in report_text
