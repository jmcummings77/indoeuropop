"""CLI tests for child-override sensitivity sweeps."""

import json
from pathlib import Path

import pytest
from pytest import CaptureFixture

from indoeuropop.orchestration.cli import main


def test_cli_sweep_child_overrides_writes_ranked_outputs(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should run a bounded child-override sensitivity sweep."""
    config_path = tmp_path / "structured.toml"
    target_path = tmp_path / "targets.csv"
    override_path = tmp_path / "overrides.toml"
    output_dir = tmp_path / "outputs"
    summary_csv = output_dir / "sensitivity.csv"
    report_md = output_dir / "sensitivity.md"
    manifest_path = output_dir / "manifest.json"
    _write_config(config_path)
    _write_targets(target_path)
    _write_overrides(override_path)

    exit_code = main(
        [
            "sweep-child-overrides",
            "--config",
            str(config_path),
            "--targets",
            str(target_path),
            "--child-region-overrides",
            str(override_path),
            "--priority-validation-value",
            "central_europe__child",
            "--protected-validation-value",
            "britain",
            "--refinement-tolerance",
            "0.1",
            "--count-factor",
            "1.0",
            "--pulse-rate-factor",
            "1.0",
            "--pulse-window-shift",
            "0",
            "--reproductive-multiplier-factor",
            "1.0",
            "--override-sensitivity-csv",
            str(summary_csv),
            "--override-sensitivity-report-md",
            str(report_md),
            "--manifest-json",
            str(manifest_path),
            "--fit-metric",
            "root_mean_squared_error",
        ]
    )
    captured = capsys.readouterr()
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "override_sensitivity_candidate_count=1" in captured.out
    assert "override_sensitivity_best_candidate=curated" in captured.out
    assert "accepted" in summary_csv.read_text(encoding="utf-8")
    assert "Child-Override Sensitivity" in report_md.read_text(encoding="utf-8")
    assert manifest_payload["name"] == "cli-child-override-sensitivity"


def test_cli_sweep_child_overrides_can_print_markdown(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should print Markdown when no report path is supplied."""
    config_path = tmp_path / "structured.toml"
    target_path = tmp_path / "targets.csv"
    override_path = tmp_path / "overrides.toml"
    _write_config(config_path)
    _write_targets(target_path)
    _write_overrides(override_path)

    exit_code = main(
        [
            "sweep-child-overrides",
            "--config",
            str(config_path),
            "--targets",
            str(target_path),
            "--child-region-overrides",
            str(override_path),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "# Child-Override Sensitivity Sweep" in captured.out
    assert "override_sensitivity_best_accepted=" in captured.out


def test_cli_sweep_child_override_interactions_uses_default_grid(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The interaction command should run the default count-reproduction grid."""
    config_path = tmp_path / "structured.toml"
    target_path = tmp_path / "targets.csv"
    override_path = tmp_path / "overrides.toml"
    _write_config(config_path)
    _write_targets(target_path)
    _write_overrides(override_path)

    exit_code = main(
        [
            "sweep-child-override-interactions",
            "--config",
            str(config_path),
            "--targets",
            str(target_path),
            "--child-region-overrides",
            str(override_path),
            "--interaction-region",
            "central_europe__child",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "override_sensitivity_candidate_count=12" in captured.out
    assert "steppe_count_x_steppe_reproductive_multiplier" in captured.out


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["sweep-child-overrides"], "requires --config"),
        (
            ["sweep-child-overrides", "--config", "missing.toml"],
            "requires --targets",
        ),
        (
            [
                "sweep-child-overrides",
                "--config",
                "missing.toml",
                "--targets",
                "missing.csv",
            ],
            "requires --child-region-overrides",
        ),
    ],
)
def test_cli_sweep_child_overrides_requires_core_inputs(
    arguments: list[str],
    message: str,
    capsys: CaptureFixture[str],
) -> None:
    """The sensitivity command should reject missing required paths."""
    with pytest.raises(SystemExit, match="2"):
        main(arguments)
    captured = capsys.readouterr()

    assert message in captured.err


def _write_config(path: Path) -> None:
    """Write a tiny structured sweep config."""
    path.write_text(
        "\n".join(
            (
                "[simulation]",
                "start_bce = 3000",
                "end_bce = 2900",
                "step_years = 50",
                "",
                "[parameters]",
                "migration_rate = 0.001",
                "",
                "[counts.britain]",
                "local = 1000",
                "steppe = 20",
                "",
                "[counts.central_europe__child]",
                "local = 1000",
                "steppe = 20",
                "",
                "[sweep]",
                "sample_count = 2",
                "seed = 23",
                'source = "steppe"',
                "",
                "[[parameter_ranges]]",
                'name = "migration_rate"',
                "low = 0.001",
                "high = 0.003",
            )
        )
        + "\n",
        encoding="utf-8",
    )


def _write_targets(path: Path) -> None:
    """Write synthetic target observations for CLI sensitivity tests."""
    path.write_text(
        "\n".join(
            (
                "status,region,source,time_bce,mean,uncertainty,citation_key,"
                "citation,note",
                "synthetic,britain,steppe,2900,0.05,0.04,synthetic,"
                "Synthetic target,requested_group_id=britain_group",
                "synthetic,central_europe__child,steppe,2900,0.08,0.04,"
                "synthetic,Synthetic target,requested_group_id=central_group",
            )
        )
        + "\n",
        encoding="utf-8",
    )


def _write_overrides(path: Path) -> None:
    """Write one child-region override TOML for CLI sensitivity tests."""
    path.write_text(
        "\n".join(
            (
                "[counts.central_europe__child]",
                "local = 1000",
                "steppe = 20",
                "",
                "[[migration_pulses]]",
                'region = "central_europe__child"',
                "start_bce = 3000",
                "end_bce = 2900",
                "annual_rate = 0.0001",
                "",
                "[source_parameters.central_europe__child.steppe]",
                "reproductive_multiplier = 1.1",
            )
        )
        + "\n",
        encoding="utf-8",
    )
