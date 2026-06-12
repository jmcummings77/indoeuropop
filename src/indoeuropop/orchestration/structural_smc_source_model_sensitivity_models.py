"""Models for structural SMC source-model sensitivity workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from indoeuropop.data.targets import TargetDataset
from indoeuropop.orchestration.structural_smc_validation_models import (
    StructuralSMCMultiFoldValidationResult,
    StructuralSMCValidationFoldSpec,
)
from indoeuropop.reporting.structural_smc_uncertainty import (
    StructuralSMCUncertaintyReport,
)


@dataclass(frozen=True)
class StructuralSMCSourceModel:
    """One labeled target dataset representing a qpAdm source-model surface."""

    label: str
    targets: TargetDataset
    target_path: Path | None = None

    def __post_init__(self) -> None:
        """Normalize and validate the source-model label."""
        label = self.label.strip()
        if not label:
            raise ValueError("source model label must be non-empty")
        object.__setattr__(self, "label", label)


@dataclass(frozen=True)
class StructuralSMCSourceModelSensitivityPaths:
    """Filesystem paths for source-model sensitivity artifacts."""

    output_dir: Path
    summary_csv: Path
    report_md: Path
    source_models_output_dir: Path


@dataclass(frozen=True)
class StructuralSMCSourceModelRunResult:
    """One source-model target run and its structural validation result."""

    source_model: StructuralSMCSourceModel
    prepared_targets: TargetDataset
    validation_result: StructuralSMCMultiFoldValidationResult
    uncertainty_report: StructuralSMCUncertaintyReport
    skipped_folds: tuple[StructuralSMCValidationFoldSpec, ...]
    missing_override_regions: tuple[str, ...]
    output_dir: Path
    prepared_targets_csv_path: Path
    structured_config_toml_path: Path
    uncertainty_csv_path: Path
    uncertainty_report_md_path: Path

    @property
    def label(self) -> str:
        """Return the source-model label."""
        return self.source_model.label

    @property
    def original_target_count(self) -> int:
        """Return the input target count before alignment."""
        return len(self.source_model.targets.observations)

    @property
    def prepared_target_count(self) -> int:
        """Return the target count retained for this source-model run."""
        return len(self.prepared_targets.observations)

    @property
    def skipped_fold_count(self) -> int:
        """Return validation folds skipped for this source-model run."""
        return len(self.skipped_folds)

    @property
    def preference_disagreement_count(self) -> int:
        """Return validation folds with calibration-holdout disagreement."""
        return self.validation_result.preference_disagreement_count

    def holdout_preferences(self) -> dict[str, str]:
        """Return holdout-preferred candidates keyed by fold name."""
        return {
            fold.spec.name: fold.holdout_preferred_candidate
            for fold in self.validation_result.folds
        }


@dataclass(frozen=True)
class StructuralSMCSourceModelSensitivityResult:
    """Aggregate source-model sensitivity result across target surfaces."""

    runs: tuple[StructuralSMCSourceModelRunResult, ...]
    common_target_ids: tuple[str, ...]
    excluded_fragile_target_ids: tuple[str, ...]
    paths: StructuralSMCSourceModelSensitivityPaths

    def __post_init__(self) -> None:
        """Require at least one completed source-model run."""
        if not self.runs:
            raise ValueError("source-model sensitivity requires at least one run")

    @property
    def source_model_count(self) -> int:
        """Return the number of evaluated source-model target surfaces."""
        return len(self.runs)

    @property
    def retained_common_target_count(self) -> int:
        """Return common target IDs retained after fragility filtering."""
        return len(self.common_target_ids) - len(self.excluded_fragile_target_ids)

    @property
    def unstable_holdout_fold_count(self) -> int:
        """Return folds whose holdout preference changes across source models."""
        return len(self.unstable_holdout_fold_names())

    def unstable_holdout_fold_names(self) -> tuple[str, ...]:
        """Return fold names with different holdout preferences across sources."""
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
    runs: tuple[StructuralSMCSourceModelRunResult, ...],
    fold_name: str,
) -> frozenset[str]:
    """Return the holdout preferences observed for one fold."""
    preferences: set[str] = set()
    for run in runs:
        by_fold = run.holdout_preferences()
        if fold_name in by_fold:
            preferences.add(by_fold[fold_name])
    return frozenset(preferences)
