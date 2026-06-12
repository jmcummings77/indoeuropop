"""Diagnostics for structural SMC validation disagreement folds."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from io import StringIO
from pathlib import Path

from indoeuropop.data.target_notes import target_note_metadata
from indoeuropop.data.targets import TargetObservation, load_target_dataset
from indoeuropop.reporting.structural_smc_disagreement_models import (
    REQUIRED_POSTERIOR_PREDICTIVE_COLUMNS,
    REQUIRED_VALIDATION_SUMMARY_COLUMNS,
    STRUCTURAL_SMC_DISAGREEMENT_FIELDS,
    StructuralSMCDisagreementReport,
    StructuralSMCDisagreementRow,
    required_cell,
)


def load_structural_smc_disagreement_report(
    summary_csv: str | Path,
    validation_output_dir: str | Path,
) -> StructuralSMCDisagreementReport:
    """Load disagreement folds and join target and posterior-predictive rows."""
    root = Path(validation_output_dir)
    rows: list[StructuralSMCDisagreementRow] = []
    for summary in _load_disagreement_summaries(summary_csv):
        rows.extend(_fold_rows(root, summary))
    return StructuralSMCDisagreementReport(tuple(rows))


def structural_smc_disagreement_rows(
    report: StructuralSMCDisagreementReport,
) -> tuple[dict[str, str], ...]:
    """Return disagreement diagnostics as CSV-ready rows."""
    return tuple(_row_payload(row) for row in report.rows)


def structural_smc_disagreement_to_csv(
    report: StructuralSMCDisagreementReport,
) -> str:
    """Return disagreement diagnostics serialized as CSV text."""
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=STRUCTURAL_SMC_DISAGREEMENT_FIELDS,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(structural_smc_disagreement_rows(report))
    return output.getvalue()


def write_structural_smc_disagreement_csv(
    report: StructuralSMCDisagreementReport,
    path: str | Path,
) -> Path:
    """Write disagreement diagnostics to CSV and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(structural_smc_disagreement_to_csv(report), encoding="utf-8")
    return output_path


def structural_smc_disagreement_markdown(
    report: StructuralSMCDisagreementReport,
) -> str:
    """Return a Markdown report for structural SMC disagreement diagnostics."""
    output = StringIO()
    output.write("# Structural SMC Disagreement Diagnostics\n\n")
    output.write(
        "This report joins disagreement folds to held-out target metadata and "
        "posterior-predictive residuals. Positive child-minus-pulse residual "
        "deltas mean the child override fit that held-out target worse.\n\n"
    )
    output.write(_summary_markdown(report))
    output.write(_fold_markdown(report))
    output.write(_target_markdown(report))
    output.write("## Interpretation Guardrail\n\n")
    output.write(
        "Use these rows to decide whether disagreement reflects fragile target "
        "construction, high uncertainty, small sample counts, or a real need for "
        "a separate structural mechanism. Do not promote either candidate from "
        "the aggregate fold count alone.\n"
    )
    return output.getvalue()


def write_structural_smc_disagreement_markdown(
    report: StructuralSMCDisagreementReport,
    path: str | Path,
) -> Path:
    """Write a disagreement Markdown report and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        structural_smc_disagreement_markdown(report), encoding="utf-8"
    )
    return output_path


def _load_disagreement_summaries(path: str | Path) -> tuple[Mapping[str, str], ...]:
    """Load validation summary rows marked as preference disagreements."""
    with Path(path).open(newline="", encoding="utf-8") as summary_file:
        reader = csv.DictReader(summary_file)
        if reader.fieldnames is None:
            raise ValueError("validation summary CSV must include a header row")
        missing = REQUIRED_VALIDATION_SUMMARY_COLUMNS.difference(reader.fieldnames)
        if missing:
            raise ValueError(
                "validation summary CSV missing columns: " + ", ".join(sorted(missing))
            )
        return tuple(
            dict(row)
            for row in reader
            if required_cell(row, "preference_disagreement") == "true"
        )


def _fold_rows(
    root: Path,
    summary: Mapping[str, str],
) -> tuple[StructuralSMCDisagreementRow, ...]:
    """Return joined target and predictive rows for one disagreement fold."""
    fold_dir = root / required_cell(summary, "fold_name")
    targets = load_target_dataset(fold_dir / "holdout-targets.csv")
    baseline = _load_predictive_rows(
        fold_dir / "smc-baseline-holdout-posterior-predictive.csv"
    )
    pulse = _load_predictive_rows(
        fold_dir / "smc-structured-pulse-holdout-posterior-predictive.csv"
    )
    child = _load_predictive_rows(
        fold_dir / "smc-child-override-holdout-posterior-predictive.csv"
    )
    return tuple(
        _joined_row(summary, index, observation, baseline, pulse, child)
        for index, observation in enumerate(targets.observations)
    )


def _joined_row(
    summary: Mapping[str, str],
    index: int,
    observation: TargetObservation,
    baseline: Mapping[int, Mapping[str, str]],
    pulse: Mapping[int, Mapping[str, str]],
    child: Mapping[int, Mapping[str, str]],
) -> StructuralSMCDisagreementRow:
    """Return one joined disagreement target row."""
    metadata = target_note_metadata(observation.note)
    return StructuralSMCDisagreementRow(
        fold_name=required_cell(summary, "fold_name"),
        categories=required_cell(summary, "categories"),
        calibration_preferred_candidate=required_cell(
            summary, "calibration_preferred_candidate"
        ),
        holdout_preferred_candidate=required_cell(
            summary, "holdout_preferred_candidate"
        ),
        fold_holdout_delta=float(
            required_cell(summary, "holdout_child_minus_structured_pulse_rmse_delta")
        ),
        target_index=index,
        target_id=metadata.get("target_id", ""),
        requested_group_id=metadata.get("requested_group_id", ""),
        matched_group_ids=metadata.get("matched_group_ids", ""),
        publication_keys=metadata.get("publication_keys", ""),
        sample_count=_optional_int(metadata.get("sample_count", "")),
        window_bce=metadata.get("window_bce", ""),
        aggregation_method=metadata.get("aggregation_method", ""),
        group_match_mode=metadata.get("group_match_mode", ""),
        observation=observation,
        baseline=baseline[index],
        structured_pulse=pulse[index],
        child_override=child[index],
    )


def _load_predictive_rows(path: Path) -> Mapping[int, Mapping[str, str]]:
    """Load posterior-predictive rows keyed by observation index."""
    with path.open(newline="", encoding="utf-8") as predictive_file:
        reader = csv.DictReader(predictive_file)
        if reader.fieldnames is None:
            raise ValueError("posterior predictive CSV must include a header row")
        missing = REQUIRED_POSTERIOR_PREDICTIVE_COLUMNS.difference(reader.fieldnames)
        if missing:
            raise ValueError(
                "posterior predictive CSV missing columns: "
                + ", ".join(sorted(missing))
            )
        return {
            int(required_cell(row, "observation_index")): dict(row) for row in reader
        }


def _row_payload(row: StructuralSMCDisagreementRow) -> dict[str, str]:
    """Return one disagreement row as string-only CSV fields."""
    return {
        **_identity_payload(row),
        **_target_payload(row),
        **_predictive_payload(row),
    }


def _identity_payload(row: StructuralSMCDisagreementRow) -> dict[str, str]:
    """Return fold and qpAdm metadata fields for one row."""
    return {
        "fold_name": row.fold_name,
        "categories": row.categories,
        "calibration_preferred_candidate": row.calibration_preferred_candidate,
        "holdout_preferred_candidate": row.holdout_preferred_candidate,
        "fold_holdout_child_minus_structured_pulse_rmse_delta": _value_text(
            row.fold_holdout_delta
        ),
        "target_index": str(row.target_index),
        "target_id": row.target_id,
        "requested_group_id": row.requested_group_id,
        "matched_group_ids": row.matched_group_ids,
        "publication_keys": row.publication_keys,
        "sample_count": "" if row.sample_count is None else str(row.sample_count),
        "window_bce": row.window_bce,
        "aggregation_method": row.aggregation_method,
        "group_match_mode": row.group_match_mode,
    }


def _target_payload(row: StructuralSMCDisagreementRow) -> dict[str, str]:
    """Return target observation fields for one row."""
    return {
        "region": row.observation.region,
        "source": row.observation.source,
        "time_bce": _value_text(row.observation.time_bce),
        "observed_mean": _value_text(row.observation.mean),
        "uncertainty": _value_text(row.observation.uncertainty),
        "citation_key": row.observation.citation_key,
        "citation": row.observation.citation,
    }


def _predictive_payload(row: StructuralSMCDisagreementRow) -> dict[str, str]:
    """Return posterior-predictive fields for one row."""
    return {
        "baseline_prediction_mean": _value_text(row.baseline_prediction_mean),
        "baseline_mean_residual": _value_text(row.baseline_mean_residual),
        "baseline_absolute_mean_residual": _value_text(
            row.baseline_absolute_mean_residual
        ),
        "structured_pulse_prediction_mean": _value_text(
            row.structured_pulse_prediction_mean
        ),
        "structured_pulse_mean_residual": _value_text(
            row.structured_pulse_mean_residual
        ),
        "structured_pulse_absolute_mean_residual": _value_text(
            row.structured_pulse_absolute_mean_residual
        ),
        "structured_pulse_observed_inside_interval": required_cell(
            row.structured_pulse, "observed_inside_interval"
        ),
        "child_override_prediction_mean": _value_text(
            row.child_override_prediction_mean
        ),
        "child_override_mean_residual": _value_text(row.child_override_mean_residual),
        "child_override_absolute_mean_residual": _value_text(
            row.child_override_absolute_mean_residual
        ),
        "child_override_observed_inside_interval": required_cell(
            row.child_override, "observed_inside_interval"
        ),
        "child_minus_structured_pulse_prediction_delta": _value_text(
            row.child_minus_structured_pulse_prediction_delta
        ),
        "child_minus_structured_pulse_abs_residual_delta": _value_text(
            row.child_minus_structured_pulse_abs_residual_delta
        ),
        "target_preferred_candidate": row.target_preferred_candidate,
    }


def _summary_markdown(report: StructuralSMCDisagreementReport) -> str:
    """Return report summary bullets."""
    return (
        "## Summary\n\n"
        f"- disagreement_fold_count: {report.disagreement_fold_count}\n"
        f"- joined_target_count: {report.target_count}\n"
        f"- structured_pulse_target_count: {report.structured_pulse_target_count}\n"
        f"- child_override_target_count: {report.child_override_target_count}\n\n"
    )


def _fold_markdown(report: StructuralSMCDisagreementReport) -> str:
    """Return fold-level disagreement summary table."""
    output = StringIO()
    output.write("## Disagreement Folds\n\n")
    output.write("| Fold | Categories | Targets | Fold holdout delta |\n")
    output.write("| --- | --- | ---: | ---: |\n")
    for fold_name in _unique(row.fold_name for row in report.rows):
        rows = tuple(row for row in report.rows if row.fold_name == fold_name)
        output.write(
            f"| {fold_name} | {rows[0].categories} | {len(rows)} | "
            f"{_value_text(rows[0].fold_holdout_delta)} |\n"
        )
    output.write("\n")
    return output.getvalue()


def _target_markdown(report: StructuralSMCDisagreementReport) -> str:
    """Return target-level disagreement table sorted by residual delta."""
    output = StringIO()
    output.write("## Target Diagnostics\n\n")
    output.write(
        "| Fold | requested_group_id | sample_count | publication_keys | "
        "uncertainty | pulse_abs_residual | child_abs_residual | "
        "child_minus_pulse_abs_delta | target_preference |\n"
    )
    output.write("| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- |\n")
    for row in report.ranked_rows:
        sample_count = "" if row.sample_count is None else str(row.sample_count)
        output.write(
            f"| {row.fold_name} | {row.requested_group_id or 'unknown'} | "
            f"{sample_count} | {row.publication_keys or 'unknown'} | "
            f"{_value_text(row.observation.uncertainty)} | "
            f"{_value_text(row.structured_pulse_absolute_mean_residual)} | "
            f"{_value_text(row.child_override_absolute_mean_residual)} | "
            f"{_value_text(row.child_minus_structured_pulse_abs_residual_delta)} | "
            f"{row.target_preferred_candidate} |\n"
        )
    output.write("\n")
    return output.getvalue()


def _optional_int(value: str) -> int | None:
    """Return an optional integer parsed from target-note metadata."""
    text = value.strip()
    return None if not text else int(text)


def _value_text(value: float) -> str:
    """Return a stable numeric string for reports."""
    return f"{value:.12g}"


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    """Return unique values while preserving order."""
    unique_values: list[str] = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)
    return tuple(unique_values)
