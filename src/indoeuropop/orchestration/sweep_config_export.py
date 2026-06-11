"""TOML export helpers for deterministic sweep specifications."""

from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

from indoeuropop.orchestration.sweeps import SweepSpec


def write_sweep_spec_toml(spec: SweepSpec, path: str | Path) -> Path:
    """Write a sweep spec as loadable TOML and return the output path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(sweep_spec_to_toml(spec), encoding="utf-8")
    return output_path


def sweep_spec_to_toml(spec: SweepSpec) -> str:
    """Return a loadable TOML representation of a sweep spec."""
    lines = [
        "[simulation]",
        f"start_bce = {_value_text(spec.start_bce)}",
        f"end_bce = {_value_text(spec.end_bce)}",
        f"step_years = {_value_text(spec.step_years)}",
        "",
        "[parameters]",
    ]
    parameters = spec.base_parameters
    for field in fields(parameters):
        name = field.name
        lines.append(f"{name} = {_value_text(getattr(parameters, name))}")
    lines.extend(("", *_counts_tables(spec), *_sweep_lines(spec)))
    lines.extend(_migration_pulse_tables(spec))
    lines.extend(_forcing_window_tables(spec))
    lines.extend(_region_parameter_tables(spec))
    lines.extend(_source_parameter_tables(spec))
    lines.extend(_parameter_range_tables(spec))
    return "\n".join(lines).rstrip() + "\n"


def _counts_tables(spec: SweepSpec) -> tuple[str, ...]:
    """Return TOML count tables."""
    lines: list[str] = []
    for region, source_counts in spec.initial_state.counts.items():
        lines.extend(("", f"[counts.{_quoted_key(region)}]"))
        for source, count in source_counts.items():
            lines.append(f"{_quoted_key(source)} = {_value_text(count)}")
    return tuple(lines)


def _sweep_lines(spec: SweepSpec) -> tuple[str, ...]:
    """Return TOML sweep metadata lines."""
    lines = [
        "[sweep]",
        f"sample_count = {spec.sample_count}",
        f"seed = {spec.seed}",
        f"source = {_quoted_string(spec.source)}",
    ]
    if spec.region is not None:
        lines.append(f"region = {_quoted_string(spec.region)}")
    return tuple(lines)


def _migration_pulse_tables(spec: SweepSpec) -> tuple[str, ...]:
    """Return TOML migration pulse tables."""
    lines: list[str] = []
    for pulse in spec.schedule.migration_pulses:
        lines.extend(
            (
                "",
                "[[migration_pulses]]",
                f"region = {_quoted_string(pulse.region)}",
                f"start_bce = {_value_text(pulse.start_bce)}",
                f"end_bce = {_value_text(pulse.end_bce)}",
                f"annual_rate = {_value_text(pulse.annual_rate)}",
            )
        )
    return tuple(lines)


def _forcing_window_tables(spec: SweepSpec) -> tuple[str, ...]:
    """Return TOML forcing window tables."""
    lines: list[str] = []
    for window in spec.schedule.forcing_windows:
        lines.extend(
            (
                "",
                "[[forcing_windows]]",
                f"start_bce = {_value_text(window.start_bce)}",
                f"end_bce = {_value_text(window.end_bce)}",
                f"climate_stress_delta = {_value_text(window.climate_stress_delta)}",
                "epidemic_mortality_delta = "
                f"{_value_text(window.epidemic_mortality_delta)}",
            )
        )
    return tuple(lines)


def _region_parameter_tables(spec: SweepSpec) -> tuple[str, ...]:
    """Return TOML region parameter override tables."""
    lines: list[str] = []
    for region, parameters in spec.parameter_set.region_parameters.items():
        lines.extend(("", f"[region_parameters.{_quoted_key(region)}]"))
        for name, value in parameters.__dict__.items():
            if value is not None:
                lines.append(f"{name} = {_value_text(value)}")
    return tuple(lines)


def _source_parameter_tables(spec: SweepSpec) -> tuple[str, ...]:
    """Return TOML source parameter override tables."""
    lines: list[str] = []
    for region, source_table in spec.parameter_set.source_parameters.items():
        for source, parameters in source_table.items():
            lines.extend(
                ("", f"[source_parameters.{_quoted_key(region)}.{_quoted_key(source)}]")
            )
            for name, value in parameters.__dict__.items():
                if value is not None:
                    lines.append(f"{name} = {_value_text(value)}")
    return tuple(lines)


def _parameter_range_tables(spec: SweepSpec) -> tuple[str, ...]:
    """Return TOML parameter range tables."""
    lines: list[str] = []
    for parameter_range in spec.parameter_ranges:
        lines.extend(
            (
                "",
                "[[parameter_ranges]]",
                f"name = {_quoted_string(parameter_range.name)}",
                f"low = {_value_text(parameter_range.low)}",
                f"high = {_value_text(parameter_range.high)}",
            )
        )
    return tuple(lines)


def _quoted_key(value: str) -> str:
    """Return a TOML-safe key string."""
    if re.fullmatch(r"[A-Za-z0-9_-]+", value):
        return value
    return _quoted_string(value)


def _quoted_string(value: str) -> str:
    """Return a minimally escaped TOML string."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _value_text(value: float) -> str:
    """Return a stable TOML numeric representation."""
    return f"{float(value):.12g}"
