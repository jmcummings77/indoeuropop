"""Input preparation helpers for source-model sensitivity workflows."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TypeVar

from indoeuropop.data.target_notes import target_note_metadata
from indoeuropop.data.targets import TargetDataset, TargetObservation
from indoeuropop.orchestration.child_region_overrides import (
    ChildRegionOverrideSet,
)
from indoeuropop.orchestration.structural_smc_source_model_sensitivity_models import (
    StructuralSMCSourceModel,
)
from indoeuropop.orchestration.target_fragility import (
    load_target_fragility_decisions,
)

_T = TypeVar("_T")


def source_model_tuple(
    source_models: Iterable[StructuralSMCSourceModel],
) -> tuple[StructuralSMCSourceModel, ...]:
    """Return unique source models in request order."""
    models = tuple(source_models)
    if len(models) < 2:
        raise ValueError("source-model sensitivity requires at least two models")
    labels = [model.label for model in models]
    if len(set(labels)) != len(labels):
        raise ValueError("source model labels must be unique")
    return models


def common_target_ids(
    source_models: tuple[StructuralSMCSourceModel, ...],
    align_common_targets: bool,
) -> tuple[str, ...]:
    """Return target IDs to retain across source-model target surfaces."""
    target_ids_by_model = tuple(target_ids(model.targets) for model in source_models)
    if not align_common_targets:
        return target_ids_by_model[0]
    common = set(target_ids_by_model[0])
    for model_target_ids in target_ids_by_model[1:]:
        common.intersection_update(model_target_ids)
    ordered = tuple(
        target_id for target_id in target_ids_by_model[0] if target_id in common
    )
    if not ordered:
        raise ValueError("source models share no target IDs")
    return ordered


def target_ids(targets: TargetDataset) -> tuple[str, ...]:
    """Return unique target IDs from a target dataset."""
    ids = tuple(target_id(observation) for observation in targets.observations)
    if len(set(ids)) != len(ids):
        raise ValueError("source-model target datasets require unique target IDs")
    return ids


def target_id(observation: TargetObservation) -> str:
    """Return the explicit target ID encoded in a target note."""
    value = target_note_metadata(observation.note).get("target_id", "").strip()
    if not value:
        raise ValueError("source-model target observations require target_id notes")
    return value


def filter_targets_by_ids(
    targets: TargetDataset,
    retained_ids: tuple[str, ...],
) -> TargetDataset:
    """Return target observations ordered by retained target ID."""
    observation_by_id = {
        target_id(observation): observation for observation in targets.observations
    }
    return TargetDataset.from_rows(
        observation_by_id[target_id_value]
        for target_id_value in retained_ids
        if target_id_value in observation_by_id
    ).require_observations()


def fragile_target_ids(
    sample_audit_csv: str | Path | None,
    *,
    excluded_flags: Iterable[str],
    exclude_repeated_estimates: bool,
    repeated_estimate_tolerance: float,
) -> frozenset[str]:
    """Return target IDs excluded by an optional fragility audit."""
    if sample_audit_csv is None:
        return frozenset()
    return frozenset(
        decision.target_id
        for decision in load_target_fragility_decisions(
            sample_audit_csv,
            excluded_flags=excluded_flags,
            exclude_repeated_estimates=exclude_repeated_estimates,
            repeated_estimate_tolerance=repeated_estimate_tolerance,
        )
        if decision.excluded
    )


def restrict_child_region_overrides(
    overrides: ChildRegionOverrideSet,
    known_regions: Iterable[str],
    *,
    require_all: bool,
) -> tuple[ChildRegionOverrideSet, tuple[str, ...]]:
    """Return overrides restricted to known regions plus missing region labels."""
    known = frozenset(known_regions)
    all_regions = _override_regions(overrides)
    missing = tuple(region for region in all_regions if region not in known)
    if missing and require_all:
        raise ValueError(f"source model is missing child override regions: {missing}")
    filtered = ChildRegionOverrideSet(
        counts=_known_mapping(overrides.counts, known),
        migration_pulses=tuple(
            pulse for pulse in overrides.migration_pulses if pulse.region in known
        ),
        region_parameters=_known_mapping(overrides.region_parameters, known),
        source_parameters=_known_mapping(overrides.source_parameters, known),
        replace_migration_pulses=overrides.replace_migration_pulses,
    )
    return filtered, missing


def _override_regions(overrides: ChildRegionOverrideSet) -> tuple[str, ...]:
    """Return override region labels in first-seen order."""
    regions: list[str] = []
    for region in (
        *overrides.counts,
        *(pulse.region for pulse in overrides.migration_pulses),
        *overrides.region_parameters,
        *overrides.source_parameters,
    ):
        if region not in regions:
            regions.append(region)
    return tuple(regions)


def _known_mapping(
    values: Mapping[str, _T],
    known_regions: frozenset[str],
) -> dict[str, _T]:
    """Return mapping entries whose region keys are known."""
    return {
        region: value for region, value in values.items() if region in known_regions
    }
