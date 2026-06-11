"""Target-aligned regional structure workflow helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path

from indoeuropop.data.target_notes import (
    append_target_note_metadata,
    target_note_value,
)
from indoeuropop.data.targets import (
    TargetDataset,
    TargetObservation,
    write_target_dataset_csv,
)
from indoeuropop.models import PopulationState
from indoeuropop.models.parameterization import ParameterSet
from indoeuropop.orchestration.sweep_config_export import (
    sweep_spec_to_toml as sweep_spec_to_toml,
)
from indoeuropop.orchestration.sweep_config_export import (
    write_sweep_spec_toml,
)
from indoeuropop.orchestration.sweeps import SweepSpec
from indoeuropop.simulation.events import MigrationPulse, SimulationSchedule


@dataclass(frozen=True)
class StructuredRegionMapping:
    """Mapping from an original target region to a structured model region."""

    original_region: str
    structure_value: str
    structured_region: str


@dataclass(frozen=True)
class TargetStructureOutputPaths:
    """Output paths for structured target/config artifacts."""

    structured_targets_csv: Path | None = None
    structured_config_toml: Path | None = None


@dataclass(frozen=True)
class TargetStructureWorkflowResult:
    """Structured target dataset, sweep spec, and region mappings."""

    targets: TargetDataset
    spec: SweepSpec
    mappings: tuple[StructuredRegionMapping, ...]
    structured_targets_csv_path: Path | None = None
    structured_config_toml_path: Path | None = None


def run_target_structure_workflow(
    spec: SweepSpec,
    targets: TargetDataset,
    *,
    structure_field: str = "note:requested_group_id",
    structure_regions: Iterable[str] = (),
    paths: TargetStructureOutputPaths | None = None,
) -> TargetStructureWorkflowResult:
    """Project selected targets and a sweep spec into structured subregions."""
    target_dataset = targets.require_observations()
    selected_regions = frozenset(structure_regions)
    structured_targets, mappings = structure_target_dataset(
        target_dataset,
        structure_field=structure_field,
        structure_regions=selected_regions,
    )
    structured_spec = structure_sweep_spec(spec, mappings)
    output_paths = TargetStructureOutputPaths() if paths is None else paths
    if output_paths.structured_targets_csv is not None:
        write_target_dataset_csv(
            structured_targets, output_paths.structured_targets_csv
        )
    if output_paths.structured_config_toml is not None:
        write_sweep_spec_toml(structured_spec, output_paths.structured_config_toml)
    return TargetStructureWorkflowResult(
        targets=structured_targets,
        spec=structured_spec,
        mappings=mappings,
        structured_targets_csv_path=output_paths.structured_targets_csv,
        structured_config_toml_path=output_paths.structured_config_toml,
    )


def structure_target_dataset(
    targets: TargetDataset,
    *,
    structure_field: str,
    structure_regions: Iterable[str] = (),
) -> tuple[TargetDataset, tuple[StructuredRegionMapping, ...]]:
    """Return targets relabeled into target-aligned structured regions."""
    selected_regions = frozenset(structure_regions)
    mapping_by_key: dict[tuple[str, str], StructuredRegionMapping] = {}
    observations: list[TargetObservation] = []
    for observation in targets.require_observations().observations:
        if selected_regions and observation.region not in selected_regions:
            observations.append(observation)
            continue
        structure_value = _structure_value(observation, structure_field)
        key = (observation.region, structure_value)
        mapping = mapping_by_key.setdefault(
            key,
            StructuredRegionMapping(
                original_region=observation.region,
                structure_value=structure_value,
                structured_region=_structured_region(
                    observation.region, structure_value
                ),
            ),
        )
        observations.append(_structured_observation(observation, mapping))
    return TargetDataset.from_rows(observations), tuple(mapping_by_key.values())


def structure_sweep_spec(
    spec: SweepSpec, mappings: Iterable[StructuredRegionMapping]
) -> SweepSpec:
    """Return a sweep spec with selected parent regions split into subregions."""
    mapping_tuple = tuple(mappings)
    if not mapping_tuple:
        return spec
    children_by_parent = _children_by_parent(mapping_tuple)
    return replace(
        spec,
        initial_state=_structured_state(spec.initial_state, children_by_parent),
        schedule=_structured_schedule(spec.schedule, children_by_parent),
        parameter_set=_structured_parameter_set(spec.parameter_set, children_by_parent),
        region=None if spec.region in children_by_parent else spec.region,
    )


def _structured_observation(
    observation: TargetObservation, mapping: StructuredRegionMapping
) -> TargetObservation:
    """Return one observation relabeled to a structured region."""
    return replace(
        observation,
        region=mapping.structured_region,
        note=append_target_note_metadata(
            observation.note,
            {
                "parent_region": mapping.original_region,
                "structure_value": mapping.structure_value,
                "structured_region": mapping.structured_region,
            },
        ),
    )


def _structure_value(observation: TargetObservation, structure_field: str) -> str:
    """Return one structure label from target fields or note metadata."""
    if structure_field == "region":
        return observation.region
    if structure_field == "source":
        return observation.source
    if structure_field == "citation_key":
        return observation.citation_key
    if structure_field.startswith("note:"):
        return target_note_value(
            observation.note, structure_field.removeprefix("note:")
        )
    raise ValueError(
        "structure_field must be one of region, source, citation_key, or note:<key>"
    )


def _structured_region(original_region: str, structure_value: str) -> str:
    """Return a stable structured region label."""
    return f"{_slug(original_region)}__{_slug(structure_value)}"


def _slug(value: str) -> str:
    """Return a lowercase identifier for a region or target label."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    if not slug:
        raise ValueError("structured region labels must not be empty")
    return slug


def _children_by_parent(
    mappings: tuple[StructuredRegionMapping, ...],
) -> dict[str, tuple[str, ...]]:
    """Return structured child regions grouped by parent region."""
    grouped: dict[str, list[str]] = {}
    for mapping in mappings:
        grouped.setdefault(mapping.original_region, []).append(
            mapping.structured_region
        )
    return {parent: tuple(children) for parent, children in grouped.items()}


def _structured_state(
    state: PopulationState, children_by_parent: dict[str, tuple[str, ...]]
) -> PopulationState:
    """Return initial counts split evenly across structured child regions."""
    counts: dict[str, dict[str, float]] = {}
    for region, source_counts in state.counts.items():
        child_regions = children_by_parent.get(region)
        if child_regions is None:
            counts[region] = dict(source_counts)
            continue
        divisor = float(len(child_regions))
        for child_region in child_regions:
            counts[child_region] = {
                source: value / divisor for source, value in source_counts.items()
            }
    return PopulationState(counts)


def _structured_schedule(
    schedule: SimulationSchedule, children_by_parent: dict[str, tuple[str, ...]]
) -> SimulationSchedule:
    """Return a schedule with parent migration pulses copied to child regions."""
    pulses: list[MigrationPulse] = []
    for pulse in schedule.migration_pulses:
        child_regions = children_by_parent.get(pulse.region)
        if child_regions is None:
            pulses.append(pulse)
            continue
        for child_region in child_regions:
            pulses.append(replace(pulse, region=child_region))
    return replace(schedule, migration_pulses=tuple(pulses))


def _structured_parameter_set(
    parameter_set: ParameterSet, children_by_parent: dict[str, tuple[str, ...]]
) -> ParameterSet:
    """Return parameter tables with parent rows copied to child regions."""
    region_parameters = dict(parameter_set.region_parameters)
    source_parameters = {
        region: dict(source_table)
        for region, source_table in parameter_set.source_parameters.items()
    }
    for parent, children in children_by_parent.items():
        parent_region_parameters = region_parameters.pop(parent, None)
        parent_source_parameters = source_parameters.pop(parent, None)
        for child in children:
            if parent_region_parameters is not None:
                region_parameters[child] = parent_region_parameters
            if parent_source_parameters is not None:
                source_parameters[child] = dict(parent_source_parameters)
    return ParameterSet(region_parameters, source_parameters)
