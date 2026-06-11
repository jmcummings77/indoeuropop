"""One-factor candidate generation for child-override sensitivity sweeps."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from math import isfinite

from indoeuropop.analysis.override_sensitivity import OverrideSensitivityCandidate
from indoeuropop.models.parameterization import SourceParameters
from indoeuropop.orchestration.child_region_overrides import ChildRegionOverrideSet
from indoeuropop.simulation.events import MigrationPulse


def child_override_sensitivity_candidates(
    overrides: ChildRegionOverrideSet,
    *,
    count_factors: Iterable[float] = (0.9, 1.1),
    pulse_rate_factors: Iterable[float] = (0.85, 1.15),
    pulse_window_shifts: Iterable[float] = (-50.0, 50.0),
    reproductive_multiplier_factors: Iterable[float] = (0.95, 1.05),
    source: str = "steppe",
) -> tuple[OverrideSensitivityCandidate, ...]:
    """Return one-factor sensitivity candidates around a curated override set."""
    if not source:
        raise ValueError("source must be non-empty")
    candidates = [_baseline_candidate(overrides)]
    factors = _candidate_factors(count_factors)
    rate_factors = _candidate_factors(pulse_rate_factors)
    shifts = _candidate_shifts(pulse_window_shifts)
    reproductive_factors = _candidate_factors(reproductive_multiplier_factors)
    for region in sorted(overrides.counts):
        candidates.extend(_count_candidates(overrides, region, factors))
        candidates.extend(_pulse_rate_candidates(overrides, region, rate_factors))
        candidates.extend(_pulse_window_candidates(overrides, region, shifts))
        candidates.extend(
            _reproductive_candidates(overrides, region, source, reproductive_factors)
        )
    return tuple(candidates)


def child_override_count_reproduction_interaction_candidates(
    overrides: ChildRegionOverrideSet,
    *,
    regions: Iterable[str] = (),
    count_factors: Iterable[float] = (0.9, 1.0, 1.1),
    reproductive_multiplier_factors: Iterable[float] = (0.9, 0.95, 1.0, 1.05),
    source: str = "steppe",
) -> tuple[OverrideSensitivityCandidate, ...]:
    """Return per-region Steppe count and reproduction interaction candidates."""
    if not source:
        raise ValueError("source must be non-empty")
    selected_regions = _selected_interaction_regions(overrides, regions, source)
    count_factor_tuple = _grid_factors(count_factors)
    reproductive_factor_tuple = _grid_factors(reproductive_multiplier_factors)
    candidates = [_baseline_candidate(overrides)]
    for region in selected_regions:
        candidates.extend(
            _count_reproduction_candidates(
                overrides,
                region,
                source,
                count_factor_tuple,
                reproductive_factor_tuple,
            )
        )
    return tuple(candidates)


def _baseline_candidate(
    overrides: ChildRegionOverrideSet,
) -> OverrideSensitivityCandidate:
    """Return the unmodified curated override candidate."""
    return OverrideSensitivityCandidate("curated", overrides, "all", "baseline", 0, 0)


def _count_candidates(
    overrides: ChildRegionOverrideSet,
    region: str,
    factors: tuple[float, ...],
) -> tuple[OverrideSensitivityCandidate, ...]:
    """Return count scaling candidates for one child region."""
    candidates: list[OverrideSensitivityCandidate] = []
    for source, base_count in sorted(overrides.counts[region].items()):
        for factor in factors:
            counts = _nested_counts(overrides)
            counts[region][source] = base_count * factor
            candidates.append(
                OverrideSensitivityCandidate(
                    _candidate_name(region, f"{source}_count", factor),
                    _with_counts(overrides, counts),
                    region,
                    f"{source}_count",
                    base_count,
                    counts[region][source],
                )
            )
    return tuple(candidates)


def _pulse_rate_candidates(
    overrides: ChildRegionOverrideSet,
    region: str,
    factors: tuple[float, ...],
) -> tuple[OverrideSensitivityCandidate, ...]:
    """Return migration-pulse annual-rate candidates for one child region."""
    region_pulses = _region_pulses(overrides, region)
    if not region_pulses:
        return ()
    base_rate = region_pulses[0].annual_rate
    return tuple(
        OverrideSensitivityCandidate(
            _candidate_name(region, "pulse_rate", factor),
            _with_pulses(overrides, _rate_scaled_pulses(overrides, region, factor)),
            region,
            "pulse_rate",
            base_rate,
            base_rate * factor,
        )
        for factor in factors
    )


def _pulse_window_candidates(
    overrides: ChildRegionOverrideSet,
    region: str,
    shifts: tuple[float, ...],
) -> tuple[OverrideSensitivityCandidate, ...]:
    """Return migration-pulse window-shift candidates for one child region."""
    if not _region_pulses(overrides, region):
        return ()
    return tuple(
        OverrideSensitivityCandidate(
            _candidate_name(region, "pulse_window_shift", shift),
            _with_pulses(overrides, _window_shifted_pulses(overrides, region, shift)),
            region,
            "pulse_window_shift",
            0,
            shift,
        )
        for shift in shifts
    )


def _reproductive_candidates(
    overrides: ChildRegionOverrideSet,
    region: str,
    source: str,
    factors: tuple[float, ...],
) -> tuple[OverrideSensitivityCandidate, ...]:
    """Return source reproductive-multiplier candidates for one child region."""
    source_parameters = overrides.source_parameters.get(region, {}).get(source)
    if source_parameters is None or source_parameters.reproductive_multiplier is None:
        return ()
    base_multiplier = source_parameters.reproductive_multiplier
    return tuple(
        OverrideSensitivityCandidate(
            _candidate_name(region, f"{source}_reproductive_multiplier", factor),
            _with_source_parameter(
                overrides,
                region,
                source,
                replace(
                    source_parameters,
                    reproductive_multiplier=base_multiplier * factor,
                ),
            ),
            region,
            f"{source}_reproductive_multiplier",
            base_multiplier,
            base_multiplier * factor,
        )
        for factor in factors
    )


def _count_reproduction_candidates(
    overrides: ChildRegionOverrideSet,
    region: str,
    source: str,
    count_factors: tuple[float, ...],
    reproductive_factors: tuple[float, ...],
) -> tuple[OverrideSensitivityCandidate, ...]:
    """Return one region's count-by-reproduction interaction grid."""
    base_count = overrides.counts[region][source]
    source_parameters = overrides.source_parameters[region][source]
    base_multiplier = source_parameters.reproductive_multiplier
    assert base_multiplier is not None
    candidates: list[OverrideSensitivityCandidate] = []
    for count_factor in count_factors:
        for reproductive_factor in reproductive_factors:
            if count_factor == 1.0 and reproductive_factor == 1.0:
                continue
            counts = _nested_counts(overrides)
            counts[region][source] = base_count * count_factor
            counted = _with_counts(overrides, counts)
            varied = _with_source_parameter(
                counted,
                region,
                source,
                replace(
                    source_parameters,
                    reproductive_multiplier=base_multiplier * reproductive_factor,
                ),
            )
            candidates.append(
                OverrideSensitivityCandidate(
                    _interaction_name(
                        region, source, count_factor, reproductive_factor
                    ),
                    varied,
                    region,
                    f"{source}_count_x_{source}_reproductive_multiplier",
                    1.0,
                    count_factor * reproductive_factor,
                )
            )
    return tuple(candidates)


def _with_counts(
    overrides: ChildRegionOverrideSet, counts: dict[str, dict[str, float]]
) -> ChildRegionOverrideSet:
    """Return overrides with replacement count tables."""
    return ChildRegionOverrideSet(
        counts=counts,
        migration_pulses=overrides.migration_pulses,
        region_parameters=overrides.region_parameters,
        source_parameters=overrides.source_parameters,
        replace_migration_pulses=overrides.replace_migration_pulses,
    )


def _with_pulses(
    overrides: ChildRegionOverrideSet, pulses: tuple[MigrationPulse, ...]
) -> ChildRegionOverrideSet:
    """Return overrides with replacement migration pulses."""
    return ChildRegionOverrideSet(
        counts=overrides.counts,
        migration_pulses=pulses,
        region_parameters=overrides.region_parameters,
        source_parameters=overrides.source_parameters,
        replace_migration_pulses=overrides.replace_migration_pulses,
    )


def _with_source_parameter(
    overrides: ChildRegionOverrideSet,
    region: str,
    source: str,
    parameters: SourceParameters,
) -> ChildRegionOverrideSet:
    """Return overrides with one source-parameter table replaced."""
    source_parameters = _nested_source_parameters(overrides)
    source_parameters.setdefault(region, {})[source] = parameters
    return ChildRegionOverrideSet(
        counts=overrides.counts,
        migration_pulses=overrides.migration_pulses,
        region_parameters=overrides.region_parameters,
        source_parameters=source_parameters,
        replace_migration_pulses=overrides.replace_migration_pulses,
    )


def _rate_scaled_pulses(
    overrides: ChildRegionOverrideSet, region: str, factor: float
) -> tuple[MigrationPulse, ...]:
    """Return pulses with one region's annual rates scaled."""
    return tuple(
        (
            replace(pulse, annual_rate=pulse.annual_rate * factor)
            if pulse.region == region
            else pulse
        )
        for pulse in overrides.migration_pulses
    )


def _window_shifted_pulses(
    overrides: ChildRegionOverrideSet, region: str, shift_years: float
) -> tuple[MigrationPulse, ...]:
    """Return pulses with one region's BCE windows shifted."""
    return tuple(
        _shift_pulse(pulse, shift_years) if pulse.region == region else pulse
        for pulse in overrides.migration_pulses
    )


def _shift_pulse(pulse: MigrationPulse, shift_years: float) -> MigrationPulse:
    """Return a pulse with start and end BCE years shifted together."""
    return replace(
        pulse,
        start_bce=pulse.start_bce + shift_years,
        end_bce=pulse.end_bce + shift_years,
    )


def _region_pulses(
    overrides: ChildRegionOverrideSet, region: str
) -> tuple[MigrationPulse, ...]:
    """Return migration pulses that target one region."""
    return tuple(
        pulse for pulse in overrides.migration_pulses if pulse.region == region
    )


def _nested_counts(
    overrides: ChildRegionOverrideSet,
) -> dict[str, dict[str, float]]:
    """Return mutable copies of nested count overrides."""
    return {region: dict(counts) for region, counts in overrides.counts.items()}


def _nested_source_parameters(
    overrides: ChildRegionOverrideSet,
) -> dict[str, dict[str, SourceParameters]]:
    """Return mutable copies of nested source-parameter overrides."""
    return {
        region: dict(source_table)
        for region, source_table in overrides.source_parameters.items()
    }


def _candidate_factors(values: Iterable[float]) -> tuple[float, ...]:
    """Return positive, non-unit scaling factors."""
    factors = tuple(float(value) for value in values)
    if any(not isfinite(factor) or factor <= 0 for factor in factors):
        raise ValueError("sensitivity factors must be finite and positive")
    return tuple(dict.fromkeys(factor for factor in factors if factor != 1.0))


def _candidate_shifts(values: Iterable[float]) -> tuple[float, ...]:
    """Return finite, non-zero BCE year shifts."""
    shifts = tuple(float(value) for value in values)
    if any(not isfinite(shift) for shift in shifts):
        raise ValueError("pulse window shifts must be finite")
    return tuple(dict.fromkeys(shift for shift in shifts if shift != 0.0))


def _grid_factors(values: Iterable[float]) -> tuple[float, ...]:
    """Return positive scaling factors for interaction grids, preserving 1.0."""
    factors = tuple(float(value) for value in values)
    if any(not isfinite(factor) or factor <= 0 for factor in factors):
        raise ValueError("interaction factors must be finite and positive")
    return tuple(dict.fromkeys(factors))


def _selected_interaction_regions(
    overrides: ChildRegionOverrideSet, regions: Iterable[str], source: str
) -> tuple[str, ...]:
    """Return child regions that have both source counts and multipliers."""
    requested_regions = tuple(region.strip() for region in regions if region.strip())
    selected = requested_regions or tuple(sorted(overrides.counts))
    if not selected:
        raise ValueError("interaction regions must contain at least one region")
    for region in selected:
        if source not in overrides.counts.get(region, {}):
            raise ValueError(f"interaction region lacks source count: {region}")
        source_parameters = overrides.source_parameters.get(region, {}).get(source)
        if (
            source_parameters is None
            or source_parameters.reproductive_multiplier is None
        ):
            raise ValueError(f"interaction region lacks multiplier: {region}")
    return selected


def _candidate_name(region: str, parameter: str, value: float) -> str:
    """Return a stable candidate name from a region, parameter, and value."""
    value_label = str(value).replace("-", "minus_").replace(".", "_")
    return f"{_slug(region)}__{_slug(parameter)}__{_slug(value_label)}"


def _interaction_name(
    region: str, source: str, count_factor: float, reproductive_factor: float
) -> str:
    """Return a stable name for a count-by-reproduction interaction candidate."""
    count_label = str(count_factor).replace(".", "_")
    reproductive_label = str(reproductive_factor).replace(".", "_")
    return (
        f"{_slug(region)}__{_slug(source)}_count__{_slug(count_label)}"
        f"__{_slug(source)}_reproductive_multiplier__{_slug(reproductive_label)}"
    )


def _slug(value: str) -> str:
    """Return a compact lower-case identifier fragment."""
    return "".join(
        character if character.isalnum() else "_" for character in value.lower()
    ).strip("_")
