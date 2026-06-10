"""Age-structured population helpers for model expansion experiments."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite

from indoeuropop.models import PopulationState

JUVENILE = "juvenile"
ADULT = "adult"
ELDER = "elder"
AGE_CLASSES = (JUVENILE, ADULT, ELDER)

AgeCounts = dict[str, dict[str, dict[str, float]]]


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
class AgeStructuredState:
    """Population counts indexed by region, source, and age class."""

    counts: Mapping[str, Mapping[str, Mapping[str, float]]]

    def __post_init__(self) -> None:
        """Validate and normalize nested age-count mappings."""
        if not self.counts:
            raise ValueError("counts must contain at least one region")

        normalized: AgeCounts = {}
        for region, source_counts in self.counts.items():
            if not region:
                raise ValueError("region names must be non-empty")
            if not source_counts:
                raise ValueError(f"{region} must contain at least one source")
            normalized[region] = {}
            for source, age_counts in source_counts.items():
                if not source:
                    raise ValueError("source names must be non-empty")
                if not age_counts:
                    raise ValueError(f"{region}/{source} must contain age counts")
                normalized[region][source] = _normalized_age_counts(
                    region, source, age_counts
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
        age_class: str | None = None,
    ) -> float:
        """Return total counts filtered by optional region, source, and age class."""
        total = 0.0
        for region_name, source_counts in self.counts.items():
            if region is not None and region_name != region:
                continue
            for source_name, age_counts in source_counts.items():
                if source is not None and source_name != source:
                    continue
                if age_class is None:
                    total += sum(age_counts.values())
                else:
                    total += age_counts.get(age_class, 0.0)
        return total

    def ancestry_proportion(self, source: str, region: str | None = None) -> float:
        """Return source ancestry after summing across age classes."""
        denominator = self.total(region=region)
        if denominator == 0:
            return 0.0
        return self.total(region=region, source=source) / denominator

    def to_population_state(self) -> PopulationState:
        """Collapse age classes into the existing source-count state."""
        return PopulationState(
            {
                region: {
                    source: sum(age_counts.values())
                    for source, age_counts in source_counts.items()
                }
                for region, source_counts in self.counts.items()
            }
        )


@dataclass(frozen=True)
class AgeStructureParameters:
    """Deterministic age-transition parameters for one projection step."""

    annual_birth_rate: float = 0.035
    juvenile_mortality_rate: float = 0.040
    adult_mortality_rate: float = 0.030
    elder_mortality_rate: float = 0.080
    juvenile_maturation_rate: float = 0.050
    adult_aging_rate: float = 0.025

    def __post_init__(self) -> None:
        """Validate age-transition rates."""
        object.__setattr__(
            self,
            "annual_birth_rate",
            _require_finite_non_negative("annual_birth_rate", self.annual_birth_rate),
        )
        for field_name in (
            "juvenile_mortality_rate",
            "adult_mortality_rate",
            "elder_mortality_rate",
            "juvenile_maturation_rate",
            "adult_aging_rate",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_probability(field_name, getattr(self, field_name)),
            )


def advance_age_structure(
    state: AgeStructuredState,
    parameters: AgeStructureParameters,
    *,
    years: float,
) -> AgeStructuredState:
    """Advance an age-structured state by one deterministic time step."""
    step_years = _require_finite_non_negative("years", years)
    next_counts: AgeCounts = {}
    for region, source_counts in state.counts.items():
        next_counts[region] = {}
        for source, age_counts in source_counts.items():
            next_counts[region][source] = _advance_age_counts(
                age_counts, parameters, step_years
            )
    return AgeStructuredState(next_counts)


def _normalized_age_counts(
    region: str, source: str, age_counts: Mapping[str, float]
) -> dict[str, float]:
    """Return age counts with missing standard classes filled with zeros."""
    normalized = {
        age_class: _require_finite_non_negative(
            f"counts[{region!r}][{source!r}][{age_class!r}]",
            age_counts.get(age_class, 0.0),
        )
        for age_class in AGE_CLASSES
    }
    unknown_classes = set(age_counts).difference(AGE_CLASSES)
    if unknown_classes:
        unknown_text = ", ".join(sorted(unknown_classes))
        raise ValueError(f"unsupported age classes: {unknown_text}")
    return normalized


def _advance_age_counts(
    age_counts: Mapping[str, float],
    parameters: AgeStructureParameters,
    years: float,
) -> dict[str, float]:
    """Return one source's age counts after births, deaths, and transitions."""
    juvenile = age_counts[JUVENILE]
    adult = age_counts[ADULT]
    elder = age_counts[ELDER]

    juvenile_survivors = _survivors(juvenile, parameters.juvenile_mortality_rate, years)
    adult_survivors = _survivors(adult, parameters.adult_mortality_rate, years)
    elder_survivors = _survivors(elder, parameters.elder_mortality_rate, years)
    births = adult * parameters.annual_birth_rate * years
    matured = _transition_count(
        juvenile_survivors, parameters.juvenile_maturation_rate, years
    )
    aged = _transition_count(adult_survivors, parameters.adult_aging_rate, years)

    return {
        JUVENILE: juvenile_survivors - matured + births,
        ADULT: adult_survivors - aged + matured,
        ELDER: elder_survivors + aged,
    }


def _survivors(count: float, mortality_rate: float, years: float) -> float:
    """Return surviving count after a capped deterministic mortality step."""
    deaths = count * min(1.0, mortality_rate * years)
    return max(0.0, count - deaths)


def _transition_count(count: float, annual_rate: float, years: float) -> float:
    """Return count transitioning to the next age class."""
    return min(count, count * annual_rate * years)
