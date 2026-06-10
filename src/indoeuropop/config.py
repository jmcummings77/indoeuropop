"""Configuration loading for small TOML simulation scenarios."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from indoeuropop.events import ForcingWindow, MigrationPulse, SimulationSchedule
from indoeuropop.models import PopulationState, SimulationParameters


@dataclass(frozen=True)
class SimulationConfig:
    """A complete runnable simulation configuration."""

    initial_state: PopulationState
    parameters: SimulationParameters
    start_bce: float = 3500.0
    end_bce: float = 1500.0
    step_years: float = 25.0
    schedule: SimulationSchedule = field(default_factory=SimulationSchedule)


def default_config() -> SimulationConfig:
    """Return a tiny built-in scenario for CLI smoke runs and examples."""
    return SimulationConfig(
        initial_state=PopulationState({"britain": {"local": 1000.0, "steppe": 25.0}}),
        parameters=SimulationParameters(),
        start_bce=3000.0,
        end_bce=2500.0,
        step_years=50.0,
        schedule=SimulationSchedule(),
    )


def load_config(path: str | Path) -> SimulationConfig:
    """Load a simulation configuration from a TOML file.

    Expected TOML shape:

    ```toml
    [simulation]
    start_bce = 3000
    end_bce = 2500
    step_years = 50

    [parameters]
    migration_rate = 0.002

    [counts.britain]
    local = 1000
    steppe = 25

    [[migration_pulses]]
    region = "britain"
    start_bce = 2900
    end_bce = 2700
    annual_rate = 0.003

    [[forcing_windows]]
    start_bce = 2850
    end_bce = 2750
    climate_stress_delta = 0.2
    epidemic_mortality_delta = 0.01
    ```
    """
    config_path = Path(path)
    with config_path.open("rb") as config_file:
        raw_config = tomllib.load(config_file)

    simulation = _table(raw_config, "simulation")
    return SimulationConfig(
        initial_state=PopulationState(_table(raw_config, "counts")),
        parameters=SimulationParameters(**_table(raw_config, "parameters")),
        start_bce=float(simulation.get("start_bce", 3500.0)),
        end_bce=float(simulation.get("end_bce", 1500.0)),
        step_years=float(simulation.get("step_years", 25.0)),
        schedule=SimulationSchedule(
            migration_pulses=tuple(
                MigrationPulse(**pulse)
                for pulse in _optional_table_list(raw_config, "migration_pulses")
            ),
            forcing_windows=tuple(
                ForcingWindow(**window)
                for window in _optional_table_list(raw_config, "forcing_windows")
            ),
        ),
    )


def _table(raw_config: dict[str, Any], key: str) -> dict[str, Any]:
    """Return a TOML table or raise a clear error for malformed config."""
    value = raw_config.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} table is required")
    return value


def _optional_table_list(
    raw_config: dict[str, Any], key: str
) -> tuple[dict[str, Any], ...]:
    """Return an optional TOML array-of-tables with clear validation errors."""
    value = raw_config.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{key} must be a list of tables")
    return tuple(value)
