"""Configuration loading for small TOML simulation scenarios."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from indoeuropop.models import PopulationState, SimulationParameters


@dataclass(frozen=True)
class SimulationConfig:
    """A complete runnable simulation configuration."""

    initial_state: PopulationState
    parameters: SimulationParameters
    start_bce: float = 3500.0
    end_bce: float = 1500.0
    step_years: float = 25.0


def default_config() -> SimulationConfig:
    """Return a tiny built-in scenario for CLI smoke runs and examples."""
    return SimulationConfig(
        initial_state=PopulationState({"britain": {"local": 1000.0, "steppe": 25.0}}),
        parameters=SimulationParameters(),
        start_bce=3000.0,
        end_bce=2500.0,
        step_years=50.0,
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
    )


def _table(raw_config: dict[str, Any], key: str) -> dict[str, Any]:
    """Return a TOML table or raise a clear error for malformed config."""
    value = raw_config.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} table is required")
    return value
