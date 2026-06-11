"""Markdown rendering for target curation audits."""

from __future__ import annotations

from collections.abc import Iterable
from io import StringIO
from pathlib import Path

from indoeuropop.data.target_curation import TargetCurationRecord
from indoeuropop.reporting.target_audit import (
    TargetCurationAudit,
    TargetCurationAuditSample,
)


def target_curation_audit_markdown(audit: TargetCurationAudit) -> str:
    """Return a Markdown report summarizing one target's curation evidence."""
    output = StringIO()
    output.write("# Target Curation Audit\n\n")
    output.write("## Target\n\n")
    output.write(f"- target_id: {audit.target_id}\n")
    output.write(f"- requested_group_id: {audit.requested_group_id or 'unknown'}\n")
    output.write(f"- region: {audit.residual.region}\n")
    output.write(f"- source: {audit.residual.source}\n")
    output.write(f"- time_bce: {_value_text(audit.residual.time_bce)}\n")
    output.write(f"- observed_mean: {_value_text(audit.residual.observed_mean)}\n")
    output.write(f"- predicted: {_value_text(audit.residual.predicted)}\n")
    output.write(f"- residual: {_value_text(audit.residual.residual)}\n")
    output.write(f"- z_score: {_value_text(audit.residual.z_score)}\n")
    output.write(f"- curation_window_bce: {_curation_window_text(audit.curation)}\n")
    output.write(f"- ancestry_method: {audit.curation.ancestry_method}\n")
    output.write(f"- aggregation_method: {audit.curation.aggregation_method}\n")
    output.write(f"- citation_key: {audit.curation.citation_key}\n")
    output.write("\n## Diagnostics\n\n")
    output.write(f"- curation_sample_count: {audit.curation.sample_count}\n")
    output.write(f"- joined_sample_count: {len(audit.samples)}\n")
    output.write(f"- missing_metadata_count: {len(audit.missing_metadata_ids)}\n")
    output.write(f"- missing_estimate_count: {len(audit.missing_estimate_ids)}\n")
    output.write(f"- metadata_time_range_bce: {_range_text(_times(audit.samples))}\n")
    output.write(f"- estimate_range: {_range_text(audit.estimates)}\n")
    output.write(f"- standard_error_range: {_range_text(audit.standard_errors)}\n")
    output.write(f"- qpadm_pvalue_range: {_range_text(audit.qpadm_pvalues)}\n")
    output.write(
        f"- all_estimates_identical: {_bool_text(audit.all_estimates_identical)}\n"
    )
    output.write(f"- sex_counts: {_counts_text(audit.sex_counts)}\n")
    output.write(f"- publication_keys: {', '.join(audit.publication_keys) or 'none'}\n")
    output.write(f"- recommendation: {audit.recommendation}\n")
    output.write("\n## Review Checks\n\n")
    for issue in audit.issues or ("No curation issues detected.",):
        output.write(f"- {issue}\n")
    output.write("\n## Samples\n\n")
    output.write(
        "| sample_id | time_bce | sex | estimate | standard_error | "
        "qpadm_pvalue | publication_key | site |\n"
    )
    output.write("| --- | ---: | --- | ---: | ---: | ---: | --- | --- |\n")
    for sample in audit.samples:
        output.write(_sample_row(sample))
    return output.getvalue()


def write_target_curation_audit_markdown(
    audit: TargetCurationAudit, path: str | Path
) -> Path:
    """Write a target curation audit report and return the output path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(target_curation_audit_markdown(audit), encoding="utf-8")
    return output_path


def _sample_row(sample: TargetCurationAuditSample) -> str:
    return (
        f"| {sample.sample_id} | {_optional_value_text(sample.time_bce)} | "
        f"{sample.sex or 'missing'} | {_optional_value_text(sample.estimate)} | "
        f"{_optional_value_text(sample.standard_error)} | "
        f"{_optional_value_text(sample.qpadm_pvalue)} | "
        f"{sample.publication_key or 'missing'} | {_markdown_cell(sample.site)} |\n"
    )


def _times(samples: Iterable[TargetCurationAuditSample]) -> tuple[float, ...]:
    return tuple(sample.time_bce for sample in samples if sample.time_bce is not None)


def _range_text(values: tuple[float, ...]) -> str:
    if not values:
        return "missing"
    return f"{_value_text(min(values))}-{_value_text(max(values))}"


def _counts_text(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}={counts[key]}" for key in sorted(counts))


def _curation_window_text(curation: TargetCurationRecord) -> str:
    return f"{_value_text(curation.start_bce)}-{_value_text(curation.end_bce)}"


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _optional_value_text(value: float | None) -> str:
    return "missing" if value is None else _value_text(value)


def _value_text(value: float) -> str:
    return f"{value:.12g}"


def _markdown_cell(value: str) -> str:
    return value.replace("|", "\\|") if value else "missing"
