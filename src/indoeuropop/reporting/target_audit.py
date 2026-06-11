"""Detailed target curation audits for qpAdm-backed residual outliers."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from indoeuropop.data.ancestry_estimates import (
    SampleAncestryEstimate,
    load_sample_ancestry_estimates,
)
from indoeuropop.data.sample_metadata import (
    SampleMetadataRecord,
    load_sample_metadata,
)
from indoeuropop.data.target_curation import (
    TargetCurationRecord,
    load_target_curation,
)
from indoeuropop.reporting.target_review import (
    TargetResidualReviewRow,
    load_target_residual_review_rows,
)

IDENTICAL_ESTIMATE_TOLERANCE = 1e-12
HIGH_STANDARD_ERROR_THRESHOLD = 0.25


@dataclass(frozen=True)
class TargetCurationAuditSample:
    """Joined metadata and qpAdm estimate evidence for one curated sample."""

    sample_id: str
    time_bce: float | None
    date_uncertainty: float | None
    sex: str
    site: str
    publication_key: str
    estimate: float | None
    standard_error: float | None
    qpadm_pvalue: float | None
    metadata_note: str = ""
    estimate_note: str = ""

    def __post_init__(self) -> None:
        """Validate sample audit values while allowing missing joined inputs."""
        if not self.sample_id:
            raise ValueError("sample_id must be non-empty")
        for field_name in ("time_bce", "date_uncertainty"):
            value = getattr(self, field_name)
            if value is not None and not isfinite(value):
                raise ValueError(f"{field_name} must be finite when present")
        for field_name in ("estimate", "standard_error", "qpadm_pvalue"):
            value = getattr(self, field_name)
            if value is not None and (not isfinite(value) or not 0 <= value <= 1):
                raise ValueError(f"{field_name} must be a proportion when present")
        if self.standard_error == 0:
            raise ValueError("standard_error must be positive when present")

    @property
    def has_metadata(self) -> bool:
        """Return whether this row found a matching sample-metadata record."""
        return self.time_bce is not None

    @property
    def has_estimate(self) -> bool:
        """Return whether this row found a matching sample-ancestry estimate."""
        return self.estimate is not None


@dataclass(frozen=True)
class TargetCurationAudit:
    """Decision-oriented audit for one target residual and its curation inputs."""

    residual: TargetResidualReviewRow
    curation: TargetCurationRecord
    samples: tuple[TargetCurationAuditSample, ...]
    outlier_z_threshold: float = 2.0

    def __post_init__(self) -> None:
        """Validate audit-level structure."""
        if not self.samples:
            raise ValueError("samples must contain at least one sample")
        if not isfinite(self.outlier_z_threshold) or self.outlier_z_threshold <= 0:
            raise ValueError("outlier_z_threshold must be positive")

    @property
    def target_id(self) -> str:
        """Return the audited target identifier."""
        return self.curation.target_id

    @property
    def requested_group_id(self) -> str:
        """Return the requested AADR group identifier when present."""
        return self.residual.requested_group_id

    @property
    def missing_metadata_ids(self) -> tuple[str, ...]:
        """Return curated sample IDs absent from the metadata input."""
        return tuple(
            sample.sample_id for sample in self.samples if not sample.has_metadata
        )

    @property
    def missing_estimate_ids(self) -> tuple[str, ...]:
        """Return curated sample IDs absent from the ancestry-estimate input."""
        return tuple(
            sample.sample_id for sample in self.samples if not sample.has_estimate
        )

    @property
    def estimates(self) -> tuple[float, ...]:
        """Return all available sample-level ancestry estimates."""
        return tuple(
            sample.estimate for sample in self.samples if sample.estimate is not None
        )

    @property
    def standard_errors(self) -> tuple[float, ...]:
        """Return all available sample-level standard errors."""
        return tuple(
            sample.standard_error
            for sample in self.samples
            if sample.standard_error is not None
        )

    @property
    def qpadm_pvalues(self) -> tuple[float, ...]:
        """Return all available qpAdm p-values."""
        return tuple(
            sample.qpadm_pvalue
            for sample in self.samples
            if sample.qpadm_pvalue is not None
        )

    @property
    def all_estimates_identical(self) -> bool:
        """Return whether multiple samples carry one identical qpAdm estimate."""
        estimates = self.estimates
        if len(estimates) < 2:
            return False
        return max(estimates) - min(estimates) <= IDENTICAL_ESTIMATE_TOLERANCE

    @property
    def critical_sample_ids(self) -> tuple[str, ...]:
        """Return samples with AADR notes marked critical."""
        return tuple(
            sample.sample_id
            for sample in self.samples
            if "assessment=CRITICAL" in sample.metadata_note
        )

    @property
    def out_of_window_sample_ids(self) -> tuple[str, ...]:
        """Return metadata rows whose dates fall outside the curation window."""
        return tuple(
            sample.sample_id
            for sample in self.samples
            if sample.time_bce is not None
            and not self.curation.end_bce <= sample.time_bce <= self.curation.start_bce
        )

    @property
    def publication_keys(self) -> tuple[str, ...]:
        """Return unique sample publication keys in curation order."""
        return _unique(
            sample.publication_key for sample in self.samples if sample.publication_key
        )

    @property
    def sex_counts(self) -> dict[str, int]:
        """Return sample counts by reported sex label."""
        counts: dict[str, int] = {}
        for sample in self.samples:
            label = sample.sex or "missing"
            counts[label] = counts.get(label, 0) + 1
        return counts

    @property
    def issues(self) -> tuple[str, ...]:
        """Return audit findings that should be reviewed before interpretation."""
        issues: list[str] = []
        if abs(self.residual.z_score) >= self.outlier_z_threshold:
            issues.append(
                "Residual exceeds the configured outlier threshold; inspect target "
                "construction before tuning simulator parameters."
            )
        if self.missing_metadata_ids:
            issues.append(
                "Curated sample IDs missing metadata: "
                + ", ".join(self.missing_metadata_ids)
            )
        if self.missing_estimate_ids:
            issues.append(
                "Curated sample IDs missing ancestry estimates: "
                + ", ".join(self.missing_estimate_ids)
            )
        if self.curation.sample_count != len(self.samples):
            issues.append("Curation sample_count does not match the sample ID list.")
        if self.out_of_window_sample_ids:
            issues.append(
                "Sample dates outside the curation window: "
                + ", ".join(self.out_of_window_sample_ids)
            )
        if self.critical_sample_ids:
            issues.append(
                "AADR metadata marks samples as CRITICAL: "
                + ", ".join(self.critical_sample_ids)
            )
        if self.all_estimates_identical:
            issues.append(
                "All curated samples share the same qpAdm estimate; verify whether "
                "the source table contains replicated group-level results."
            )
        if (
            _max_or_none(self.standard_errors) is not None
            and (_max_or_none(self.standard_errors) or 0.0)
            >= HIGH_STANDARD_ERROR_THRESHOLD
        ):
            issues.append("At least one qpAdm standard error is high for a target row.")
        if len(self.publication_keys) > 1:
            issues.append(
                "The curated group spans multiple publication keys; verify that AADR "
                "group harmonization is intended."
            )
        return tuple(issues)

    @property
    def recommendation(self) -> str:
        """Return the next scientific action implied by the audit."""
        if self.missing_metadata_ids or self.missing_estimate_ids:
            return "Fix target input joins before interpreting this residual."
        if self.all_estimates_identical:
            return (
                "Review qpAdm source/outgroup choices and table granularity; do not "
                "treat replicated group-level estimates as independent sample signal."
            )
        if self.critical_sample_ids:
            return (
                "Decide whether CRITICAL AADR samples should be excluded or caveated."
            )
        if abs(self.residual.z_score) >= self.outlier_z_threshold:
            return "Review target curation and qpAdm model fit before simulator tuning."
        return "No curation blocker found; this target can move to scenario review."


def load_target_curation_audit(
    *,
    residuals_path: str | Path,
    curation_path: str | Path,
    sample_metadata_path: str | Path,
    ancestry_estimates_path: str | Path,
    target_id: str | None = None,
    requested_group_id: str | None = None,
    outlier_z_threshold: float = 2.0,
) -> TargetCurationAudit:
    """Load and join residual, curation, metadata, and qpAdm estimate evidence."""
    residual = _select_residual(
        load_target_residual_review_rows(residuals_path),
        target_id=target_id,
        requested_group_id=requested_group_id,
    )
    selected_target_id = target_id or _note_value(residual.note, "target_id")
    if not selected_target_id:
        raise ValueError("target_id is required when residual notes omit target_id")

    curation = _target_curation_record(curation_path, selected_target_id)
    metadata = load_sample_metadata(sample_metadata_path)
    metadata_by_id = {record.sample_id: record for record in metadata.records}
    ancestry_estimates = load_sample_ancestry_estimates(ancestry_estimates_path)
    estimates_by_key = {
        (estimate.sample_id, estimate.source, estimate.method): estimate
        for estimate in ancestry_estimates.estimates
    }
    return TargetCurationAudit(
        residual=residual,
        curation=curation,
        samples=tuple(
            _sample_audit_row(
                sample_id,
                metadata_by_id=metadata_by_id,
                estimates_by_key=estimates_by_key,
                curation=curation,
            )
            for sample_id in curation.sample_ids
        ),
        outlier_z_threshold=outlier_z_threshold,
    )


def _select_residual(
    rows: tuple[TargetResidualReviewRow, ...],
    *,
    target_id: str | None,
    requested_group_id: str | None,
) -> TargetResidualReviewRow:
    """Select a residual by target, group, or highest absolute z-score."""
    if target_id is not None:
        return _single_residual(
            rows,
            lambda row: _note_value(row.note, "target_id") == target_id,
            f"target_id={target_id}",
        )
    if requested_group_id is not None:
        return _single_residual(
            rows,
            lambda row: row.requested_group_id == requested_group_id,
            f"requested_group_id={requested_group_id}",
        )
    return max(rows, key=lambda row: row.abs_z_score)


def _single_residual(
    rows: tuple[TargetResidualReviewRow, ...],
    predicate: Callable[[TargetResidualReviewRow], bool],
    label: str,
) -> TargetResidualReviewRow:
    """Return exactly one residual matching a predicate."""
    matches = tuple(row for row in rows if predicate(row))
    if not matches:
        raise ValueError(f"no residual row matched {label}")
    if len(matches) > 1:
        raise ValueError(f"multiple residual rows matched {label}")
    return matches[0]


def _target_curation_record(path: str | Path, target_id: str) -> TargetCurationRecord:
    """Return one curation row by target identifier."""
    matches = tuple(
        record
        for record in load_target_curation(path).records
        if record.target_id == target_id
    )
    if not matches:
        raise ValueError(f"no target curation row matched target_id={target_id}")
    return matches[0]


def _sample_audit_row(
    sample_id: str,
    *,
    metadata_by_id: dict[str, SampleMetadataRecord],
    estimates_by_key: dict[tuple[str, str, str], SampleAncestryEstimate],
    curation: TargetCurationRecord,
) -> TargetCurationAuditSample:
    """Join one sample's metadata and ancestry estimate for audit reporting."""
    metadata = metadata_by_id.get(sample_id)
    estimate = estimates_by_key.get(
        (sample_id, curation.source, curation.ancestry_method)
    )
    return TargetCurationAuditSample(
        sample_id=sample_id,
        time_bce=getattr(metadata, "time_bce", None),
        date_uncertainty=getattr(metadata, "date_uncertainty", None),
        sex=getattr(metadata, "sex", ""),
        site=getattr(metadata, "site", ""),
        publication_key=getattr(metadata, "publication_key", ""),
        estimate=getattr(estimate, "estimate", None),
        standard_error=getattr(estimate, "standard_error", None),
        qpadm_pvalue=_optional_note_float(
            getattr(estimate, "note", ""),
            "qpadm_pvalue",
        ),
        metadata_note=getattr(metadata, "note", ""),
        estimate_note=getattr(estimate, "note", ""),
    )


def _note_value(note: str, key: str) -> str:
    """Return a semicolon-delimited note value for a key when present."""
    prefix = f"{key}="
    for part in note.split(";"):
        text = part.strip()
        if text.startswith(prefix):
            return text.removeprefix(prefix).strip()
    return ""


def _optional_note_float(note: str, key: str) -> float | None:
    """Return a float from a semicolon-delimited note field when present."""
    value = _note_value(note, key)
    return None if value == "" else float(value)


def _max_or_none(values: tuple[float, ...]) -> float | None:
    """Return the maximum value or `None` for empty inputs."""
    return None if not values else max(values)


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    """Return unique strings while preserving curation order."""
    unique_values: list[str] = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)
    return tuple(unique_values)
