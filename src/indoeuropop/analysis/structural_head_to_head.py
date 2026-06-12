"""Helpers for same-baseline structural candidate comparisons."""

from __future__ import annotations

from dataclasses import dataclass, replace

from indoeuropop.orchestration.sweeps import SweepSpec
from indoeuropop.simulation.events import STEPPE_SOURCE, MigrationPulse


@dataclass(frozen=True)
class StructuredPulseCandidate:
    """A migration pulse copied across structured child regions."""

    name: str
    region_prefix: str
    start_bce: float
    end_bce: float
    annual_rate: float
    source: str = STEPPE_SOURCE

    def __post_init__(self) -> None:
        """Validate identity fields and pulse parameters."""
        normalized_name = self.name.strip()
        normalized_prefix = self.region_prefix.strip()
        if not normalized_name:
            raise ValueError("name must be non-empty")
        if not normalized_prefix:
            raise ValueError("region_prefix must be non-empty")
        pulse = MigrationPulse(
            region=normalized_prefix,
            start_bce=self.start_bce,
            end_bce=self.end_bce,
            annual_rate=self.annual_rate,
            source=self.source,
        )
        object.__setattr__(self, "name", normalized_name)
        object.__setattr__(self, "region_prefix", normalized_prefix)
        object.__setattr__(self, "start_bce", pulse.start_bce)
        object.__setattr__(self, "end_bce", pulse.end_bce)
        object.__setattr__(self, "annual_rate", pulse.annual_rate)

    def pulse_for_region(self, region: str) -> MigrationPulse:
        """Return this structured candidate as a pulse for one child region."""
        return MigrationPulse(
            region=region,
            start_bce=self.start_bce,
            end_bce=self.end_bce,
            annual_rate=self.annual_rate,
            source=self.source,
        )


def structured_pulse_regions(
    spec: SweepSpec,
    candidate: StructuredPulseCandidate,
) -> tuple[str, ...]:
    """Return modeled regions targeted by a structured pulse candidate."""
    regions = tuple(
        region
        for region in spec.initial_state.regions()
        if region.startswith(candidate.region_prefix)
    )
    if not regions:
        raise ValueError(
            "structured pulse region prefix matched no modeled regions: "
            f"{candidate.region_prefix}"
        )
    return regions


def apply_structured_pulse_candidate(
    spec: SweepSpec,
    candidate: StructuredPulseCandidate,
) -> SweepSpec:
    """Return a sweep spec with a structured broad-pulse candidate appended."""
    pulses = tuple(
        candidate.pulse_for_region(region)
        for region in structured_pulse_regions(spec, candidate)
    )
    return replace(
        spec,
        schedule=replace(
            spec.schedule,
            migration_pulses=(*spec.schedule.migration_pulses, *pulses),
        ),
    )


def better_root_mean_squared_error_delta(
    left_delta: float,
    right_delta: float,
) -> str:
    """Return which candidate has the stronger RMSE improvement signal."""
    if left_delta < right_delta:
        return "left"
    if right_delta < left_delta:
        return "right"
    return "tie"
