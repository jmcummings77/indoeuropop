"""Tests for the command-line interface."""

import json
from pathlib import Path

import pytest
from pytest import CaptureFixture, raises

from indoeuropop.cli import main


def test_cli_demo_prints_summary(capsys: CaptureFixture[str]) -> None:
    """The default demo command should print a final ancestry summary."""
    exit_code = main(["demo"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "final_steppe_ancestry=" in captured.out


def test_cli_build_targets_writes_target_csv(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should build target observations from curated sample inputs."""
    output_path = tmp_path / "outputs" / "targets.csv"

    exit_code = main(
        [
            "build-targets",
            "--sample-metadata",
            "examples/sample-metadata.example.csv",
            "--target-curation",
            "examples/target-curation.example.csv",
            "--ancestry-estimates",
            "examples/sample-ancestry-estimates.example.csv",
            "--target-output",
            str(output_path),
        ]
    )
    captured = capsys.readouterr()
    output_text = output_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert "target_count=1" in captured.out
    assert f"target_output={output_path}" in captured.out
    assert output_text.startswith("status,region,source,time_bce")
    assert "synthetic,britain,steppe,2900,0.08,0.03" in output_text


@pytest.mark.parametrize(
    "argv",
    [
        ["build-targets"],
        [
            "build-targets",
            "--sample-metadata",
            "examples/sample-metadata.example.csv",
        ],
        [
            "build-targets",
            "--sample-metadata",
            "examples/sample-metadata.example.csv",
            "--target-curation",
            "examples/target-curation.example.csv",
            "--ancestry-estimates",
            "examples/sample-ancestry-estimates.example.csv",
        ],
    ],
)
def test_cli_build_targets_requires_pipeline_paths(argv: list[str]) -> None:
    """The target-building command should reject incomplete input paths."""
    with raises(SystemExit) as exc_info:
        main(argv)
    assert exc_info.value.code == 2


def test_cli_demo_can_write_plot_and_use_config(tmp_path: Path) -> None:
    """The CLI should load config files and write optional plots."""
    config_path = tmp_path / "scenario.toml"
    plot_path = tmp_path / "plots" / "ancestry.png"
    manifest_path = tmp_path / "manifests" / "demo.json"
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
            "--manifest-json",
            str(manifest_path),
            "--region",
            "britain",
            "--stochastic",
            "--seed",
            "11",
        ]
    )

    assert exit_code == 0
    assert plot_path.exists()
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_payload["metadata"]["simulator"] == "tau_leap"
    assert manifest_payload["metadata"]["seed"] == "11"
    assert {artifact["role"] for artifact in manifest_payload["artifacts"]} == {
        "config",
        "plot",
    }
    assert manifest_payload["fingerprints"][0]["kind"] == "simulation_result"


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
    manifest_path = tmp_path / "manifests" / "demo.json"
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
            "--manifest-json",
            str(manifest_path),
        ]
    )
    report_text = report_path.read_text(encoding="utf-8")
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "final_ancestry" in report_text
    assert "target_mean" in report_text
    assert "chi_square" in report_text
    assert {artifact["role"] for artifact in manifest_payload["artifacts"]} == {
        "provenance",
        "targets",
    }


def test_cli_demo_can_write_fingerprint_only_manifest(tmp_path: Path) -> None:
    """The CLI should write a manifest even when no file artifacts exist."""
    manifest_path = tmp_path / "manifests" / "demo.json"

    exit_code = main(["demo", "--manifest-json", str(manifest_path)])
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert manifest_payload["name"] == "cli-demo"
    assert manifest_payload["artifacts"] == []
    assert manifest_payload["metadata"]["simulator"] == "deterministic"
    assert manifest_payload["fingerprints"][0]["kind"] == "simulation_result"


def test_cli_sweep_can_write_outputs(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The sweep command should run a TOML-backed deterministic sweep."""
    sweep_csv = tmp_path / "outputs" / "sweep-runs.csv"
    sensitivity_csv = tmp_path / "outputs" / "sensitivity.csv"
    manifest_path = tmp_path / "outputs" / "sweep-manifest.json"

    exit_code = main(
        [
            "sweep",
            "--config",
            "examples/sweep.example.toml",
            "--sweep-runs-csv",
            str(sweep_csv),
            "--sensitivity-csv",
            str(sensitivity_csv),
            "--manifest-json",
            str(manifest_path),
        ]
    )
    captured = capsys.readouterr()
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "sweep_run_count=3" in captured.out
    assert "sensitivity=migration_rate" in captured.out
    assert "summary_final_ancestry" in sweep_csv.read_text(encoding="utf-8")
    assert sensitivity_csv.read_text(encoding="utf-8").startswith("parameter,outcome")
    assert manifest_payload["name"] == "cli-sweep"
    assert manifest_payload["fingerprints"][0]["kind"] == "sweep_collection"
    assert {artifact["role"] for artifact in manifest_payload["artifacts"]} == {
        "config",
        "sensitivity",
        "sweep_runs",
    }


def test_cli_sweep_can_write_target_fit_outputs(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The sweep command should rank deterministic runs against targets."""
    target_path = tmp_path / "targets.csv"
    target_fit_csv = tmp_path / "outputs" / "target-fit.csv"
    manifest_path = tmp_path / "outputs" / "sweep-manifest.json"
    target_path.write_text(
        "\n".join(
            [
                "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note",
                'synthetic,britain,steppe,2900,0.1,0.05,key,"Synthetic",Example',
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "sweep",
            "--config",
            "examples/sweep.example.toml",
            "--targets",
            str(target_path),
            "--target-fit-csv",
            str(target_fit_csv),
            "--manifest-json",
            str(manifest_path),
            "--fit-metric",
            "root_mean_squared_error",
        ]
    )
    captured = capsys.readouterr()
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "best_target_fit=" in captured.out
    assert "metric=root_mean_squared_error" in captured.out
    assert "fit_root_mean_squared_error" in target_fit_csv.read_text(encoding="utf-8")
    assert manifest_payload["metadata"]["target_fit_metric"] == (
        "root_mean_squared_error"
    )
    assert {artifact["role"] for artifact in manifest_payload["artifacts"]} == {
        "config",
        "targets",
        "target_fit",
    }


def test_cli_sweep_requires_config() -> None:
    """The sweep command should reject missing TOML configuration."""
    with raises(SystemExit) as exc_info:
        main(["sweep"])
    assert exc_info.value.code == 2


def test_cli_sweep_target_fit_requires_targets() -> None:
    """The sweep command should reject target-fit CSVs without target data."""
    with raises(SystemExit) as exc_info:
        main(
            [
                "sweep",
                "--config",
                "examples/sweep.example.toml",
                "--target-fit-csv",
                "target-fit.csv",
            ]
        )
    assert exc_info.value.code == 2
