"""Compartmental epidemic helpers for model expansion experiments."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite

from indoeuropop.models import PopulationState

SUSCEPTIBLE = "susceptible"
INFECTED = "infected"
RECOVERED = "recovered"
DECEASED = "deceased"
EPIDEMIC_COMPARTMENTS = (SUSCEPTIBLE, INFECTED, RECOVERED, DECEASED)
LIVING_COMPARTMENTS = (SUSCEPTIBLE, INFECTED, RECOVERED)

EpidemicCounts = dict[str, dict[str, dict[str, float]]]


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
class EpidemicState:
    """Population counts indexed by region, source, and epidemic compartment."""

    counts: Mapping[str, Mapping[str, Mapping[str, float]]]

    def __post_init__(self) -> None:
        """Validate and normalize nested epidemic-count mappings."""
        if not self.counts:
            raise ValueError("counts must contain at least one region")

        normalized: EpidemicCounts = {}
        for region, source_counts in self.counts.items():
            if not region:
                raise ValueError("region names must be non-empty")
            if not source_counts:
                raise ValueError(f"{region} must contain at least one source")
            normalized[region] = {}
            for source, compartment_counts in source_counts.items():
                if not source:
                    raise ValueError("source names must be non-empty")
                if not compartment_counts:
                    raise ValueError(
                        f"{region}/{source} must contain compartment counts"
                    )
                normalized[region][source] = _normalized_compartment_counts(
                    region, source, compartment_counts
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
        compartment: str | None = None,
        living_only: bool = False,
    ) -> float:
        """Return total counts filtered by region, source, or compartment."""
        if compartment is not None and compartment not in EPIDEMIC_COMPARTMENTS:
            raise ValueError("compartment label is not supported")

        total = 0.0
        for region_name, source_counts in self.counts.items():
            if region is not None and region_name != region:
                continue
            for source_name, compartment_counts in source_counts.items():
                if source is not None and source_name != source:
                    continue
                if compartment is not None:
                    total += compartment_counts.get(compartment, 0.0)
                elif living_only:
                    total += sum(
                        compartment_counts[label] for label in LIVING_COMPARTMENTS
                    )
                else:
                    total += sum(compartment_counts.values())
        return total

    def infection_prevalence(
        self, *, region: str | None = None, source: str | None = None
    ) -> float:
        """Return infected share among living people for a filtered population."""
        denominator = self.total(region=region, source=source, living_only=True)
        if denominator == 0:
            return 0.0
        return (
            self.total(region=region, source=source, compartment=INFECTED) / denominator
        )

    def to_population_state(self, *, include_deceased: bool = False) -> PopulationState:
        """Collapse compartments into source counts for existing model helpers."""
        compartments = (
            EPIDEMIC_COMPARTMENTS if include_deceased else LIVING_COMPARTMENTS
        )
        return PopulationState(
            {
                region: {
                    source: sum(compartment_counts[label] for label in compartments)
                    for source, compartment_counts in source_counts.items()
                }
                for region, source_counts in self.counts.items()
            }
        )


@dataclass(frozen=True)
class EpidemicParameters:
    """Deterministic parameters for one compartmental epidemic projection."""

    transmission_rate: float = 0.0
    recovery_rate: float = 0.0
    disease_mortality_rate: float = 0.0
    background_mortality_rate: float = 0.0
    source_susceptibility: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate transmission, recovery, mortality, and susceptibility fields."""
        object.__setattr__(
            self,
            "transmission_rate",
            _require_finite_non_negative("transmission_rate", self.transmission_rate),
        )
        for field_name in (
            "recovery_rate",
            "disease_mortality_rate",
            "background_mortality_rate",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_probability(field_name, getattr(self, field_name)),
            )
        object.__setattr__(
            self,
            "source_susceptibility",
            _normalized_multiplier_map(
                "source_susceptibility", self.source_susceptibility
            ),
        )


def advance_epidemic(
    state: EpidemicState,
    parameters: EpidemicParameters,
    *,
    years: float,
) -> EpidemicState:
    """Advance an epidemic state by one deterministic transmission step."""
    step_years = _require_finite_non_negative("years", years)
    next_counts: EpidemicCounts = {}

    for region, source_counts in state.counts.items():
        living_total = state.total(region=region, living_only=True)
        infected_total = state.total(region=region, compartment=INFECTED)
        force = _infection_force(parameters, infected_total, living_total)
        next_counts[region] = {}
        for source, compartment_counts in source_counts.items():
            next_counts[region][source] = _advance_source_compartments(
                compartment_counts=compartment_counts,
                susceptibility=parameters.source_susceptibility.get(source, 1.0),
                infection_force=force,
                parameters=parameters,
                years=step_years,
            )

    return EpidemicState(next_counts)


def _normalized_compartment_counts(
    region: str, source: str, compartment_counts: Mapping[str, float]
) -> dict[str, float]:
    """Return compartment counts with missing standard labels filled with zeros."""
    normalized = {
        compartment: _require_finite_non_negative(
            f"counts[{region!r}][{source!r}][{compartment!r}]",
            compartment_counts.get(compartment, 0.0),
        )
        for compartment in EPIDEMIC_COMPARTMENTS
    }
    unknown_compartments = set(compartment_counts).difference(EPIDEMIC_COMPARTMENTS)
    if unknown_compartments:
        unknown_text = ", ".join(sorted(unknown_compartments))
        raise ValueError(f"unsupported epidemic compartments: {unknown_text}")
    return normalized


def _normalized_multiplier_map(
    name: str, multipliers: Mapping[str, float]
) -> dict[str, float]:
    """Return validated source-specific susceptibility multipliers."""
    normalized: dict[str, float] = {}
    for source, value in multipliers.items():
        if not source:
            raise ValueError(f"{name} source names must be non-empty")
        normalized[source] = _require_finite_non_negative(f"{name}[{source!r}]", value)
    return normalized


def _infection_force(
    parameters: EpidemicParameters, infected_total: float, living_total: float
) -> float:
    """Return region-level infection force from infected and living totals."""
    if living_total == 0:
        return 0.0
    return parameters.transmission_rate * infected_total / living_total


def _advance_source_compartments(
    *,
    compartment_counts: Mapping[str, float],
    susceptibility: float,
    infection_force: float,
    parameters: EpidemicParameters,
    years: float,
) -> dict[str, float]:
    """Return one source's compartment counts after transmission and removals."""
    susceptible = compartment_counts[SUSCEPTIBLE]
    infected = compartment_counts[INFECTED]
    recovered = compartment_counts[RECOVERED]
    deceased = compartment_counts[DECEASED]

    background_rate = min(1.0, parameters.background_mortality_rate * years)
    susceptible_background_deaths = susceptible * background_rate
    infected_background_deaths = infected * background_rate
    recovered_background_deaths = recovered * background_rate

    susceptible_after_background = susceptible - susceptible_background_deaths
    infected_after_background = infected - infected_background_deaths
    recovered_after_background = recovered - recovered_background_deaths

    infection_rate = min(1.0, infection_force * susceptibility * years)
    new_infections = susceptible_after_background * infection_rate
    disease_removals = _disease_removals(infected_after_background, parameters, years)
    recoveries = _recovery_count(disease_removals, parameters)
    disease_deaths = disease_removals - recoveries

    return {
        SUSCEPTIBLE: susceptible_after_background - new_infections,
        INFECTED: infected_after_background + new_infections - disease_removals,
        RECOVERED: recovered_after_background + recoveries,
        DECEASED: (
            deceased
            + susceptible_background_deaths
            + infected_background_deaths
            + recovered_background_deaths
            + disease_deaths
        ),
    }


def _disease_removals(
    infected: float, parameters: EpidemicParameters, years: float
) -> float:
    """Return infected people removed by recovery or disease mortality."""
    removal_rate = parameters.recovery_rate + parameters.disease_mortality_rate
    return infected * min(1.0, removal_rate * years)


def _recovery_count(removals: float, parameters: EpidemicParameters) -> float:
    """Return the recovered share of infected removals."""
    removal_rate = parameters.recovery_rate + parameters.disease_mortality_rate
    if removal_rate == 0:
        return 0.0
    return removals * parameters.recovery_rate / removal_rate
