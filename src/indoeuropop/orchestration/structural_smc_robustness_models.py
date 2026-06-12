"""Models for unified structural SMC robustness decisions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from indoeuropop.data.structural_smc_caveat_dispositions import (
    StructuralSMCCaveatDispositionValidationReport,
)

StructuralSMCRobustnessStatus = Literal[
    "blocked", "review_with_caveats", "ready_to_promote"
]
StructuralSMCRobustnessSeverity = Literal["blocker", "caution"]


@dataclass(frozen=True)
class StructuralSMCRobustnessIssue:
    """One blocker or caveat produced by a robustness gate."""

    gate: str
    severity: StructuralSMCRobustnessSeverity
    message: str

    def __post_init__(self) -> None:
        """Normalize text fields and reject invalid issue severities."""
        gate = self.gate.strip()
        message = self.message.strip()
        if not gate:
            raise ValueError("gate must be non-empty")
        if self.severity not in ("blocker", "caution"):
            raise ValueError("severity must be blocker or caution")
        if not message:
            raise ValueError("message must be non-empty")
        object.__setattr__(self, "gate", gate)
        object.__setattr__(self, "message", message)


@dataclass(frozen=True)
class TargetFragilityRobustnessSummary:
    """Decision counts from the target-fragility sensitivity gate."""

    audited_target_count: int
    excluded_target_count: int

    def __post_init__(self) -> None:
        """Reject impossible target-fragility counts."""
        _require_non_negative("audited_target_count", self.audited_target_count)
        _require_non_negative("excluded_target_count", self.excluded_target_count)
        if self.excluded_target_count > self.audited_target_count:
            raise ValueError("excluded_target_count cannot exceed audited_target_count")

    @property
    def retained_audited_target_count(self) -> int:
        """Return audited targets not excluded by the fragility gate."""
        return self.audited_target_count - self.excluded_target_count


@dataclass(frozen=True)
class FitMetricRobustnessSummary:
    """Aggregate sensitivity counts from fit-metric validation runs."""

    metric_count: int
    unstable_holdout_fold_count: int
    max_preference_disagreement_count: int
    max_uncertainty_tie_target_count: int

    def __post_init__(self) -> None:
        """Reject negative fit-metric robustness counts."""
        for field_name in (
            "metric_count",
            "unstable_holdout_fold_count",
            "max_preference_disagreement_count",
            "max_uncertainty_tie_target_count",
        ):
            _require_non_negative(field_name, getattr(self, field_name))


@dataclass(frozen=True)
class SourceModelRobustnessSummary:
    """Aggregate sensitivity counts from source-model validation runs."""

    source_model_count: int
    unstable_holdout_fold_count: int
    max_preference_disagreement_count: int
    max_uncertainty_tie_target_count: int
    max_missing_override_region_count: int
    max_skipped_fold_count: int

    def __post_init__(self) -> None:
        """Reject negative source-model robustness counts."""
        for field_name in (
            "source_model_count",
            "unstable_holdout_fold_count",
            "max_preference_disagreement_count",
            "max_uncertainty_tie_target_count",
            "max_missing_override_region_count",
            "max_skipped_fold_count",
        ):
            _require_non_negative(field_name, getattr(self, field_name))


@dataclass(frozen=True)
class StructuralSMCRobustnessDecisionPaths:
    """Filesystem paths written by the robustness decision report."""

    output_dir: Path
    summary_csv: Path
    report_md: Path


@dataclass(frozen=True)
class StructuralSMCRobustnessDecision:
    """Unified promotion decision across structural SMC robustness gates."""

    candidate_name: str
    target_fragility: TargetFragilityRobustnessSummary
    fit_metric: FitMetricRobustnessSummary
    source_model: SourceModelRobustnessSummary
    issues: tuple[StructuralSMCRobustnessIssue, ...]
    paths: StructuralSMCRobustnessDecisionPaths
    caveat_dispositions: StructuralSMCCaveatDispositionValidationReport | None = None

    def __post_init__(self) -> None:
        """Normalize the candidate name used in reports."""
        candidate_name = self.candidate_name.strip()
        if not candidate_name:
            raise ValueError("candidate_name must be non-empty")
        object.__setattr__(self, "candidate_name", candidate_name)

    @property
    def blocker_count(self) -> int:
        """Return the number of issues that block candidate promotion."""
        return sum(issue.severity == "blocker" for issue in self.issues)

    @property
    def caution_count(self) -> int:
        """Return the number of non-blocking caveats."""
        return sum(issue.severity == "caution" for issue in self.issues)

    @property
    def status(self) -> StructuralSMCRobustnessStatus:
        """Return the candidate's unified robustness status."""
        if self.blocker_count:
            return "blocked"
        if self.caution_count:
            return "review_with_caveats"
        return "ready_to_promote"

    @property
    def recommendation(self) -> str:
        """Return a concise promotion recommendation."""
        recommendations = {
            "blocked": "do_not_promote",
            "review_with_caveats": "promote_only_with_documented_caveats",
            "ready_to_promote": "promote",
        }
        return recommendations[self.status]


def _require_non_negative(field_name: str, value: int) -> None:
    """Raise when a count field is negative."""
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")
