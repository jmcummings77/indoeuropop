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
    assert config.schedule.migration_pulses == ()
    assert config.schedule.forcing_windows == ()


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

        [region_parameters.britain]
        migration_rate = 0.004

        [counts.britain]
        local = 100
        steppe = 5

        [[migration_pulses]]
        region = "britain"
        start_bce = 3050
        end_bce = 3025
        annual_rate = 0.002

        [[forcing_windows]]
        start_bce = 3050
        end_bce = 3025
        climate_stress_delta = 0.2
        epidemic_mortality_delta = 0.01

        [source_parameters.britain.steppe]
        fertility_rate = 0.05
        reproductive_multiplier = 1.2
        """,
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.start_bce == 3100
    assert config.end_bce == 3000
    assert config.step_years == 25
    assert config.parameters.migration_rate == 0.003
    assert config.initial_state.source_total("steppe", "britain") == 5
    assert len(config.schedule.migration_pulses) == 1
    assert len(config.schedule.forcing_windows) == 1
    assert config.schedule.migration_pulses[0].annual_rate == 0.002
    assert config.schedule.forcing_windows[0].climate_stress_delta == 0.2
    assert config.parameter_set.region_parameters["britain"].migration_rate == 0.004
    source_parameters = config.parameter_set.source_parameters["britain"]["steppe"]
    assert source_parameters.fertility_rate == 0.05
    assert source_parameters.reproductive_multiplier == 1.2


def test_example_pulsed_config_loads() -> None:
    """The checked-in pulsed example should remain loadable."""
    config = load_config("examples/pulsed-scenario.example.toml")

    assert config.schedule.migration_pulses[0].region == "britain"
    assert config.schedule.forcing_windows[0].epidemic_mortality_delta == 0.01


def test_example_parameter_override_config_loads() -> None:
    """The checked-in parameter override example should remain loadable."""
    config = load_config("examples/parameter-overrides.example.toml")

    assert config.parameter_set.region_parameters["britain"].migration_rate == 0.003
    assert (
        config.parameter_set.source_parameters["britain"]["steppe"].fertility_rate
        == 0.04
    )


@pytest.mark.parametrize("contents", ["", "[parameters]\nmigration_rate = 0.1\n"])
def test_load_config_requires_tables(tmp_path: Path, contents: str) -> None:
    """Required config tables should be validated explicitly."""
    config_path = tmp_path / "bad.toml"
    config_path.write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError):
        load_config(config_path)


def test_load_config_rejects_bad_schedule_tables(tmp_path: Path) -> None:
    """Optional event schedule sections should be arrays of tables."""
    config_path = tmp_path / "bad-schedule.toml"
    config_path.write_text(
        """
        migration_pulses = "not-a-list"

        [simulation]
        start_bce = 3100
        end_bce = 3000

        [parameters]
        migration_rate = 0.003

        [counts.britain]
        local = 100
        steppe = 5
        """,
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="migration_pulses"):
        load_config(config_path)


@pytest.mark.parametrize(
    "extra_config,match",
    [
        ('region_parameters = "bad"\n', "region_parameters"),
        (
            """
            [source_parameters.britain]
            steppe = "bad"
            """,
            "source_parameters",
        ),
    ],
)
def test_load_config_rejects_bad_parameter_tables(
    tmp_path: Path, extra_config: str, match: str
) -> None:
    """Parameter override tables should have the expected nested shape."""
    config_path = tmp_path / "bad-parameters.toml"
    config_path.write_text(
        f"""
        {extra_config}

        [simulation]
        start_bce = 3100
        end_bce = 3000

        [parameters]
        migration_rate = 0.003

        [counts.britain]
        local = 100
        steppe = 5
        """,
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=match):
        load_config(config_path)
