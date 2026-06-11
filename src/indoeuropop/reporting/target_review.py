"""Markdown review helpers for target residual diagnostics."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from io import StringIO
from math import isfinite
from pathlib import Path
from typing import Any

TARGET_RESIDUAL_REVIEW_COLUMNS = (
    "target_index",
    "region",
    "source",
    "time_bce",
    "observed_mean",
    "uncertainty",
    "predicted",
    "residual",
    "z_score",
    "note",
)

REQUIRED_TARGET_RESIDUAL_REVIEW_COLUMNS = frozenset(TARGET_RESIDUAL_REVIEW_COLUMNS)


@dataclass(frozen=True)
class TargetResidualReviewRow:
    """One target residual row prepared for review reporting."""

    target_index: int
    region: str
    source: str
    time_bce: float
    observed_mean: float
    uncertainty: float
    predicted: float
    residual: float
    z_score: float
    requested_group_id: str
    note: str = ""

    def __post_init__(self) -> None:
        """Validate review-row fields."""
        if self.target_index <= 0:
            raise ValueError("target_index must be positive")
        for field_name in ("region", "source"):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must be non-empty")
        for field_name in (
            "time_bce",
            "observed_mean",
            "uncertainty",
            "predicted",
            "residual",
            "z_score",
        ):
            if not isfinite(getattr(self, field_name)):
                raise ValueError(f"{field_name} must be finite")
        if self.uncertainty <= 0:
            raise ValueError("uncertainty must be positive")

    @property
    def abs_z_score(self) -> float:
        """Return the absolute z-score for sorting outliers."""
        return abs(self.z_score)


@dataclass(frozen=True)
class TargetResidualRegionSummary:
    """Aggregate residual diagnostics for one modeled region."""

    region: str
    observation_count: int
    mean_abs_residual: float
    max_abs_z_score: float


@dataclass(frozen=True)
class TargetResidualReview:
    """A reviewable summary of target-comparison residuals."""

    rows: tuple[TargetResidualReviewRow, ...]
    outlier_z_threshold: float = 2.0
    diagnostics: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate review inputs."""
        if not self.rows:
            raise ValueError("rows must contain at least one residual")
        if not isfinite(self.outlier_z_threshold) or self.outlier_z_threshold <= 0:
            raise ValueError("outlier_z_threshold must be positive")

    @property
    def outliers(self) -> tuple[TargetResidualReviewRow, ...]:
        """Return residual rows beyond the absolute z-score threshold."""
        return tuple(
            row
            for row in self.ranked_rows
            if row.abs_z_score >= self.outlier_z_threshold
        )

    @property
    def ranked_rows(self) -> tuple[TargetResidualReviewRow, ...]:
        """Return residual rows sorted by descending absolute z-score."""
        return tuple(sorted(self.rows, key=lambda row: row.abs_z_score, reverse=True))

    @property
    def region_summaries(self) -> tuple[TargetResidualRegionSummary, ...]:
        """Return aggregate residual diagnostics by region."""
        summaries: list[TargetResidualRegionSummary] = []
        for region in _unique(row.region for row in self.rows):
            region_rows = tuple(row for row in self.rows if row.region == region)
            summaries.append(
                TargetResidualRegionSummary(
                    region=region,
                    observation_count=len(region_rows),
                    mean_abs_residual=sum(abs(row.residual) for row in region_rows)
                    / len(region_rows),
                    max_abs_z_score=max(row.abs_z_score for row in region_rows),
                )
            )
        return tuple(summaries)

    @property
    def recommendation(self) -> str:
        """Return a cautious next-step recommendation for the residual pattern."""
        if self.outliers:
            return (
                "Review qpAdm model choices and target curation before widening "
                "simulator parameter ranges."
            )
        if _diagnostic_int(self.diagnostics, "dropped_target_count") > len(self.rows):
            return (
                "Review dropped target rows before treating retained targets as "
                "representative."
            )
        return "Proceed to parameter-range refinement and held-out validation."


def load_target_residual_review(
    residuals_path: str | Path,
    *,
    diagnostics_path: str | Path | None = None,
    outlier_z_threshold: float = 2.0,
) -> TargetResidualReview:
    """Load residual CSV diagnostics and optional JSON target-build diagnostics."""
    diagnostics = (
        None if diagnostics_path is None else _load_json_mapping(diagnostics_path)
    )
    return TargetResidualReview(
        rows=load_target_residual_review_rows(residuals_path),
        diagnostics=diagnostics,
        outlier_z_threshold=outlier_z_threshold,
    )


def load_target_residual_review_rows(
    residuals_path: str | Path,
) -> tuple[TargetResidualReviewRow, ...]:
    """Load residual rows from a target-comparison CSV file."""
    path = Path(residuals_path)
    with path.open(newline="", encoding="utf-8") as residuals_file:
        reader = csv.DictReader(residuals_file)
        if reader.fieldnames is None:
            raise ValueError("target residual CSV must include a header row")
        missing_columns = REQUIRED_TARGET_RESIDUAL_REVIEW_COLUMNS.difference(
            reader.fieldnames
        )
        if missing_columns:
            missing_text = ", ".join(sorted(missing_columns))
            raise ValueError(f"target residual CSV missing columns: {missing_text}")
        rows = [
            _review_row_from_csv(row, line_number)
            for line_number, row in enumerate(reader, start=2)
        ]
    if not rows:
        raise ValueError("target residual CSV must contain at least one row")
    return tuple(rows)


def target_residual_review_markdown(review: TargetResidualReview) -> str:
    """Return a Markdown residual review report."""
    output = StringIO()
    top_row = review.ranked_rows[0]
    output.write("# Target Residual Review\n\n")
    output.write("## Summary\n\n")
    output.write(f"- residual_count: {len(review.rows)}\n")
    output.write(f"- outlier_z_threshold: {_value_text(review.outlier_z_threshold)}\n")
    output.write(f"- outlier_count: {len(review.outliers)}\n")
    output.write(f"- max_abs_z_score: {_value_text(top_row.abs_z_score)}\n")
    output.write(f"- top_outlier_group: {top_row.requested_group_id or 'unknown'}\n")
    output.write(f"- recommendation: {review.recommendation}\n")
    _write_diagnostics(output, review.diagnostics)
    output.write("\n## Region Summary\n\n")
    output.write("| region | observations | mean_abs_residual | max_abs_z_score |\n")
    output.write("| --- | ---: | ---: | ---: |\n")
    for summary in review.region_summaries:
        output.write(
            f"| {summary.region} | {summary.observation_count} | "
            f"{_value_text(summary.mean_abs_residual)} | "
            f"{_value_text(summary.max_abs_z_score)} |\n"
        )
    output.write("\n## Ranked Residuals\n\n")
    output.write(
        "| rank | region | requested_group_id | time_bce | observed | "
        "predicted | residual | z_score |\n"
    )
    output.write("| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |\n")
    for rank, row in enumerate(review.ranked_rows, start=1):
        output.write(
            f"| {rank} | {row.region} | {row.requested_group_id or 'unknown'} | "
            f"{_value_text(row.time_bce)} | {_value_text(row.observed_mean)} | "
            f"{_value_text(row.predicted)} | {_value_text(row.residual)} | "
            f"{_value_text(row.z_score)} |\n"
        )
    return output.getvalue()


def write_target_residual_review_markdown(
    review: TargetResidualReview, path: str | Path
) -> Path:
    """Write a target residual review report and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(target_residual_review_markdown(review), encoding="utf-8")
    return output_path


def _review_row_from_csv(
    row: Mapping[str, str | None], line_number: int
) -> TargetResidualReviewRow:
    """Convert one CSV row into a typed residual-review row."""
    note = _optional_cell(row, "note")
    try:
        return TargetResidualReviewRow(
            target_index=int(_required_cell(row, "target_index")),
            region=_required_cell(row, "region"),
            source=_required_cell(row, "source"),
            time_bce=float(_required_cell(row, "time_bce")),
            observed_mean=float(_required_cell(row, "observed_mean")),
            uncertainty=float(_required_cell(row, "uncertainty")),
            predicted=float(_required_cell(row, "predicted")),
            residual=float(_required_cell(row, "residual")),
            z_score=float(_required_cell(row, "z_score")),
            requested_group_id=_note_value(note, "requested_group_id"),
            note=note,
        )
    except ValueError as error:
        raise ValueError(
            f"invalid target residual CSV row {line_number}: {error}"
        ) from error


def _required_cell(row: Mapping[str, str | None], column: str) -> str:
    """Return a stripped required cell from a CSV row."""
    value = row.get(column)
    if value is None or value.strip() == "":
        raise ValueError(f"{column} is required")
    return value.strip()


def _optional_cell(row: Mapping[str, str | None], column: str) -> str:
    """Return a stripped optional cell from a CSV row."""
    value = row.get(column)
    return "" if value is None else value.strip()


def _note_value(note: str, key: str) -> str:
    """Return a semicolon-delimited note value for a key when present."""
    prefix = f"{key}="
    for part in note.split(";"):
        text = part.strip()
        if text.startswith(prefix):
            return text.removeprefix(prefix).strip()
    return ""


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    """Return unique values while preserving insertion order."""
    unique_values: list[str] = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)
    return tuple(unique_values)


def _load_json_mapping(path: str | Path) -> Mapping[str, Any]:
    """Load a JSON object from disk."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("target diagnostics JSON must contain an object")
    return payload


def _diagnostic_int(diagnostics: Mapping[str, Any] | None, key: str) -> int:
    """Return an integer diagnostics value when available."""
    if diagnostics is None:
        return 0
    value = diagnostics.get(key, 0)
    return int(value) if isinstance(value, int | float) else 0


def _write_diagnostics(output: StringIO, diagnostics: Mapping[str, Any] | None) -> None:
    """Write optional target-build diagnostics into a report buffer."""
    if diagnostics is None:
        return
    for key in (
        "requested_target_count",
        "retained_target_count",
        "dropped_target_count",
        "retained_sample_count",
        "target_observation_count",
    ):
        if key in diagnostics:
            output.write(f"- {key}: {diagnostics[key]}\n")


def _value_text(value: float) -> str:
    """Return a compact stable text representation for numeric output."""
    return f"{value:.12g}"
