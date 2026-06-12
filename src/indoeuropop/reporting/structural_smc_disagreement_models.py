"""Models for structural SMC disagreement diagnostics."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite

from indoeuropop.data.targets import TargetObservation

STRUCTURAL_SMC_DISAGREEMENT_FIELDS = (
    "fold_name",
    "categories",
    "calibration_preferred_candidate",
    "holdout_preferred_candidate",
    "fold_holdout_child_minus_structured_pulse_rmse_delta",
    "target_index",
    "target_id",
    "requested_group_id",
    "matched_group_ids",
    "publication_keys",
    "sample_count",
    "window_bce",
    "aggregation_method",
    "group_match_mode",
    "region",
    "source",
    "time_bce",
    "observed_mean",
    "uncertainty",
    "citation_key",
    "citation",
    "baseline_prediction_mean",
    "baseline_mean_residual",
    "baseline_absolute_mean_residual",
    "structured_pulse_prediction_mean",
    "structured_pulse_mean_residual",
    "structured_pulse_absolute_mean_residual",
    "structured_pulse_observed_inside_interval",
    "child_override_prediction_mean",
    "child_override_mean_residual",
    "child_override_absolute_mean_residual",
    "child_override_observed_inside_interval",
    "child_minus_structured_pulse_prediction_delta",
    "child_minus_structured_pulse_abs_residual_delta",
    "target_preferred_candidate",
)

REQUIRED_VALIDATION_SUMMARY_COLUMNS = frozenset(
    (
        "fold_name",
        "categories",
        "calibration_preferred_candidate",
        "holdout_preferred_candidate",
        "preference_disagreement",
        "holdout_child_minus_structured_pulse_rmse_delta",
    )
)

REQUIRED_POSTERIOR_PREDICTIVE_COLUMNS = frozenset(
    (
        "observation_index",
        "prediction_mean",
        "mean_residual",
        "absolute_mean_residual",
        "observed_inside_interval",
    )
)


@dataclass(frozen=True)
class StructuralSMCDisagreementRow:
    """One held-out target row from a structural SMC disagreement fold."""

    fold_name: str
    categories: str
    calibration_preferred_candidate: str
    holdout_preferred_candidate: str
    fold_holdout_delta: float
    target_index: int
    target_id: str
    requested_group_id: str
    matched_group_ids: str
    publication_keys: str
    sample_count: int | None
    window_bce: str
    aggregation_method: str
    group_match_mode: str
    observation: TargetObservation
    baseline: Mapping[str, str]
    structured_pulse: Mapping[str, str]
    child_override: Mapping[str, str]

    def __post_init__(self) -> None:
        """Validate row identity, finite fold delta, and index values."""
        for field_name in (
            "fold_name",
            "calibration_preferred_candidate",
            "holdout_preferred_candidate",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must be non-empty")
        if self.target_index < 0:
            raise ValueError("target_index must be non-negative")
        if not isfinite(self.fold_holdout_delta):
            raise ValueError("fold_holdout_delta must be finite")
        if self.sample_count is not None and self.sample_count < 0:
            raise ValueError("sample_count must be non-negative when present")

    @property
    def baseline_prediction_mean(self) -> float:
        """Return baseline predictive mean for this held-out target."""
        return _float_cell(self.baseline, "prediction_mean")

    @property
    def baseline_mean_residual(self) -> float:
        """Return baseline mean residual for this held-out target."""
        return _float_cell(self.baseline, "mean_residual")

    @property
    def baseline_absolute_mean_residual(self) -> float:
        """Return baseline absolute mean residual for this held-out target."""
        return _float_cell(self.baseline, "absolute_mean_residual")

    @property
    def structured_pulse_prediction_mean(self) -> float:
        """Return structured-pulse predictive mean for this held-out target."""
        return _float_cell(self.structured_pulse, "prediction_mean")

    @property
    def structured_pulse_mean_residual(self) -> float:
        """Return structured-pulse mean residual for this held-out target."""
        return _float_cell(self.structured_pulse, "mean_residual")

    @property
    def structured_pulse_absolute_mean_residual(self) -> float:
        """Return structured-pulse absolute mean residual for this target."""
        return _float_cell(self.structured_pulse, "absolute_mean_residual")

    @property
    def child_override_prediction_mean(self) -> float:
        """Return child-override predictive mean for this held-out target."""
        return _float_cell(self.child_override, "prediction_mean")

    @property
    def child_override_mean_residual(self) -> float:
        """Return child-override mean residual for this held-out target."""
        return _float_cell(self.child_override, "mean_residual")

    @property
    def child_override_absolute_mean_residual(self) -> float:
        """Return child-override absolute mean residual for this target."""
        return _float_cell(self.child_override, "absolute_mean_residual")

    @property
    def child_minus_structured_pulse_prediction_delta(self) -> float:
        """Return child prediction minus structured-pulse prediction."""
        return (
            self.child_override_prediction_mean - self.structured_pulse_prediction_mean
        )

    @property
    def child_minus_structured_pulse_abs_residual_delta(self) -> float:
        """Return child absolute residual minus structured-pulse absolute residual."""
        return (
            self.child_override_absolute_mean_residual
            - self.structured_pulse_absolute_mean_residual
        )

    @property
    def target_preferred_candidate(self) -> str:
        """Return the candidate with lower absolute residual on this target."""
        delta = self.child_minus_structured_pulse_abs_residual_delta
        if delta < 0:
            return "child_override"
        if delta > 0:
            return "structured_pulse"
        return "tie"


@dataclass(frozen=True)
class StructuralSMCDisagreementReport:
    """Joined target and posterior-predictive diagnostics for disagreements."""

    rows: tuple[StructuralSMCDisagreementRow, ...]

    @property
    def disagreement_fold_count(self) -> int:
        """Return the number of disagreement folds represented by rows."""
        return len({row.fold_name for row in self.rows})

    @property
    def target_count(self) -> int:
        """Return the number of joined held-out target rows."""
        return len(self.rows)

    @property
    def structured_pulse_target_count(self) -> int:
        """Return target rows whose residual favors structured pulse."""
        return sum(
            row.target_preferred_candidate == "structured_pulse" for row in self.rows
        )

    @property
    def child_override_target_count(self) -> int:
        """Return target rows whose residual favors child override."""
        return sum(
            row.target_preferred_candidate == "child_override" for row in self.rows
        )

    @property
    def ranked_rows(self) -> tuple[StructuralSMCDisagreementRow, ...]:
        """Return rows sorted by strongest child-minus-pulse residual penalty."""
        return tuple(
            sorted(
                self.rows,
                key=lambda row: row.child_minus_structured_pulse_abs_residual_delta,
                reverse=True,
            )
        )


def required_cell(row: Mapping[str, str | None], column: str) -> str:
    """Return a non-empty CSV cell value."""
    value = row.get(column)
    if value is None or value.strip() == "":
        raise ValueError(f"{column} is required")
    return value.strip()


def _float_cell(row: Mapping[str, str], column: str) -> float:
    """Return a finite float from a CSV cell."""
    value = float(required_cell(row, column))
    if not isfinite(value):
        raise ValueError(f"{column} must be finite")
    return value
