"""Markdown rendering for disagreement target curation audits."""

from __future__ import annotations

from collections.abc import Iterable
from io import StringIO
from pathlib import Path

from indoeuropop.data.target_curation import TargetCurationRecord
from indoeuropop.reporting.disagreement_target_audit_models import (
    DisagreementTargetCurationAudit,
    DisagreementTargetCurationAuditReport,
    target_curation_sample_flags,
)
from indoeuropop.reporting.target_audit import TargetCurationAuditSample


def disagreement_target_audit_markdown(
    report: DisagreementTargetCurationAuditReport,
) -> str:
    """Return a Markdown batch curation audit for disagreement targets."""
    output = StringIO()
    output.write("# Structural SMC Disagreement Target Audit\n\n")
    output.write("## Summary\n\n")
    output.write(f"- target_count: {report.target_count}\n")
    output.write(f"- joined_sample_count: {report.sample_count}\n")
    output.write(f"- issue_target_count: {report.issue_target_count}\n\n")
    output.write("## Target Overview\n\n")
    output.write(
        "| fold | requested_group_id | target_preference | samples | "
        "uncertainty | child_minus_pulse_abs_delta | issue_count |\n"
    )
    output.write("| --- | --- | --- | ---: | ---: | ---: | ---: |\n")
    for audit in report.ranked_audits:
        output.write(
            f"| {audit.fold_name} | {audit.requested_group_id} | "
            f"{audit.target_preferred_candidate} | {audit.sample_count} | "
            f"{_value_text(audit.uncertainty)} | "
            f"{_value_text(audit.child_minus_structured_pulse_abs_residual_delta)} | "
            f"{len(audit.issues)} |\n"
        )
    output.write("\n")
    for audit in report.ranked_audits:
        _write_audit_section(output, audit)
    return output.getvalue()


def write_disagreement_target_audit_markdown(
    report: DisagreementTargetCurationAuditReport,
    path: str | Path,
) -> Path:
    """Write a Markdown batch audit and return the output path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(disagreement_target_audit_markdown(report), encoding="utf-8")
    return output_path


def _write_audit_section(
    output: StringIO,
    audit: DisagreementTargetCurationAudit,
) -> None:
    """Append one target's detailed Markdown audit section."""
    output.write(f"## {audit.requested_group_id}\n\n")
    output.write(f"- target_id: {audit.target_id}\n")
    output.write(f"- fold_name: {audit.fold_name}\n")
    output.write(f"- target_preferred_candidate: {audit.target_preferred_candidate}\n")
    output.write(f"- observed_mean: {_value_text(audit.observed_mean)}\n")
    output.write(f"- uncertainty: {_value_text(audit.uncertainty)}\n")
    output.write(
        "- structured_pulse_absolute_mean_residual: "
        f"{_value_text(audit.structured_pulse_absolute_mean_residual)}\n"
    )
    output.write(
        "- child_override_absolute_mean_residual: "
        f"{_value_text(audit.child_override_absolute_mean_residual)}\n"
    )
    output.write(f"- curation_window_bce: {_curation_window_text(audit.curation)}\n")
    output.write(f"- curation_sample_count: {audit.curation.sample_count}\n")
    output.write(f"- metadata_time_range_bce: {_range_text(_times(audit.samples))}\n")
    output.write(f"- estimate_range: {_range_text(audit.estimates)}\n")
    output.write(f"- standard_error_range: {_range_text(audit.standard_errors)}\n")
    output.write(f"- qpadm_pvalue_range: {_range_text(audit.qpadm_pvalues)}\n")
    output.write(f"- target_publication_keys: {audit.publication_keys}\n")
    output.write(
        "- sample_publication_keys: "
        f"{', '.join(audit.sample_publication_keys) or 'none'}\n"
    )
    output.write(f"- recommendation: {audit.recommendation}\n")
    output.write("\n### Review Checks\n\n")
    for issue in audit.issues or ("No curation issues detected.",):
        output.write(f"- {issue}\n")
    output.write("\n### Samples\n\n")
    output.write(
        "| sample_id | time_bce | sex | estimate | standard_error | "
        "qpadm_pvalue | publication_key | flags | site |\n"
    )
    output.write("| --- | ---: | --- | ---: | ---: | ---: | --- | --- | --- |\n")
    for sample in audit.samples:
        output.write(_sample_markdown_row(audit, sample))
    output.write("\n")


def _sample_markdown_row(
    audit: DisagreementTargetCurationAudit,
    sample: TargetCurationAuditSample,
) -> str:
    """Return one sample as a Markdown table row."""
    return (
        f"| {sample.sample_id} | {_optional_value_text(sample.time_bce)} | "
        f"{sample.sex or 'missing'} | {_optional_value_text(sample.estimate)} | "
        f"{_optional_value_text(sample.standard_error)} | "
        f"{_optional_value_text(sample.qpadm_pvalue)} | "
        f"{sample.publication_key or 'missing'} | "
        f"{', '.join(target_curation_sample_flags(audit, sample)) or 'none'} | "
        f"{_markdown_cell(sample.site)} |\n"
    )


def _times(samples: Iterable[TargetCurationAuditSample]) -> tuple[float, ...]:
    """Return present sample dates."""
    return tuple(sample.time_bce for sample in samples if sample.time_bce is not None)


def _range_text(values: tuple[float, ...]) -> str:
    """Return a compact min-max range or missing marker."""
    if not values:
        return "missing"
    return f"{_value_text(min(values))}-{_value_text(max(values))}"


def _curation_window_text(curation: TargetCurationRecord) -> str:
    """Return a compact BCE window for one curation record."""
    return f"{_value_text(curation.start_bce)}-{_value_text(curation.end_bce)}"


def _optional_value_text(value: float | None) -> str:
    """Return a compact value or missing marker."""
    return "missing" if value is None else _value_text(value)


def _value_text(value: float) -> str:
    """Return a stable compact numeric string."""
    return f"{value:.12g}"


def _markdown_cell(value: str) -> str:
    """Escape Markdown table separators in a text cell."""
    return value.replace("|", "\\|") if value else "missing"
