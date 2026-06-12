"""Models for target-fragility sensitivity gates."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from indoeuropop.data.targets import TargetDataset
from indoeuropop.orchestration.structural_smc_validation_models import (
    StructuralSMCMultiFoldValidationResult,
    StructuralSMCValidationFoldSpec,
)

DEFAULT_TARGET_FRAGILITY_FLAGS = (
    "high_se",
    "critical",
    "missing_metadata",
    "missing_estimate",
    "out_of_window",
)

DEFAULT_REPEATED_ESTIMATE_TOLERANCE = 1e-12


@dataclass(frozen=True)
class TargetFragilityDecision:
    """One target-level inclusion decision derived from sample audit evidence."""

    target_id: str
    requested_group_id: str
    sample_count: int
    available_estimate_count: int
    unique_estimate_count: int
    sample_flags: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Normalize labels and reject inconsistent aggregate counts."""
        target_id = self.target_id.strip()
        requested_group_id = self.requested_group_id.strip()
        if not target_id:
            raise ValueError("target_id must be non-empty")
        if not requested_group_id:
            raise ValueError("requested_group_id must be non-empty")
        for field_name in (
            "sample_count",
            "available_estimate_count",
            "unique_estimate_count",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} must be non-negative")
        if self.available_estimate_count > self.sample_count:
            raise ValueError("available_estimate_count cannot exceed sample_count")
        if self.unique_estimate_count > self.available_estimate_count:
            raise ValueError(
                "unique_estimate_count cannot exceed available_estimate_count"
            )
        object.__setattr__(self, "target_id", target_id)
        object.__setattr__(self, "requested_group_id", requested_group_id)
        object.__setattr__(self, "sample_flags", _unique(self.sample_flags))
        object.__setattr__(self, "reasons", _unique(self.reasons))

    @property
    def excluded(self) -> bool:
        """Return whether this target should be removed by the gate."""
        return bool(self.reasons)

    @property
    def reason_text(self) -> str:
        """Return semicolon-delimited exclusion reasons for reports."""
        return ";".join(self.reasons)

    @property
    def sample_flag_text(self) -> str:
        """Return semicolon-delimited sample flags for reports."""
        return ";".join(self.sample_flags)


@dataclass(frozen=True)
class TargetFragilityGatePaths:
    """Filesystem paths written by a target-fragility validation gate."""

    output_dir: Path
    filtered_targets_csv: Path
    decisions_csv: Path
    report_md: Path
    validation_output_dir: Path


@dataclass(frozen=True)
class TargetFragilityGateResult:
    """Result from filtering fragile targets and rerunning validation."""

    decisions: tuple[TargetFragilityDecision, ...]
    original_targets: TargetDataset
    filtered_targets: TargetDataset
    skipped_folds: tuple[StructuralSMCValidationFoldSpec, ...]
    validation_result: StructuralSMCMultiFoldValidationResult
    paths: TargetFragilityGatePaths

    @property
    def original_target_count(self) -> int:
        """Return the target count before applying the fragility filter."""
        return len(self.original_targets.observations)

    @property
    def filtered_target_count(self) -> int:
        """Return the target count retained after applying the fragility filter."""
        return len(self.filtered_targets.observations)

    @property
    def excluded_target_count(self) -> int:
        """Return the number of target IDs excluded by the gate."""
        return sum(decision.excluded for decision in self.decisions)

    @property
    def skipped_fold_count(self) -> int:
        """Return the number of folds dropped after target filtering."""
        return len(self.skipped_folds)


def repeated_estimates(
    estimates: tuple[float, ...],
    *,
    tolerance: float = DEFAULT_REPEATED_ESTIMATE_TOLERANCE,
) -> bool:
    """Return whether multiple estimates are equal within a small tolerance."""
    if not isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance must be a non-negative finite value")
    return len(estimates) >= 2 and max(estimates) - min(estimates) <= tolerance


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    """Return unique non-empty values while preserving order."""
    unique_values: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in unique_values:
            unique_values.append(normalized)
    return tuple(unique_values)
