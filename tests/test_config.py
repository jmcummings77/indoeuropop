"""Tests for TOML configuration loading."""

from pathlib import Path

import pytest

from indoeuropop.config import default_config, load_config


def test_default_config_is_runnable() -> None:
    """The built-in config should contain state, parameters, and a timeline."""
    config = default_config()

    assert config.initial_state.total("britain") > 0
    assert config.parameters.migration_rate >= 0
    assert config.start_bce > config.end_bce
    assert config.step_years > 0


def test_load_config_from_toml(tmp_path: Path) -> None:
    """A TOML file should load into a complete SimulationConfig."""
    config_path = tmp_path / "scenario.toml"
    config_path.write_text(
        """
        [simulation]
        start_bce = 3100
        end_bce = 3000
        step_years = 25

        [parameters]
        migration_rate = 0.003
        fertility_rate = 0.04

        [counts.britain]
        local = 100
        steppe = 5
        """,
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.start_bce == 3100
    assert config.end_bce == 3000
    assert config.step_years == 25
    assert config.parameters.migration_rate == 0.003
    assert config.initial_state.source_total("steppe", "britain") == 5


@pytest.mark.parametrize("contents", ["", "[parameters]\nmigration_rate = 0.1\n"])
def test_load_config_requires_tables(tmp_path: Path, contents: str) -> None:
    """Required config tables should be validated explicitly."""
    config_path = tmp_path / "bad.toml"
    config_path.write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError):
        load_config(config_path)
