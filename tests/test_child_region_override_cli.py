"""CLI tests for child-region override commands."""

from pathlib import Path

import pytest
from pytest import CaptureFixture

from indoeuropop.orchestration.cli import main
from indoeuropop.simulation.config import load_sweep_spec


def test_cli_apply_child_region_overrides_writes_config(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should apply a partial override TOML to a structured config."""
    config_path = tmp_path / "structured.toml"
    override_path = tmp_path / "overrides.toml"
    output_path = tmp_path / "outputs" / "overridden.toml"
    _write_config(config_path)
    _write_overrides(override_path)

    exit_code = main(
        [
            "apply-child-region-overrides",
            "--config",
            str(config_path),
            "--child-region-overrides",
            str(override_path),
            "--overridden-config-out",
            str(output_path),
        ]
    )
    captured = capsys.readouterr()
    spec = load_sweep_spec(output_path)

    assert exit_code == 0
    assert "count_override_count=1" in captured.out
    assert "migration_pulse_override_count=1" in captured.out
    assert "region_parameter_override_count=1" in captured.out
    assert "source_parameter_override_count=1" in captured.out
    assert spec.initial_state.counts["central_europe__tiefbrunn"]["steppe"] == 42
    assert spec.schedule.migration_pulses[-1].annual_rate == pytest.approx(0.00014)


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["apply-child-region-overrides"], "requires --config"),
        (
            ["apply-child-region-overrides", "--config", "missing.toml"],
            "requires --child-region-overrides",
        ),
        (
            [
                "apply-child-region-overrides",
                "--config",
                "missing.toml",
                "--child-region-overrides",
                "missing-overrides.toml",
            ],
            "requires --overridden-config-out",
        ),
    ],
)
def test_cli_apply_child_region_overrides_requires_core_paths(
    arguments: list[str],
    message: str,
    capsys: CaptureFixture[str],
) -> None:
    """The override command should reject missing required paths early."""
    with pytest.raises(SystemExit, match="2"):
        main(arguments)
    captured = capsys.readouterr()

    assert message in captured.err


def _write_config(path: Path) -> None:
    """Write a small structured sweep config for CLI override tests."""
    path.write_text(
        "\n".join(
            (
                "[simulation]",
                "start_bce = 3300",
                "end_bce = 1700",
                "step_years = 25",
                "",
                "[parameters]",
                "migration_rate = 0.00005",
                "",
                "[counts.central_europe__tiefbrunn]",
                "local = 1200",
                "steppe = 2.5",
                "",
                "[counts.britain]",
                "local = 7000",
                "steppe = 5",
                "",
                "[sweep]",
                "sample_count = 2",
                "seed = 661",
                'source = "steppe"',
                "",
                "[[migration_pulses]]",
                'region = "central_europe__tiefbrunn"',
                "start_bce = 3000",
                "end_bce = 2300",
                "annual_rate = 0.00006",
                "",
                "[[parameter_ranges]]",
                'name = "migration_rate"',
                "low = 0",
                "high = 0.00003",
            )
        )
        + "\n",
        encoding="utf-8",
    )


def _write_overrides(path: Path) -> None:
    """Write a partial child-region override TOML for CLI tests."""
    path.write_text(
        "\n".join(
            (
                "[counts.central_europe__tiefbrunn]",
                "local = 760",
                "steppe = 42",
                "",
                "[[migration_pulses]]",
                'region = "central_europe__tiefbrunn"',
                "start_bce = 2980",
                "end_bce = 2450",
                "annual_rate = 0.00014",
                "",
                "[region_parameters.central_europe__tiefbrunn]",
                "migration_rate = 0.0002",
                "",
                "[source_parameters.central_europe__tiefbrunn.steppe]",
                "reproductive_multiplier = 1.18",
            )
        )
        + "\n",
        encoding="utf-8",
    )
