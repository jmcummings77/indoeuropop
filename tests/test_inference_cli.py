"""CLI tests for ABC rejection target-parameter inference."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
from pytest import CaptureFixture

from indoeuropop.orchestration.cli import main
from indoeuropop.orchestration.inference_cli import run_inference_command


def test_cli_infer_target_parameters_writes_outputs(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    """The CLI inference command should write requested artifacts."""
    output_dir = tmp_path / "inference"
    target_path = tmp_path / "targets.csv"
    holdout_path = tmp_path / "holdout.csv"
    target_path.write_text(
        (
            "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note\n"
            "synthetic,britain,steppe,2950,0.05,0.03,synthetic,Synthetic target,note\n"
        ),
        encoding="utf-8",
    )
    holdout_path.write_text(
        (
            "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note\n"
            "synthetic,britain,steppe,2900,0.06,0.04,synthetic,Synthetic holdout,note\n"
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "infer-target-parameters",
            "--config",
            "examples/sweep.example.toml",
            "--targets",
            str(target_path),
            "--fit-metric",
            "root_mean_squared_error",
            "--acceptance-count",
            "2",
            "--posterior-samples-csv",
            str(output_dir / "accepted.csv"),
            "--posterior-summary-csv",
            str(output_dir / "summary.csv"),
            "--inference-report-md",
            str(output_dir / "report.md"),
            "--posterior-predictive-csv",
            str(output_dir / "posterior.csv"),
            "--posterior-predictive-report-md",
            str(output_dir / "posterior.md"),
            "--posterior-predictive-plot",
            str(output_dir / "posterior.png"),
            "--holdout-targets",
            str(holdout_path),
            "--holdout-posterior-predictive-csv",
            str(output_dir / "holdout.csv"),
            "--holdout-posterior-predictive-report-md",
            str(output_dir / "holdout.md"),
            "--holdout-posterior-predictive-plot",
            str(output_dir / "holdout.png"),
            "--manifest-json",
            str(output_dir / "manifest.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "inference_candidate_count=3" in captured.out
    assert "inference_accepted_count=2" in captured.out
    assert "inference_acceptance_criterion=count" in captured.out
    assert "posterior_predictive=coverage_rate=" in captured.out
    assert "holdout_posterior_predictive=coverage_rate=" in captured.out
    assert f"posterior_samples_csv={output_dir / 'accepted.csv'}" in captured.out
    assert f"posterior_predictive_csv={output_dir / 'posterior.csv'}" in captured.out
    assert (
        f"holdout_posterior_predictive_plot={output_dir / 'holdout.png'}"
        in captured.out
    )
    assert (output_dir / "accepted.csv").exists()
    assert (output_dir / "summary.csv").exists()
    assert (output_dir / "report.md").exists()
    assert (output_dir / "posterior.csv").exists()
    assert (output_dir / "posterior.md").exists()
    assert (output_dir / "posterior.png").exists()
    assert (output_dir / "holdout.csv").exists()
    assert (output_dir / "holdout.md").exists()
    assert (output_dir / "holdout.png").exists()
    assert (output_dir / "manifest.json").exists()


def test_cli_infer_target_parameters_smc_writes_outputs(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    """The CLI SMC command should write sequential calibration artifacts."""
    output_dir = tmp_path / "smc"
    target_path = tmp_path / "targets.csv"
    holdout_path = tmp_path / "holdout.csv"
    target_path.write_text(
        (
            "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note\n"
            "synthetic,britain,steppe,2950,0.05,0.03,synthetic,Synthetic target,note\n"
        ),
        encoding="utf-8",
    )
    holdout_path.write_text(
        (
            "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note\n"
            "synthetic,britain,steppe,2900,0.06,0.04,synthetic,Synthetic holdout,note\n"
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "infer-target-parameters-smc",
            "--config",
            "examples/sweep.example.toml",
            "--targets",
            str(target_path),
            "--fit-metric",
            "root_mean_squared_error",
            "--acceptance-count",
            "1",
            "--smc-generations",
            "2",
            "--smc-sample-count",
            "3",
            "--smc-seed-stride",
            "13",
            "--smc-generations-csv",
            str(output_dir / "generations.csv"),
            "--posterior-samples-csv",
            str(output_dir / "samples.csv"),
            "--posterior-summary-csv",
            str(output_dir / "summary.csv"),
            "--inference-report-md",
            str(output_dir / "report.md"),
            "--posterior-predictive-csv",
            str(output_dir / "posterior.csv"),
            "--posterior-predictive-report-md",
            str(output_dir / "posterior.md"),
            "--posterior-predictive-plot",
            str(output_dir / "posterior.png"),
            "--holdout-targets",
            str(holdout_path),
            "--holdout-posterior-predictive-csv",
            str(output_dir / "holdout.csv"),
            "--holdout-posterior-predictive-report-md",
            str(output_dir / "holdout.md"),
            "--holdout-posterior-predictive-plot",
            str(output_dir / "holdout.png"),
            "--manifest-json",
            str(output_dir / "manifest.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "smc_generation_count=2" in captured.out
    assert "smc_total_candidate_count=6" in captured.out
    assert "smc_final_accepted_count=1" in captured.out
    assert "smc_threshold_schedule=" in captured.out
    assert "posterior_predictive=coverage_rate=" in captured.out
    assert "holdout_posterior_predictive=coverage_rate=" in captured.out
    assert f"smc_generations_csv={output_dir / 'generations.csv'}" in captured.out
    assert f"posterior_samples_csv={output_dir / 'samples.csv'}" in captured.out
    assert (
        f"holdout_posterior_predictive_plot={output_dir / 'holdout.png'}"
        in captured.out
    )
    assert f"manifest_json={output_dir / 'manifest.json'}" in captured.out
    assert (output_dir / "generations.csv").exists()
    assert (output_dir / "samples.csv").exists()
    assert (output_dir / "summary.csv").exists()
    assert (output_dir / "report.md").exists()
    assert (output_dir / "posterior.csv").exists()
    assert (output_dir / "posterior.md").exists()
    assert (output_dir / "posterior.png").exists()
    assert (output_dir / "holdout.csv").exists()
    assert (output_dir / "holdout.md").exists()
    assert (output_dir / "holdout.png").exists()
    assert (output_dir / "manifest.json").exists()


@pytest.mark.parametrize(
    "argv,expected",
    [
        (["infer-target-parameters"], "requires --config"),
        (
            ["infer-target-parameters", "--config", "examples/sweep.example.toml"],
            "requires --targets",
        ),
    ],
)
def test_cli_infer_target_parameters_requires_inputs(
    argv: list[str],
    expected: str,
    capsys: CaptureFixture[str],
) -> None:
    """Inference CLI should reject missing required paths."""
    with pytest.raises(SystemExit, match="2"):
        main(argv)
    captured = capsys.readouterr()

    assert expected in captured.err


@pytest.mark.parametrize(
    "argv,expected",
    [
        (["infer-target-parameters-smc"], "requires --config"),
        (
            ["infer-target-parameters-smc", "--config", "examples/sweep.example.toml"],
            "requires --targets",
        ),
        (
            [
                "infer-target-parameters-smc",
                "--config",
                "examples/sweep.example.toml",
                "--targets",
                "examples/target-observations.example.csv",
                "--holdout-posterior-predictive-csv",
                "holdout.csv",
            ],
            "require --holdout-targets",
        ),
    ],
)
def test_cli_infer_target_parameters_smc_rejects_invalid_inputs(
    argv: list[str],
    expected: str,
    capsys: CaptureFixture[str],
) -> None:
    """SMC CLI should reject missing paths and unsupported holdout outputs."""
    with pytest.raises(SystemExit, match="2"):
        main(argv)
    captured = capsys.readouterr()

    assert expected in captured.err


def test_inference_handler_ignores_unrelated_commands() -> None:
    """The delegated inference handler should return None for unrelated commands."""
    args = argparse.Namespace(command="demo")
    parser = argparse.ArgumentParser()

    assert run_inference_command(args, parser) is None


def test_cli_infer_target_parameters_requires_holdout_for_holdout_outputs(
    capsys: CaptureFixture[str],
) -> None:
    """Holdout-only outputs should require an explicit holdout target file."""
    with pytest.raises(SystemExit, match="2"):
        main(
            [
                "infer-target-parameters",
                "--config",
                "examples/sweep.example.toml",
                "--targets",
                "examples/target-observations.example.csv",
                "--holdout-posterior-predictive-csv",
                "holdout.csv",
            ]
        )
    captured = capsys.readouterr()

    assert "require --holdout-targets" in captured.err
