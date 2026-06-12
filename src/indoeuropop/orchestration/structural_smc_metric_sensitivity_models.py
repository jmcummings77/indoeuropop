"""Models for structural SMC fit-metric sensitivity workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from indoeuropop.data.targets import TargetDataset
from indoeuropop.orchestration.structural_smc_validation_models import (
    StructuralSMCMultiFoldValidationResult,
    StructuralSMCValidationFoldSpec,
)
from indoeuropop.orchestration.target_fragility_models import TargetFragilityDecision
from indoeuropop.reporting.structural_smc_uncertainty import (
    StructuralSMCUncertaintyReport,
)

DEFAULT_STRUCTURAL_SMC_FIT_METRICS = ("root_mean_squared_error", "chi_square")


@dataclass(frozen=True)
class StructuralSMCFitMetricSensitivityPaths:
    """Filesystem paths for a fit-metric sensitivity run."""

    output_dir: Path
    filtered_targets_csv: Path
    decisions_csv: Path
    summary_csv: Path
    report_md: Path
    metrics_output_dir: Path


@dataclass(frozen=True)
class StructuralSMCFitMetricRunResult:
    """One structural SMC validation and uncertainty review under one metric."""

    fit_metric: str
    validation_result: StructuralSMCMultiFoldValidationResult
    uncertainty_report: StructuralSMCUncertaintyReport
    output_dir: Path
    uncertainty_csv_path: Path
    uncertainty_report_md_path: Path

    def __post_init__(self) -> None:
        """Require a non-empty fit-metric label."""
        if not self.fit_metric.strip():
            raise ValueError("fit_metric must be non-empty")

    @property
    def preference_disagreement_count(self) -> int:
        """Return validation folds with calibration-holdout disagreement."""
        return self.validation_result.preference_disagreement_count

    @property
    def uncertainty_tie_target_count(self) -> int:
        """Return disagreement targets treated as uncertainty ties."""
        return self.uncertainty_report.uncertainty_tie_target_count

    def holdout_preferences(self) -> dict[str, str]:
        """Return holdout-preferred candidates keyed by fold name."""
        return {
            fold.spec.name: fold.holdout_preferred_candidate
            for fold in self.validation_result.folds
        }


@dataclass(frozen=True)
class StructuralSMCFitMetricSensitivityResult:
    """Aggregate fit-metric sensitivity result across validation runs."""

    decisions: tuple[TargetFragilityDecision, ...]
    original_targets: TargetDataset
    filtered_targets: TargetDataset
    skipped_folds: tuple[StructuralSMCValidationFoldSpec, ...]
    runs: tuple[StructuralSMCFitMetricRunResult, ...]
    paths: StructuralSMCFitMetricSensitivityPaths

    def __post_init__(self) -> None:
        """Require at least one completed metric run."""
        if not self.runs:
            raise ValueError("fit-metric sensitivity requires at least one run")

    @property
    def original_target_count(self) -> int:
        """Return the target count before applying the fragility filter."""
        return len(self.original_targets.observations)

    @property
    def filtered_target_count(self) -> int:
        """Return the target count retained after fragility filtering."""
        return len(self.filtered_targets.observations)

    @property
    def excluded_target_count(self) -> int:
        """Return the number of target IDs excluded by fragility decisions."""
        return sum(decision.excluded for decision in self.decisions)

    @property
    def skipped_fold_count(self) -> int:
        """Return the number of folds dropped after target filtering."""
        return len(self.skipped_folds)

    @property
    def unstable_holdout_fold_count(self) -> int:
        """Return folds whose holdout preference changes across metrics."""
        return len(self.unstable_holdout_fold_names())

    def unstable_holdout_fold_names(self) -> tuple[str, ...]:
        """Return fold names with different holdout preferences across metrics."""
        return tuple(
            fold_name
            for fold_name in self.fold_names()
            if len(_preferences_for_fold(self.runs, fold_name)) > 1
        )

    def fold_names(self) -> tuple[str, ...]:
        """Return validation fold names in first-seen order."""
        names: list[str] = []
        for run in self.runs:
            for fold in run.validation_result.folds:
                if fold.spec.name not in names:
                    names.append(fold.spec.name)
        return tuple(names)


def _preferences_for_fold(
    runs: tuple[StructuralSMCFitMetricRunResult, ...],
    fold_name: str,
) -> frozenset[str]:
    """Return the set of holdout preferences observed for one fold."""
    preferences: set[str] = set()
    for run in runs:
        by_fold = run.holdout_preferences()
        if fold_name in by_fold:
            preferences.add(by_fold[fold_name])
    return frozenset(preferences)
