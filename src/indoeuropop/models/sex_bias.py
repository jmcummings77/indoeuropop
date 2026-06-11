"""Sex-structured reproduction helpers for model expansion experiments."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite

from indoeuropop.models import PopulationState

FEMALE = "female"
MALE = "male"
SEXES = (FEMALE, MALE)

SexCounts = dict[str, dict[str, dict[str, float]]]


def _require_finite_non_negative(name: str, value: float) -> float:
    """Return a numeric value after validating it is finite and non-negative."""
    numeric_value = float(value)
    if not isfinite(numeric_value) or numeric_value < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return numeric_value


def _require_probability(name: str, value: float) -> float:
    """Return a numeric value after validating it is a probability."""
    numeric_value = _require_finite_non_negative(name, value)
    if numeric_value > 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return numeric_value


@dataclass(frozen=True)
class SexStructuredState:
    """Population counts indexed by region, source, and binary sex label.

    The labels are demographic bookkeeping labels for this scaffold. They do
    not imply that later ancient-DNA metadata will always contain confident sex
    calls, nor do they represent social gender categories.
    """

    counts: Mapping[str, Mapping[str, Mapping[str, float]]]

    def __post_init__(self) -> None:
        """Validate and normalize nested sex-count mappings."""
        if not self.counts:
            raise ValueError("counts must contain at least one region")

        normalized: SexCounts = {}
        for region, source_counts in self.counts.items():
            if not region:
                raise ValueError("region names must be non-empty")
            if not source_counts:
                raise ValueError(f"{region} must contain at least one source")
            normalized[region] = {}
            for source, sex_counts in source_counts.items():
                if not source:
                    raise ValueError("source names must be non-empty")
                if not sex_counts:
                    raise ValueError(f"{region}/{source} must contain sex counts")
                normalized[region][source] = _normalized_sex_counts(
                    region, source, sex_counts
                )

        object.__setattr__(self, "counts", normalized)

    def regions(self) -> tuple[str, ...]:
        """Return region labels in deterministic insertion order."""
        return tuple(self.counts)

    def sources(self, region: str | None = None) -> tuple[str, ...]:
        """Return source labels for one region or all regions."""
        if region is not None:
            return tuple(self.counts[region])

        sources: list[str] = []
        for source_counts in self.counts.values():
            for source in source_counts:
                if source not in sources:
                    sources.append(source)
        return tuple(sources)

    def total(
        self,
        *,
        region: str | None = None,
        source: str | None = None,
        sex: str | None = None,
    ) -> float:
        """Return total counts filtered by optional region, source, and sex."""
        if sex is not None and sex not in SEXES:
            raise ValueError("sex label is not supported")

        total = 0.0
        for region_name, source_counts in self.counts.items():
            if region is not None and region_name != region:
                continue
            for source_name, sex_counts in source_counts.items():
                if source is not None and source_name != source:
                    continue
                if sex is None:
                    total += sum(sex_counts.values())
                else:
                    total += sex_counts.get(sex, 0.0)
        return total

    def source_proportion_by_sex(
        self, source: str, sex: str, region: str | None = None
    ) -> float:
        """Return a source proportion after filtering to one sex label."""
        if sex not in SEXES:
            raise ValueError("sex label is not supported")

        denominator = self.total(region=region, sex=sex)
        if denominator == 0:
            return 0.0
        return self.total(region=region, source=source, sex=sex) / denominator

    def to_population_state(self) -> PopulationState:
        """Collapse sex labels into the existing source-count state."""
        return PopulationState(
            {
                region: {
                    source: sum(sex_counts.values())
                    for source, sex_counts in source_counts.items()
                }
                for region, source_counts in self.counts.items()
            }
        )


@dataclass(frozen=True)
class SexBiasParameters:
    """Parameters for expected sex-biased autosomal birth contributions."""

    annual_birth_rate: float = 0.035
    maternal_autosomal_share: float = 0.5
    female_reproductive_multipliers: Mapping[str, float] = field(default_factory=dict)
    male_reproductive_multipliers: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate rates, inheritance share, and source multipliers."""
        object.__setattr__(
            self,
            "annual_birth_rate",
            _require_finite_non_negative("annual_birth_rate", self.annual_birth_rate),
        )
        object.__setattr__(
            self,
            "maternal_autosomal_share",
            _require_probability(
                "maternal_autosomal_share", self.maternal_autosomal_share
            ),
        )
        object.__setattr__(
            self,
            "female_reproductive_multipliers",
            _normalized_multiplier_map(
                "female_reproductive_multipliers",
                self.female_reproductive_multipliers,
            ),
        )
        object.__setattr__(
            self,
            "male_reproductive_multipliers",
            _normalized_multiplier_map(
                "male_reproductive_multipliers",
                self.male_reproductive_multipliers,
            ),
        )


def expected_births_by_source(
    state: SexStructuredState,
    parameters: SexBiasParameters,
    *,
    years: float,
    region: str | None = None,
) -> PopulationState:
    """Estimate newborn source contributions from sex-specific weights.

    This is a deterministic expectation, not a pedigree simulation. It uses
    female reproductive weight to set the total number of births and blends
    source contributions using the maternal and paternal autosomal shares.
    """
    step_years = _require_finite_non_negative("years", years)
    regions = _selected_regions(state, region)
    birth_counts: dict[str, dict[str, float]] = {}

    for region_name in regions:
        source_counts = state.counts[region_name]
        female_weights = _reproductive_weights(
            source_counts, FEMALE, parameters.female_reproductive_multipliers
        )
        male_weights = _reproductive_weights(
            source_counts, MALE, parameters.male_reproductive_multipliers
        )
        female_total = sum(female_weights.values())
        male_total = sum(male_weights.values())
        birth_counts[region_name] = _expected_region_births(
            source_counts=source_counts,
            female_weights=female_weights,
            male_weights=male_weights,
            female_total=female_total,
            male_total=male_total,
            parameters=parameters,
            years=step_years,
        )

    return PopulationState(birth_counts)


def _normalized_sex_counts(
    region: str, source: str, sex_counts: Mapping[str, float]
) -> dict[str, float]:
    """Return sex counts with missing standard labels filled with zeros."""
    normalized = {
        sex: _require_finite_non_negative(
            f"counts[{region!r}][{source!r}][{sex!r}]",
            sex_counts.get(sex, 0.0),
        )
        for sex in SEXES
    }
    unknown_sexes = set(sex_counts).difference(SEXES)
    if unknown_sexes:
        unknown_text = ", ".join(sorted(unknown_sexes))
        raise ValueError(f"unsupported sex labels: {unknown_text}")
    return normalized


def _normalized_multiplier_map(
    name: str, multipliers: Mapping[str, float]
) -> dict[str, float]:
    """Return validated source-specific reproductive multipliers."""
    normalized: dict[str, float] = {}
    for source, value in multipliers.items():
        if not source:
            raise ValueError(f"{name} source names must be non-empty")
        normalized[source] = _require_finite_non_negative(f"{name}[{source!r}]", value)
    return normalized


def _selected_regions(state: SexStructuredState, region: str | None) -> tuple[str, ...]:
    """Return the regions that should be included in a birth projection."""
    if region is None:
        return state.regions()
    if region not in state.counts:
        raise KeyError(region)
    return (region,)


def _reproductive_weights(
    source_counts: Mapping[str, Mapping[str, float]],
    sex: str,
    multipliers: Mapping[str, float],
) -> dict[str, float]:
    """Return reproductive weights for one sex across sources."""
    return {
        source: sex_counts[sex] * multipliers.get(source, 1.0)
        for source, sex_counts in source_counts.items()
    }


def _expected_region_births(
    *,
    source_counts: Mapping[str, Mapping[str, float]],
    female_weights: Mapping[str, float],
    male_weights: Mapping[str, float],
    female_total: float,
    male_total: float,
    parameters: SexBiasParameters,
    years: float,
) -> dict[str, float]:
    """Return expected newborn source counts for one region."""
    if female_total == 0 or male_total == 0:
        return dict.fromkeys(source_counts, 0.0)

    birth_total = female_total * parameters.annual_birth_rate * years
    maternal_share = parameters.maternal_autosomal_share
    paternal_share = 1.0 - maternal_share

    return {
        source: birth_total
        * (
            maternal_share * female_weights[source] / female_total
            + paternal_share * male_weights[source] / male_total
        )
        for source in source_counts
    }
