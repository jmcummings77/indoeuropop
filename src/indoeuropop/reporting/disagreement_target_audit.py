"""CSV loading and serialization for disagreement target curation audits."""

from __future__ import annotations

import csv
from collections.abc import Mapping
from io import StringIO
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
from indoeuropop.data.target_notes import target_note_metadata
from indoeuropop.reporting.disagreement_target_audit_models import (
    DISAGREEMENT_TARGET_AUDIT_SAMPLE_FIELDS,
    REQUIRED_DISAGREEMENT_TARGET_AUDIT_COLUMNS,
    DisagreementTargetCurationAudit,
    DisagreementTargetCurationAuditReport,
    target_curation_sample_flags,
)
from indoeuropop.reporting.structural_smc_disagreement_models import required_cell
from indoeuropop.reporting.target_audit import TargetCurationAuditSample


def load_disagreement_target_curation_audit(
    *,
    disagreement_csv: str | Path,
    curation_path: str | Path,
    sample_metadata_path: str | Path,
    ancestry_estimates_path: str | Path,
) -> DisagreementTargetCurationAuditReport:
    """Load a batch curation audit for structural SMC disagreement targets."""
    curation_by_target = {
        record.target_id: record
        for record in load_target_curation(curation_path).records
    }
    metadata_by_id = {
        record.sample_id: record
        for record in load_sample_metadata(sample_metadata_path).records
    }
    estimates_by_key = {
        (estimate.sample_id, estimate.source, estimate.method): estimate
        for estimate in load_sample_ancestry_estimates(
            ancestry_estimates_path
        ).estimates
    }
    return DisagreementTargetCurationAuditReport(
        tuple(
            _audit_from_row(
                row,
                curation_by_target=curation_by_target,
                metadata_by_id=metadata_by_id,
                estimates_by_key=estimates_by_key,
            )
            for row in _load_disagreement_rows(disagreement_csv)
        )
    )


def disagreement_target_audit_sample_rows(
    report: DisagreementTargetCurationAuditReport,
) -> tuple[dict[str, str], ...]:
    """Return long-form sample-level audit rows for CSV serialization."""
    return tuple(
        _sample_payload(audit, sample)
        for audit in report.ranked_audits
        for sample in audit.samples
    )


def disagreement_target_audit_samples_to_csv(
    report: DisagreementTargetCurationAuditReport,
) -> str:
    """Return long-form sample-level audit rows as CSV text."""
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=DISAGREEMENT_TARGET_AUDIT_SAMPLE_FIELDS,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(disagreement_target_audit_sample_rows(report))
    return output.getvalue()


def write_disagreement_target_audit_samples_csv(
    report: DisagreementTargetCurationAuditReport,
    path: str | Path,
) -> Path:
    """Write long-form sample-level audit rows to CSV and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        disagreement_target_audit_samples_to_csv(report), encoding="utf-8"
    )
    return output_path


def _load_disagreement_rows(path: str | Path) -> tuple[Mapping[str, str], ...]:
    """Load structural SMC disagreement rows from a diagnostic CSV."""
    with Path(path).open(newline="", encoding="utf-8") as audit_file:
        reader = csv.DictReader(audit_file)
        if reader.fieldnames is None:
            raise ValueError("disagreement target audit CSV must include a header row")
        missing = REQUIRED_DISAGREEMENT_TARGET_AUDIT_COLUMNS.difference(
            reader.fieldnames
        )
        if missing:
            raise ValueError(
                "disagreement target audit CSV missing columns: "
                + ", ".join(sorted(missing))
            )
        rows = tuple(dict(row) for row in reader)
    if not rows:
        raise ValueError("disagreement target audit CSV must contain at least one row")
    return rows


def _audit_from_row(
    row: Mapping[str, str],
    *,
    curation_by_target: Mapping[str, TargetCurationRecord],
    metadata_by_id: Mapping[str, SampleMetadataRecord],
    estimates_by_key: Mapping[tuple[str, str, str], SampleAncestryEstimate],
) -> DisagreementTargetCurationAudit:
    """Build one target audit from a disagreement row and joined inputs."""
    target_id = required_cell(row, "target_id")
    try:
        curation = curation_by_target[target_id]
    except KeyError as error:
        raise ValueError(
            f"no target curation row matched target_id={target_id}"
        ) from error
    return DisagreementTargetCurationAudit(
        fold_name=required_cell(row, "fold_name"),
        target_id=target_id,
        requested_group_id=required_cell(row, "requested_group_id"),
        target_preferred_candidate=required_cell(row, "target_preferred_candidate"),
        child_minus_structured_pulse_abs_residual_delta=float(
            required_cell(row, "child_minus_structured_pulse_abs_residual_delta")
        ),
        observed_mean=float(required_cell(row, "observed_mean")),
        uncertainty=float(required_cell(row, "uncertainty")),
        publication_keys=required_cell(row, "publication_keys"),
        structured_pulse_absolute_mean_residual=float(
            required_cell(row, "structured_pulse_absolute_mean_residual")
        ),
        child_override_absolute_mean_residual=float(
            required_cell(row, "child_override_absolute_mean_residual")
        ),
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
    )


def _sample_audit_row(
    sample_id: str,
    *,
    metadata_by_id: Mapping[str, SampleMetadataRecord],
    estimates_by_key: Mapping[tuple[str, str, str], SampleAncestryEstimate],
    curation: TargetCurationRecord,
) -> TargetCurationAuditSample:
    """Join one curated sample to metadata and qpAdm estimate evidence."""
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
        qpadm_pvalue=_optional_note_float(getattr(estimate, "note", "")),
        metadata_note=getattr(metadata, "note", ""),
        estimate_note=getattr(estimate, "note", ""),
    )


def _sample_payload(
    audit: DisagreementTargetCurationAudit,
    sample: TargetCurationAuditSample,
) -> dict[str, str]:
    """Return one target/sample join as a CSV-ready payload."""
    return {
        "fold_name": audit.fold_name,
        "target_id": audit.target_id,
        "requested_group_id": audit.requested_group_id,
        "target_preferred_candidate": audit.target_preferred_candidate,
        "child_minus_structured_pulse_abs_residual_delta": _value_text(
            audit.child_minus_structured_pulse_abs_residual_delta
        ),
        "observed_mean": _value_text(audit.observed_mean),
        "uncertainty": _value_text(audit.uncertainty),
        "curation_sample_count": str(audit.curation.sample_count),
        "sample_id": sample.sample_id,
        "sample_time_bce": _optional_value_text(sample.time_bce),
        "date_uncertainty": _optional_value_text(sample.date_uncertainty),
        "sex": sample.sex or "missing",
        "site": sample.site,
        "publication_key": sample.publication_key,
        "estimate": _optional_value_text(sample.estimate),
        "standard_error": _optional_value_text(sample.standard_error),
        "qpadm_pvalue": _optional_value_text(sample.qpadm_pvalue),
        "has_metadata": _bool_text(sample.has_metadata),
        "has_estimate": _bool_text(sample.has_estimate),
        "sample_flags": "|".join(target_curation_sample_flags(audit, sample)),
        "target_note": audit.curation.note,
        "sample_metadata_note": sample.metadata_note,
        "sample_estimate_note": sample.estimate_note,
    }


def _optional_note_float(note: str) -> float | None:
    """Return a qpAdm p-value from a semicolon-delimited note when present."""
    value = target_note_metadata(note).get("qpadm_pvalue")
    return None if value is None else float(value)


def _optional_value_text(value: float | None) -> str:
    """Return a compact value or missing marker."""
    return "missing" if value is None else _value_text(value)


def _value_text(value: float) -> str:
    """Return a stable compact numeric string."""
    return f"{value:.12g}"


def _bool_text(value: bool) -> str:
    """Return a lower-case boolean string."""
    return "true" if value else "false"
