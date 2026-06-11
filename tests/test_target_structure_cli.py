"""CLI tests for target-aligned structural-region commands."""

from pathlib import Path

import pytest
from pytest import CaptureFixture

from indoeuropop.data.targets import load_target_dataset
from indoeuropop.orchestration.cli import main
from indoeuropop.simulation.config import load_sweep_spec


def test_cli_structure_target_regions_writes_outputs(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The structure-target-regions command should write loadable artifacts."""
    config_path = tmp_path / "sweep.toml"
    targets_path = tmp_path / "targets.csv"
    structured_targets_path = tmp_path / "outputs" / "structured-targets.csv"
    structured_config_path = tmp_path / "outputs" / "structured-config.toml"
    _write_config(config_path)
    _write_targets(targets_path)

    exit_code = main(
        [
            "structure-target-regions",
            "--config",
            str(config_path),
            "--targets",
            str(targets_path),
            "--structure-region",
            "central_europe",
            "--structured-targets-out",
            str(structured_targets_path),
            "--structured-config-out",
            str(structured_config_path),
        ]
    )
    captured = capsys.readouterr()
    structured_targets = load_target_dataset(structured_targets_path)
    structured_spec = load_sweep_spec(structured_config_path)

    assert exit_code == 0
    assert "structured_target_count=2" in captured.out
    assert "structured_region_count=1" in captured.out
    assert "structured_region=central_europe" in captured.out
    assert structured_targets.observations[0].region == (
        "central_europe__germany_tiefbrunn_cordedware_1"
    )
    assert structured_targets.observations[1].region == "britain"
    assert structured_spec.initial_state.regions() == (
        "central_europe__germany_tiefbrunn_cordedware_1",
        "britain",
    )


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["structure-target-regions"], "requires --config"),
        (
            ["structure-target-regions", "--config", "missing.toml"],
            "requires --targets",
        ),
        (
            [
                "structure-target-regions",
                "--config",
                "missing.toml",
                "--targets",
                "missing.csv",
            ],
            "requires --structured-targets-out",
        ),
        (
            [
                "structure-target-regions",
                "--config",
                "missing.toml",
                "--targets",
                "missing.csv",
                "--structured-targets-out",
                "out.csv",
            ],
            "requires --structured-config-out",
        ),
    ],
)
def test_cli_structure_target_regions_requires_core_paths(
    arguments: list[str],
    message: str,
    capsys: CaptureFixture[str],
) -> None:
    """The structure command should reject missing required paths early."""
    with pytest.raises(SystemExit, match="2"):
        main(arguments)
    captured = capsys.readouterr()

    assert message in captured.err


def _write_config(path: Path) -> None:
    """Write a tiny sweep config for CLI structure tests."""
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
                "[counts.central_europe]",
                "local = 1000",
                "steppe = 40",
                "",
                "[counts.britain]",
                "local = 900",
                "steppe = 30",
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
    """Write a tiny target CSV for CLI structure tests."""
    path.write_text(
        "\n".join(
            (
                "status,region,source,time_bce,mean,uncertainty,citation_key,"
                "citation,note",
                "synthetic,central_europe,steppe,2900,0.08,0.04,synthetic,"
                "Synthetic target,requested_group_id=Germany_Tiefbrunn_CordedWare-1",
                "synthetic,britain,steppe,2900,0.05,0.03,synthetic,"
                "Synthetic target,requested_group_id=Britain_BellBeaker",
            )
        )
        + "\n",
        encoding="utf-8",
    )
