"""Shared models for multi-fold structural SMC validation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from math import isfinite
from pathlib import Path

from indoeuropop.orchestration.experiments import (
    ExperimentArtifact,
    ExperimentManifest,
)
from indoeuropop.orchestration.structural_smc_outputs import (
    StructuralSMCComparisonResult,
)

DEFAULT_STRUCTURAL_SMC_CHRONOLOGY_WINDOWS: tuple[tuple[str, float, float], ...] = (
    ("early_steppe_transition_3000_2500_bce", 3000.0, 2500.0),
    ("middle_beaker_transition_2500_2300_bce", 2500.0, 2300.0),
    ("late_beaker_transition_2300_1900_bce", 2300.0, 1900.0),
)


@dataclass(frozen=True)
class StructuralSMCValidationFoldSpec:
    """One pre-registered holdout fold for structural SMC validation."""

    name: str
    categories: tuple[str, ...]
    holdout_field: str = "region"
    holdout_value: str = ""
    start_bce: float | None = None
    end_bce: float | None = None
    description: str = ""

    def __post_init__(self) -> None:
        """Normalize fold labels and validate field or time-window mode."""
        name = structural_smc_validation_slug(self.name)
        categories = tuple(_unique(value.strip() for value in self.categories))
        field = self.holdout_field.strip()
        value = self.holdout_value.strip()
        if not name:
            raise ValueError("fold name must be non-empty")
        if not categories:
            raise ValueError("fold categories must contain at least one value")
        if self.is_time_window:
            if not _valid_time_window(self.start_bce, self.end_bce):
                raise ValueError("time-window folds require start_bce >= end_bce")
        elif not field or not value:
            raise ValueError("field folds require holdout_field and holdout_value")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "categories", categories)
        object.__setattr__(self, "holdout_field", field)
        object.__setattr__(self, "holdout_value", value)
        object.__setattr__(self, "description", self.description.strip())

    @property
    def is_time_window(self) -> bool:
        """Return whether this fold holds out a BCE time interval."""
        return self.start_bce is not None or self.end_bce is not None

    @property
    def category_text(self) -> str:
        """Return comma-separated category labels for reports."""
        return ",".join(self.categories)


@dataclass(frozen=True)
class StructuralSMCValidationFoldResult:
    """Result from running one structural SMC validation fold."""

    spec: StructuralSMCValidationFoldSpec
    calibration_target_count: int
    holdout_target_count: int
    comparison: StructuralSMCComparisonResult

    @property
    def calibration_preferred_candidate(self) -> str:
        """Return the calibration-preferred structural candidate label."""
        return structural_smc_preferred_candidate(
            self.comparison.child_minus_structured_pulse_rmse_delta
        )

    @property
    def holdout_preferred_candidate(self) -> str:
        """Return the holdout-preferred structural candidate label."""
        delta = self.comparison.child_minus_structured_pulse_holdout_rmse_delta
        assert delta is not None
        return structural_smc_preferred_candidate(delta)

    @property
    def has_preference_disagreement(self) -> bool:
        """Return whether calibration and holdout choose different candidates."""
        return self.calibration_preferred_candidate != self.holdout_preferred_candidate


@dataclass(frozen=True)
class StructuralSMCValidationOutputPaths:
    """Input and output paths for a multi-fold structural SMC validation run."""

    output_dir: Path | None = None
    config: Path | None = None
    targets: Path | None = None
    child_region_overrides: Path | None = None
    summary_csv: Path | None = None
    report_md: Path | None = None
    manifest_json: Path | None = None


@dataclass(frozen=True)
class StructuralSMCMultiFoldValidationResult:
    """Aggregate result from several structural SMC validation folds."""

    folds: tuple[StructuralSMCValidationFoldResult, ...]
    artifacts: tuple[ExperimentArtifact, ...] = ()
    manifest: ExperimentManifest | None = None
    summary_csv_path: Path | None = None
    report_md_path: Path | None = None
    manifest_json_path: Path | None = None

    def __post_init__(self) -> None:
        """Require at least one completed fold."""
        if not self.folds:
            raise ValueError("structural SMC validation requires at least one fold")

    @property
    def preference_disagreement_count(self) -> int:
        """Return the number of folds with calibration-holdout disagreement."""
        return sum(fold.has_preference_disagreement for fold in self.folds)


def structural_smc_preferred_candidate(child_minus_pulse_delta: float) -> str:
    """Return the preferred candidate from child-minus-pulse RMSE delta."""
    if child_minus_pulse_delta < 0:
        return "child_override"
    if child_minus_pulse_delta > 0:
        return "structured_pulse"
    return "tie"


def merge_structural_smc_validation_folds(
    folds: Iterable[StructuralSMCValidationFoldSpec],
) -> tuple[StructuralSMCValidationFoldSpec, ...]:
    """Merge duplicate folds while preserving category annotations."""
    merged: dict[tuple[object, ...], StructuralSMCValidationFoldSpec] = {}
    for fold in folds:
        key = _fold_key(fold)
        existing = merged.get(key)
        if existing is None:
            merged[key] = fold
        else:
            merged[key] = replace(
                existing,
                categories=tuple(_unique((*existing.categories, *fold.categories))),
            )
    return tuple(merged.values())


def structural_smc_validation_slug(value: str) -> str:
    """Return a filesystem-friendly lowercase fold label."""
    return "_".join(value.strip().lower().replace("-", "_").split())


def _fold_key(fold: StructuralSMCValidationFoldSpec) -> tuple[object, ...]:
    """Return a stable key for deduplicating validation folds."""
    if fold.is_time_window:
        return ("time_window", fold.start_bce, fold.end_bce)
    return ("field", fold.holdout_field, fold.holdout_value)


def _valid_time_window(start_bce: float | None, end_bce: float | None) -> bool:
    """Return whether BCE window endpoints are finite and ordered."""
    return (
        start_bce is not None
        and end_bce is not None
        and isfinite(start_bce)
        and isfinite(end_bce)
        and start_bce >= end_bce
    )


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    """Return unique non-empty values while preserving order."""
    unique_values: list[str] = []
    for value in values:
        if value and value not in unique_values:
            unique_values.append(value)
    return tuple(unique_values)
