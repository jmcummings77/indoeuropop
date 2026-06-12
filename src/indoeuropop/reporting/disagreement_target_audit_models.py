"""Models for structural SMC disagreement target curation audits."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite

from indoeuropop.data.target_curation import TargetCurationRecord
from indoeuropop.reporting.target_audit import (
    HIGH_STANDARD_ERROR_THRESHOLD,
    IDENTICAL_ESTIMATE_TOLERANCE,
    TargetCurationAuditSample,
)

REQUIRED_DISAGREEMENT_TARGET_AUDIT_COLUMNS = frozenset(
    (
        "fold_name",
        "target_id",
        "requested_group_id",
        "publication_keys",
        "region",
        "source",
        "time_bce",
        "observed_mean",
        "uncertainty",
        "structured_pulse_absolute_mean_residual",
        "child_override_absolute_mean_residual",
        "child_minus_structured_pulse_abs_residual_delta",
        "target_preferred_candidate",
    )
)

DISAGREEMENT_TARGET_AUDIT_SAMPLE_FIELDS = (
    "fold_name",
    "target_id",
    "requested_group_id",
    "target_preferred_candidate",
    "child_minus_structured_pulse_abs_residual_delta",
    "observed_mean",
    "uncertainty",
    "curation_sample_count",
    "sample_id",
    "sample_time_bce",
    "date_uncertainty",
    "sex",
    "site",
    "publication_key",
    "estimate",
    "standard_error",
    "qpadm_pvalue",
    "has_metadata",
    "has_estimate",
    "sample_flags",
    "target_note",
    "sample_metadata_note",
    "sample_estimate_note",
)


@dataclass(frozen=True)
class DisagreementTargetCurationAudit:
    """Joined curation, metadata, and qpAdm evidence for one disagreement target."""

    fold_name: str
    target_id: str
    requested_group_id: str
    target_preferred_candidate: str
    child_minus_structured_pulse_abs_residual_delta: float
    observed_mean: float
    uncertainty: float
    publication_keys: str
    structured_pulse_absolute_mean_residual: float
    child_override_absolute_mean_residual: float
    curation: TargetCurationRecord
    samples: tuple[TargetCurationAuditSample, ...]

    def __post_init__(self) -> None:
        """Validate target-level audit values."""
        for field_name in (
            "fold_name",
            "target_id",
            "requested_group_id",
            "target_preferred_candidate",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must be non-empty")
        for field_name in (
            "child_minus_structured_pulse_abs_residual_delta",
            "observed_mean",
            "uncertainty",
            "structured_pulse_absolute_mean_residual",
            "child_override_absolute_mean_residual",
        ):
            if not isfinite(getattr(self, field_name)):
                raise ValueError(f"{field_name} must be finite")
        if self.uncertainty <= 0:
            raise ValueError("uncertainty must be positive")
        if not self.samples:
            raise ValueError("samples must contain at least one sample")

    @property
    def sample_count(self) -> int:
        """Return the number of curated sample rows joined for this target."""
        return len(self.samples)

    @property
    def missing_metadata_ids(self) -> tuple[str, ...]:
        """Return curated sample IDs missing from sample metadata."""
        return tuple(
            sample.sample_id for sample in self.samples if not sample.has_metadata
        )

    @property
    def missing_estimate_ids(self) -> tuple[str, ...]:
        """Return curated sample IDs missing from sample ancestry estimates."""
        return tuple(
            sample.sample_id for sample in self.samples if not sample.has_estimate
        )

    @property
    def critical_sample_ids(self) -> tuple[str, ...]:
        """Return sample IDs whose metadata carries a CRITICAL assessment."""
        return tuple(
            sample.sample_id
            for sample in self.samples
            if "assessment=CRITICAL" in sample.metadata_note
        )

    @property
    def out_of_window_sample_ids(self) -> tuple[str, ...]:
        """Return sample IDs whose dates sit outside the curation window."""
        return tuple(
            sample.sample_id
            for sample in self.samples
            if sample.time_bce is not None
            and not self.curation.end_bce <= sample.time_bce <= self.curation.start_bce
        )

    @property
    def estimates(self) -> tuple[float, ...]:
        """Return available sample-level ancestry estimates."""
        return tuple(
            sample.estimate for sample in self.samples if sample.estimate is not None
        )

    @property
    def standard_errors(self) -> tuple[float, ...]:
        """Return available sample-level qpAdm standard errors."""
        return tuple(
            sample.standard_error
            for sample in self.samples
            if sample.standard_error is not None
        )

    @property
    def qpadm_pvalues(self) -> tuple[float, ...]:
        """Return available sample-level qpAdm p-values."""
        return tuple(
            sample.qpadm_pvalue
            for sample in self.samples
            if sample.qpadm_pvalue is not None
        )

    @property
    def all_estimates_identical(self) -> bool:
        """Return whether multiple samples share one identical estimate."""
        estimates = self.estimates
        return (
            len(estimates) >= 2
            and max(estimates) - min(estimates) <= IDENTICAL_ESTIMATE_TOLERANCE
        )

    @property
    def sample_publication_keys(self) -> tuple[str, ...]:
        """Return unique sample publication keys in curation order."""
        return _unique(
            sample.publication_key for sample in self.samples if sample.publication_key
        )

    @property
    def high_standard_error(self) -> bool:
        """Return whether any sample estimate has a high standard error."""
        return (
            bool(self.standard_errors)
            and max(self.standard_errors) >= HIGH_STANDARD_ERROR_THRESHOLD
        )

    @property
    def issues(self) -> tuple[str, ...]:
        """Return curation warnings to review before structural tuning."""
        issues: list[str] = []
        if self.missing_metadata_ids:
            issues.append(
                "Missing sample metadata: " + ", ".join(self.missing_metadata_ids)
            )
        if self.missing_estimate_ids:
            issues.append(
                "Missing qpAdm estimates: " + ", ".join(self.missing_estimate_ids)
            )
        if self.curation.sample_count != self.sample_count:
            issues.append("Curation sample_count does not match joined samples.")
        if self.out_of_window_sample_ids:
            issues.append(
                "Sample dates outside curation window: "
                + ", ".join(self.out_of_window_sample_ids)
            )
        if self.critical_sample_ids:
            issues.append(
                "AADR metadata marks samples as CRITICAL: "
                + ", ".join(self.critical_sample_ids)
            )
        if self.all_estimates_identical:
            issues.append("Multiple curated samples share one qpAdm estimate.")
        if self.high_standard_error:
            issues.append("At least one qpAdm standard error is high.")
        if len(self.sample_publication_keys) > 1:
            issues.append("Curated samples span multiple publication keys.")
        if not _target_publication_keys(self.publication_keys).issuperset(
            self.sample_publication_keys
        ):
            issues.append("Sample publication keys are not all in target notes.")
        return tuple(issues)

    @property
    def recommendation(self) -> str:
        """Return the next review action for this target."""
        if self.missing_metadata_ids or self.missing_estimate_ids:
            return "Fix missing joins before interpreting this disagreement target."
        if self.critical_sample_ids:
            return "Decide whether CRITICAL AADR samples should remain in the target."
        if self.all_estimates_identical or self.high_standard_error:
            return "Review qpAdm source model and uncertainty before model tuning."
        if self.out_of_window_sample_ids:
            return "Review chronology/window assignment before structural tuning."
        return "No curation blocker found; move this row to scenario review."


@dataclass(frozen=True)
class DisagreementTargetCurationAuditReport:
    """Batch audit report for structural SMC disagreement targets."""

    audits: tuple[DisagreementTargetCurationAudit, ...]

    @property
    def target_count(self) -> int:
        """Return the number of audited disagreement targets."""
        return len(self.audits)

    @property
    def sample_count(self) -> int:
        """Return the number of joined sample rows across audited targets."""
        return sum(audit.sample_count for audit in self.audits)

    @property
    def issue_target_count(self) -> int:
        """Return the number of targets with at least one audit issue."""
        return sum(bool(audit.issues) for audit in self.audits)

    @property
    def ranked_audits(self) -> tuple[DisagreementTargetCurationAudit, ...]:
        """Return targets ranked by child-minus-pulse residual penalty."""
        return tuple(
            sorted(
                self.audits,
                key=lambda audit: audit.child_minus_structured_pulse_abs_residual_delta,
                reverse=True,
            )
        )


def target_curation_sample_flags(
    audit: DisagreementTargetCurationAudit,
    sample: TargetCurationAuditSample,
) -> tuple[str, ...]:
    """Return compact review flags for a joined sample row."""
    flags: list[str] = []
    if not sample.has_metadata:
        flags.append("missing_metadata")
    if not sample.has_estimate:
        flags.append("missing_estimate")
    if sample.sample_id in audit.critical_sample_ids:
        flags.append("critical")
    if sample.sample_id in audit.out_of_window_sample_ids:
        flags.append("out_of_window")
    if (
        sample.standard_error is not None
        and sample.standard_error >= HIGH_STANDARD_ERROR_THRESHOLD
    ):
        flags.append("high_se")
    return tuple(flags)


def _target_publication_keys(value: str) -> frozenset[str]:
    """Return target-level publication keys from pipe-separated metadata."""
    return frozenset(part.strip() for part in value.split("|") if part.strip())


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    """Return unique strings while preserving input order."""
    unique_values: list[str] = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)
    return tuple(unique_values)
