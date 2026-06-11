"""Region and source-specific simulation parameter overrides."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from math import isfinite

from indoeuropop.models import SimulationParameters

LOCAL_SOURCE = "local"
STEPPE_SOURCE = "steppe"


def _optional_probability(name: str, value: float | None) -> float | None:
    """Return an optional probability after validation."""
    if value is None:
        return None
    numeric_value = float(value)
    if not isfinite(numeric_value) or numeric_value < 0 or numeric_value > 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return numeric_value


def _optional_non_negative(name: str, value: float | None) -> float | None:
    """Return an optional non-negative scalar after validation."""
    if value is None:
        return None
    numeric_value = float(value)
    if not isfinite(numeric_value) or numeric_value < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return numeric_value


@dataclass(frozen=True)
class RegionParameters:
    """Optional overrides for parameters shared by all sources in one region."""

    migration_rate: float | None = None
    epidemic_mortality_rate: float | None = None
    violence_mortality_rate: float | None = None
    climate_stress: float | None = None

    def __post_init__(self) -> None:
        """Validate optional region-level rate overrides."""
        for field_name in (
            "migration_rate",
            "epidemic_mortality_rate",
            "violence_mortality_rate",
            "climate_stress",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_probability(field_name, getattr(self, field_name)),
            )

    def apply(self, parameters: SimulationParameters) -> SimulationParameters:
        """Return base parameters with this region's non-None overrides applied."""
        replacements = {
            field_name: value
            for field_name, value in (
                ("migration_rate", self.migration_rate),
                ("epidemic_mortality_rate", self.epidemic_mortality_rate),
                ("violence_mortality_rate", self.violence_mortality_rate),
                ("climate_stress", self.climate_stress),
            )
            if value is not None
        }
        return replace(parameters, **replacements)


@dataclass(frozen=True)
class SourceParameters:
    """Optional overrides for one source inside one region."""

    fertility_rate: float | None = None
    mortality_rate: float | None = None
    epidemic_risk: float | None = None
    reproductive_multiplier: float | None = None

    def __post_init__(self) -> None:
        """Validate optional source-level rate and multiplier overrides."""
        for field_name in ("fertility_rate", "mortality_rate", "epidemic_risk"):
            object.__setattr__(
                self,
                field_name,
                _optional_probability(field_name, getattr(self, field_name)),
            )
        object.__setattr__(
            self,
            "reproductive_multiplier",
            _optional_non_negative(
                "reproductive_multiplier", self.reproductive_multiplier
            ),
        )


@dataclass(frozen=True)
class ResolvedSourceParameters:
    """Concrete source parameters used for one simulation step."""

    fertility_rate: float
    mortality_rate: float
    epidemic_risk: float
    reproductive_multiplier: float


@dataclass(frozen=True)
class ParameterSet:
    """Region/source parameter tables layered over global defaults."""

    region_parameters: Mapping[str, RegionParameters] = field(default_factory=dict)
    source_parameters: Mapping[str, Mapping[str, SourceParameters]] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        """Validate table keys and normalize mappings to immutable-friendly dicts."""
        normalized_regions: dict[str, RegionParameters] = {}
        for region, region_parameters in self.region_parameters.items():
            if not region:
                raise ValueError("region parameter names must be non-empty")
            normalized_regions[region] = region_parameters

        normalized_sources: dict[str, dict[str, SourceParameters]] = {}
        for region, source_table in self.source_parameters.items():
            if not region:
                raise ValueError("source parameter region names must be non-empty")
            normalized_sources[region] = {}
            for source, source_parameters in source_table.items():
                if not source:
                    raise ValueError("source parameter names must be non-empty")
                normalized_sources[region][source] = source_parameters

        object.__setattr__(self, "region_parameters", normalized_regions)
        object.__setattr__(self, "source_parameters", normalized_sources)

    def parameters_for_region(
        self, parameters: SimulationParameters, region: str
    ) -> SimulationParameters:
        """Return global parameters with any region override applied."""
        region_parameters = self.region_parameters.get(region)
        if region_parameters is None:
            return parameters
        return region_parameters.apply(parameters)

    def source_for(
        self, parameters: SimulationParameters, *, region: str, source: str
    ) -> ResolvedSourceParameters:
        """Return concrete source parameters for a region/source pair."""
        defaults = _default_source_parameters(parameters, source)
        overrides = self.source_parameters.get(region, {}).get(source)
        if overrides is None:
            return defaults
        return ResolvedSourceParameters(
            fertility_rate=(
                defaults.fertility_rate
                if overrides.fertility_rate is None
                else overrides.fertility_rate
            ),
            mortality_rate=(
                defaults.mortality_rate
                if overrides.mortality_rate is None
                else overrides.mortality_rate
            ),
            epidemic_risk=(
                defaults.epidemic_risk
                if overrides.epidemic_risk is None
                else overrides.epidemic_risk
            ),
            reproductive_multiplier=(
                defaults.reproductive_multiplier
                if overrides.reproductive_multiplier is None
                else overrides.reproductive_multiplier
            ),
        )


def _default_source_parameters(
    parameters: SimulationParameters, source: str
) -> ResolvedSourceParameters:
    """Return source defaults derived from the global parameter bundle."""
    if source == STEPPE_SOURCE:
        return ResolvedSourceParameters(
            fertility_rate=parameters.fertility_rate,
            mortality_rate=parameters.steppe_mortality_rate,
            epidemic_risk=parameters.steppe_epidemic_risk,
            reproductive_multiplier=parameters.elite_reproductive_advantage,
        )
    if source == LOCAL_SOURCE:
        return ResolvedSourceParameters(
            fertility_rate=parameters.fertility_rate,
            mortality_rate=parameters.local_mortality_rate,
            epidemic_risk=parameters.local_epidemic_risk,
            reproductive_multiplier=1.0,
        )
    return ResolvedSourceParameters(
        fertility_rate=parameters.fertility_rate,
        mortality_rate=parameters.local_mortality_rate,
        epidemic_risk=parameters.local_epidemic_risk,
        reproductive_multiplier=1.0,
    )
