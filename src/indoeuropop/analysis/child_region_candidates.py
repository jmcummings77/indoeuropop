"""Child-region structural candidate comparison helpers."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class ChildRegionCandidate:
    """A target-aligned child-region override candidate.

    The candidate describes a structured-model hypothesis rather than a
    historical claim. Counts summarize the breadth of the override file so
    reports can distinguish a narrow target-specific adjustment from a broad
    regional rewrite.
    """

    name: str
    override_path: str = ""
    overridden_region_count: int = 0
    migration_pulse_count: int = 0

    def __post_init__(self) -> None:
        """Validate and normalize candidate identity and counts."""
        normalized_name = self.name.strip()
        normalized_path = self.override_path.strip()
        if not normalized_name:
            raise ValueError("name must be non-empty")
        if self.overridden_region_count < 0:
            raise ValueError("overridden_region_count must be non-negative")
        if self.migration_pulse_count < 0:
            raise ValueError("migration_pulse_count must be non-negative")
        object.__setattr__(self, "name", normalized_name)
        object.__setattr__(self, "override_path", normalized_path)


@dataclass(frozen=True)
class StructuralComparisonReference:
    """Reference structural comparison deltas from another candidate run."""

    name: str
    root_mean_squared_error_delta: float
    coverage_rate_delta: float
    focus_residual_delta: float

    def __post_init__(self) -> None:
        """Validate reference labels and finite metric deltas."""
        normalized_name = self.name.strip()
        if not normalized_name:
            raise ValueError("name must be non-empty")
        values = (
            self.root_mean_squared_error_delta,
            self.coverage_rate_delta,
            self.focus_residual_delta,
        )
        if any(not isfinite(value) for value in values):
            raise ValueError("reference metric deltas must be finite")
        object.__setattr__(self, "name", normalized_name)


def root_mean_squared_error_advantage(
    candidate_delta: float,
    reference: StructuralComparisonReference,
) -> float:
    """Return child-candidate RMSE delta minus reference RMSE delta.

    Negative values mean the child-region candidate improved RMSE more than the
    reference did relative to its own baseline. This is a diagnostic comparison
    rather than a likelihood ratio, especially when the baselines differ.
    """
    if not isfinite(candidate_delta):
        raise ValueError("candidate_delta must be finite")
    return candidate_delta - reference.root_mean_squared_error_delta
