"""Apply curated child-region overrides to structured sweep specs."""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from indoeuropop.models import PopulationState
from indoeuropop.models.parameterization import (
    ParameterSet,
    RegionParameters,
    SourceParameters,
)
from indoeuropop.orchestration.sweep_config_export import write_sweep_spec_toml
from indoeuropop.orchestration.sweeps import SweepSpec
from indoeuropop.simulation.events import MigrationPulse, SimulationSchedule


@dataclass(frozen=True)
class ChildRegionOverrideSet:
    """Curated partial overrides for target-aligned child regions."""

    counts: Mapping[str, Mapping[str, float]] = field(default_factory=dict)
    migration_pulses: tuple[MigrationPulse, ...] = ()
    region_parameters: Mapping[str, RegionParameters] = field(default_factory=dict)
    source_parameters: Mapping[str, Mapping[str, SourceParameters]] = field(
        default_factory=dict
    )
    replace_migration_pulses: bool = True

    def __post_init__(self) -> None:
        """Validate override tables and normalize nested mappings."""
        normalized_counts = PopulationState(self.counts).counts if self.counts else {}
        parameter_set = ParameterSet(
            self.region_parameters,
            self.source_parameters,
        )
        if not any(
            (
                normalized_counts,
                self.migration_pulses,
                parameter_set.region_parameters,
                parameter_set.source_parameters,
            )
        ):
            raise ValueError(
                "child region override set must contain at least one override"
            )
        object.__setattr__(self, "counts", normalized_counts)
        object.__setattr__(self, "region_parameters", parameter_set.region_parameters)
        object.__setattr__(self, "source_parameters", parameter_set.source_parameters)


@dataclass(frozen=True)
class ChildRegionOverrideOutputPaths:
    """Output paths for child-region override artifacts."""

    overridden_config_toml: Path | None = None


@dataclass(frozen=True)
class ChildRegionOverrideWorkflowResult:
    """Result from applying child-region overrides to one sweep spec."""

    spec: SweepSpec
    overrides: ChildRegionOverrideSet
    overridden_config_toml_path: Path | None = None


def load_child_region_overrides(path: str | Path) -> ChildRegionOverrideSet:
    """Load child-region override tables from a partial TOML file."""
    override_path = Path(path)
    with override_path.open("rb") as override_file:
        raw_overrides = tomllib.load(override_file)

    replace_migration_pulses = _replace_migration_pulses(raw_overrides)
    return ChildRegionOverrideSet(
        counts=_load_count_overrides(raw_overrides),
        migration_pulses=tuple(
            MigrationPulse(**pulse)
            for pulse in _optional_table_list(raw_overrides, "migration_pulses")
        ),
        region_parameters={
            region: RegionParameters(**parameters)
            for region, parameters in _optional_named_tables(
                raw_overrides, "region_parameters"
            ).items()
        },
        source_parameters={
            region: {
                source: SourceParameters(**parameters)
                for source, parameters in source_table.items()
            }
            for region, source_table in _optional_nested_tables(
                raw_overrides, "source_parameters"
            ).items()
        },
        replace_migration_pulses=replace_migration_pulses,
    )


def run_child_region_override_workflow(
    spec: SweepSpec,
    overrides: ChildRegionOverrideSet,
    *,
    paths: ChildRegionOverrideOutputPaths | None = None,
) -> ChildRegionOverrideWorkflowResult:
    """Apply child-region overrides and optionally write the resulting config."""
    overridden_spec = apply_child_region_overrides(spec, overrides)
    output_paths = ChildRegionOverrideOutputPaths() if paths is None else paths
    if output_paths.overridden_config_toml is not None:
        write_sweep_spec_toml(overridden_spec, output_paths.overridden_config_toml)
    return ChildRegionOverrideWorkflowResult(
        spec=overridden_spec,
        overrides=overrides,
        overridden_config_toml_path=output_paths.overridden_config_toml,
    )


def apply_child_region_overrides(
    spec: SweepSpec,
    overrides: ChildRegionOverrideSet,
) -> SweepSpec:
    """Return a sweep spec with curated child-region overrides applied."""
    _validate_override_regions(spec, overrides)
    return replace(
        spec,
        initial_state=_initial_state_with_counts(spec, overrides),
        schedule=_schedule_with_pulse_overrides(spec, overrides),
        parameter_set=_parameter_set_with_overrides(spec, overrides),
    )


def _load_count_overrides(raw_overrides: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Return validated count overrides from TOML data."""
    raw_counts = _optional_named_tables(raw_overrides, "counts")
    if not raw_counts:
        return {}
    return {
        region: dict(source_counts)
        for region, source_counts in PopulationState(raw_counts).counts.items()
    }


def _replace_migration_pulses(raw_overrides: dict[str, Any]) -> bool:
    """Return the pulse replacement mode from an optional options table."""
    options = raw_overrides.get("options", {})
    if not isinstance(options, dict):
        raise ValueError("options must be a table")
    replace_pulses = options.get("replace_migration_pulses", True)
    if not isinstance(replace_pulses, bool):
        raise ValueError("replace_migration_pulses must be a boolean")
    return replace_pulses


def _optional_table_list(
    raw_overrides: dict[str, Any], key: str
) -> tuple[dict[str, Any], ...]:
    """Return an optional TOML array-of-tables with clear validation errors."""
    value = raw_overrides.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{key} must be a list of tables")
    return tuple(value)


def _optional_named_tables(raw_overrides: dict[str, Any], key: str) -> dict[str, Any]:
    """Return an optional TOML table of named child-region tables."""
    value = raw_overrides.get(key, {})
    if not isinstance(value, dict) or not all(
        isinstance(item, dict) for item in value.values()
    ):
        raise ValueError(f"{key} must be a table of tables")
    return value


def _optional_nested_tables(
    raw_overrides: dict[str, Any], key: str
) -> dict[str, dict[str, Any]]:
    """Return an optional TOML table nested two levels deep."""
    value = _optional_named_tables(raw_overrides, key)
    if not all(
        isinstance(source_table, dict)
        and all(isinstance(item, dict) for item in source_table.values())
        for source_table in value.values()
    ):
        raise ValueError(f"{key} must be a nested table of tables")
    return value


def _validate_override_regions(
    spec: SweepSpec,
    overrides: ChildRegionOverrideSet,
) -> None:
    """Raise if override tables reference regions outside the sweep spec."""
    known_regions = frozenset(spec.initial_state.regions())
    _validate_regions("count override", overrides.counts, known_regions)
    _validate_regions(
        "migration pulse override",
        (pulse.region for pulse in overrides.migration_pulses),
        known_regions,
    )
    _validate_regions(
        "region parameter override",
        overrides.region_parameters,
        known_regions,
    )
    _validate_regions(
        "source parameter override",
        overrides.source_parameters,
        known_regions,
    )


def _validate_regions(
    label: str,
    regions: Iterable[str],
    known_regions: frozenset[str],
) -> None:
    """Raise a compact error for unknown override region labels."""
    region_tuple = tuple(regions)
    unknown_regions = sorted(set(region_tuple).difference(known_regions))
    if unknown_regions:
        unknown_text = ", ".join(unknown_regions)
        raise ValueError(f"{label} references unknown regions: {unknown_text}")


def _initial_state_with_counts(
    spec: SweepSpec,
    overrides: ChildRegionOverrideSet,
) -> PopulationState:
    """Return an initial state with full child-region count replacements."""
    counts = {
        region: dict(source_counts)
        for region, source_counts in spec.initial_state.counts.items()
    }
    for region, source_counts in overrides.counts.items():
        counts[region] = dict(source_counts)
    return PopulationState(counts)


def _schedule_with_pulse_overrides(
    spec: SweepSpec,
    overrides: ChildRegionOverrideSet,
) -> SimulationSchedule:
    """Return a schedule with child-region migration pulse overrides applied."""
    if not overrides.migration_pulses:
        return spec.schedule
    replacement_regions = frozenset(
        pulse.region for pulse in overrides.migration_pulses
    )
    existing_pulses = tuple(
        pulse
        for pulse in spec.schedule.migration_pulses
        if not (
            overrides.replace_migration_pulses and pulse.region in replacement_regions
        )
    )
    return replace(
        spec.schedule,
        migration_pulses=(*existing_pulses, *overrides.migration_pulses),
    )


def _parameter_set_with_overrides(
    spec: SweepSpec,
    overrides: ChildRegionOverrideSet,
) -> ParameterSet:
    """Return parameter tables with child-region overrides applied."""
    region_parameters = dict(spec.parameter_set.region_parameters)
    region_parameters.update(overrides.region_parameters)
    source_parameters = {
        region: dict(source_table)
        for region, source_table in spec.parameter_set.source_parameters.items()
    }
    for region, source_table in overrides.source_parameters.items():
        merged_source_table = dict(source_parameters.get(region, {}))
        merged_source_table.update(source_table)
        source_parameters[region] = merged_source_table
    return ParameterSet(region_parameters, source_parameters)
