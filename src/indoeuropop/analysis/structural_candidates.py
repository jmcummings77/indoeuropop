"""Model-structure candidate helpers for targeted diagnostic comparisons."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite

from indoeuropop.analysis.posterior_predictive import PosteriorPredictiveDiagnostics
from indoeuropop.orchestration.sweeps import SweepSpec
from indoeuropop.simulation.events import (
    STEPPE_SOURCE,
    MigrationPulse,
)


@dataclass(frozen=True)
class MigrationPulseCandidate:
    """A time-localized migration pulse candidate added to a sweep spec."""

    name: str
    region: str
    start_bce: float
    end_bce: float
    annual_rate: float
    source: str = STEPPE_SOURCE

    def __post_init__(self) -> None:
        """Validate identity fields and pulse parameters."""
        normalized_name = self.name.strip()
        normalized_region = self.region.strip()
        if not normalized_name:
            raise ValueError("name must be non-empty")
        if not normalized_region:
            raise ValueError("region must be non-empty")
        pulse = MigrationPulse(
            region=normalized_region,
            start_bce=self.start_bce,
            end_bce=self.end_bce,
            annual_rate=self.annual_rate,
            source=self.source,
        )
        object.__setattr__(self, "name", normalized_name)
        object.__setattr__(self, "region", normalized_region)
        object.__setattr__(self, "start_bce", pulse.start_bce)
        object.__setattr__(self, "end_bce", pulse.end_bce)
        object.__setattr__(self, "annual_rate", pulse.annual_rate)

    def pulse(self) -> MigrationPulse:
        """Return this candidate as a simulation migration pulse."""
        return MigrationPulse(
            region=self.region,
            start_bce=self.start_bce,
            end_bce=self.end_bce,
            annual_rate=self.annual_rate,
            source=self.source,
        )


@dataclass(frozen=True)
class PosteriorPredictiveMetricDelta:
    """Candidate-minus-baseline posterior predictive metric changes."""

    baseline_label: str
    candidate_label: str
    coverage_rate_delta: float
    mean_absolute_error_delta: float
    root_mean_squared_error_delta: float
    max_abs_z_score_delta: float
    focus_observation_index: int
    focus_residual_delta: float

    def __post_init__(self) -> None:
        """Validate labels, finite deltas, and focus observation index."""
        if not self.baseline_label:
            raise ValueError("baseline_label must be non-empty")
        if not self.candidate_label:
            raise ValueError("candidate_label must be non-empty")
        if self.focus_observation_index < 0:
            raise ValueError("focus_observation_index must be non-negative")
        values = (
            self.coverage_rate_delta,
            self.mean_absolute_error_delta,
            self.root_mean_squared_error_delta,
            self.max_abs_z_score_delta,
            self.focus_residual_delta,
        )
        if any(not isfinite(value) for value in values):
            raise ValueError("metric deltas must be finite")

    @property
    def improves_root_mean_squared_error(self) -> bool:
        """Return whether the candidate lowered posterior predictive RMSE."""
        return self.root_mean_squared_error_delta < 0

    @property
    def improves_focus_residual(self) -> bool:
        """Return whether the candidate lowered absolute focus residual."""
        return self.focus_residual_delta < 0


def apply_migration_pulse_candidate(
    spec: SweepSpec,
    candidate: MigrationPulseCandidate,
) -> SweepSpec:
    """Return a sweep spec with a candidate migration pulse appended."""
    known_regions = set(spec.initial_state.regions())
    if candidate.region not in known_regions:
        raise ValueError(
            f"candidate region is not in the sweep spec: {candidate.region}"
        )
    return replace(
        spec,
        schedule=replace(
            spec.schedule,
            migration_pulses=(*spec.schedule.migration_pulses, candidate.pulse()),
        ),
    )


def posterior_predictive_metric_delta(
    baseline: PosteriorPredictiveDiagnostics,
    candidate: PosteriorPredictiveDiagnostics,
    *,
    baseline_label: str = "baseline",
    candidate_label: str = "candidate",
    focus_observation_index: int | None = None,
) -> PosteriorPredictiveMetricDelta:
    """Return aggregate and focus-row candidate-minus-baseline deltas."""
    if baseline.observation_count != candidate.observation_count:
        raise ValueError("diagnostics must have the same observation count")
    focus_index = (
        baseline.worst_observation.observation_index
        if focus_observation_index is None
        else focus_observation_index
    )
    if focus_index >= baseline.observation_count:
        raise ValueError("focus_observation_index is outside diagnostics")
    baseline_focus = baseline.observations[focus_index]
    candidate_focus = candidate.observations[focus_index]
    return PosteriorPredictiveMetricDelta(
        baseline_label=baseline_label,
        candidate_label=candidate_label,
        coverage_rate_delta=candidate.coverage_rate - baseline.coverage_rate,
        mean_absolute_error_delta=(
            candidate.mean_absolute_error - baseline.mean_absolute_error
        ),
        root_mean_squared_error_delta=(
            candidate.root_mean_squared_error - baseline.root_mean_squared_error
        ),
        max_abs_z_score_delta=candidate.max_abs_z_score - baseline.max_abs_z_score,
        focus_observation_index=focus_index,
        focus_residual_delta=(
            candidate_focus.absolute_mean_residual
            - baseline_focus.absolute_mean_residual
        ),
    )
