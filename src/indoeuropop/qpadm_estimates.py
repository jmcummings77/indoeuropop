"""Convert qpAdm-style ancestry tables into project estimate CSVs."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import cast

from indoeuropop.ancestry_estimates import (
    EstimateStatus,
    SampleAncestryEstimate,
    SampleAncestryEstimateDataset,
    write_sample_ancestry_estimates_csv,
)

DEFAULT_QPADM_SOURCE = "steppe"
DEFAULT_QPADM_METHOD = "qpadm_steppe"

_SAMPLE_ID_NAMES = frozenset({"id", "sample id", "sample_id", "genetic id"})
_STEPPE_NAMES = frozenset(
    {"steppe", "steppe fraction", "steppe_fraction", "steppe weight"}
)
_STANDARD_ERROR_NAMES = frozenset(
    {"se", "stderr", "std err", "std_err", "standard error", "standard_error"}
)
_PVALUE_NAMES = frozenset(
    {"p", "pvalue", "p value", "p_value", "p-value", "qpadm pvalue", "qpadm_pvalue"}
)


@dataclass(frozen=True)
class QpAdmEstimate:
    """One externally computed qpAdm-style steppe ancestry estimate."""

    sample_id: str
    steppe_fraction: float
    standard_error: float | None = None
    p_value: float | None = None

    def __post_init__(self) -> None:
        """Validate qpAdm estimate fields."""
        if not self.sample_id:
            raise ValueError("sample_id must be non-empty")
        if not isfinite(self.steppe_fraction) or not 0 <= self.steppe_fraction <= 1:
            raise ValueError("steppe_fraction must be a finite proportion")
        if self.standard_error is not None and (
            not isfinite(self.standard_error)
            or self.standard_error <= 0
            or self.standard_error > 1
        ):
            raise ValueError("standard_error must be a positive finite proportion")
        if self.p_value is not None and (
            not isfinite(self.p_value) or not 0 <= self.p_value <= 1
        ):
            raise ValueError("p_value must be a finite proportion")


def load_qpadm_estimate_table(path: str | Path) -> tuple[QpAdmEstimate, ...]:
    """Load qpAdm-style estimates from a CSV or TSV file."""
    table_path = Path(path)
    with table_path.open(newline="", encoding="utf-8") as estimate_file:
        return parse_qpadm_estimate_table(estimate_file)


def parse_qpadm_estimate_table(lines: Iterable[str]) -> tuple[QpAdmEstimate, ...]:
    """Parse a qpAdm-style table into estimates keyed by first occurrence.

    The parser accepts comma- or tab-separated tables. It requires a sample ID
    column and a steppe-fraction column. Standard error and qpAdm p-value columns
    are optional, but standard errors are required later unless a default is
    supplied during conversion into the project estimate schema.
    """
    line_tuple = tuple(line for line in lines if line.strip())
    if not line_tuple:
        raise ValueError("qpAdm estimate table must contain a header row")
    delimiter = "\t" if "\t" in line_tuple[0] else ","
    reader = csv.DictReader(line_tuple, delimiter=delimiter)
    columns = _qpadm_columns(list(reader.fieldnames or ()))
    estimates_by_id: dict[str, QpAdmEstimate] = {}
    for row in reader:
        estimate = _estimate_from_qpadm_row(row, columns)
        if estimate is None or estimate.sample_id in estimates_by_id:
            continue
        estimates_by_id[estimate.sample_id] = estimate
    return tuple(estimates_by_id.values())


def load_qpadm_sample_ancestry_estimates(
    path: str | Path,
    *,
    source: str = DEFAULT_QPADM_SOURCE,
    method: str = DEFAULT_QPADM_METHOD,
    default_standard_error: float | None = None,
    status: EstimateStatus = "published",
) -> SampleAncestryEstimateDataset:
    """Load a qpAdm-style table as project sample ancestry estimates."""
    return qpadm_estimates_to_sample_ancestry_dataset(
        load_qpadm_estimate_table(path),
        source=source,
        method=method,
        default_standard_error=default_standard_error,
        status=status,
    )


def qpadm_estimates_to_sample_ancestry_dataset(
    estimates: Iterable[QpAdmEstimate],
    *,
    source: str = DEFAULT_QPADM_SOURCE,
    method: str = DEFAULT_QPADM_METHOD,
    default_standard_error: float | None = None,
    status: EstimateStatus = "published",
) -> SampleAncestryEstimateDataset:
    """Convert qpAdm estimates into the target-pipeline estimate schema."""
    estimate_rows = tuple(
        _sample_ancestry_estimate(
            estimate,
            source=source,
            method=method,
            default_standard_error=default_standard_error,
            status=status,
        )
        for estimate in estimates
    )
    return SampleAncestryEstimateDataset.from_rows(estimate_rows).require_estimates()


def write_qpadm_sample_ancestry_estimates_csv(
    table_path: str | Path,
    output_path: str | Path,
    *,
    source: str = DEFAULT_QPADM_SOURCE,
    method: str = DEFAULT_QPADM_METHOD,
    default_standard_error: float | None = None,
    status: EstimateStatus = "published",
) -> Path:
    """Convert a qpAdm-style table and write project sample estimates."""
    return write_sample_ancestry_estimates_csv(
        load_qpadm_sample_ancestry_estimates(
            table_path,
            source=source,
            method=method,
            default_standard_error=default_standard_error,
            status=status,
        ),
        output_path,
    )


def _qpadm_columns(fieldnames: list[str]) -> dict[str, str | None]:
    """Resolve qpAdm table columns by tolerant header matching."""
    sample_column = _column_by_name(fieldnames, _SAMPLE_ID_NAMES)
    steppe_column = _column_by_name(fieldnames, _STEPPE_NAMES)
    if sample_column is None or steppe_column is None:
        raise ValueError("qpAdm table must include sample ID and steppe columns")
    return {
        "sample_id": sample_column,
        "steppe_fraction": steppe_column,
        "standard_error": _column_by_name(fieldnames, _STANDARD_ERROR_NAMES),
        "p_value": _column_by_name(fieldnames, _PVALUE_NAMES),
    }


def _column_by_name(
    fieldnames: list[str],
    expected_names: frozenset[str],
) -> str | None:
    """Return the first field whose normalized name matches expected names."""
    for fieldname in fieldnames:
        normalized = _normalized_name(fieldname)
        if normalized in expected_names:
            return fieldname
    for fieldname in fieldnames:
        normalized = _normalized_name(fieldname)
        if any(name in normalized for name in expected_names if len(name) > 2):
            return fieldname
    return None


def _estimate_from_qpadm_row(
    row: dict[str, str | None],
    columns: dict[str, str | None],
) -> QpAdmEstimate | None:
    """Convert one tolerant qpAdm row, returning `None` for unusable rows."""
    sample_id = _optional_cell(row, cast(str, columns["sample_id"]))
    steppe_fraction = _optional_float(row, cast(str, columns["steppe_fraction"]))
    if not sample_id or steppe_fraction is None or not 0 <= steppe_fraction <= 1:
        return None
    return QpAdmEstimate(
        sample_id=sample_id,
        steppe_fraction=steppe_fraction,
        standard_error=_optional_float(row, columns["standard_error"]),
        p_value=_optional_float(row, columns["p_value"]),
    )


def _sample_ancestry_estimate(
    estimate: QpAdmEstimate,
    *,
    source: str,
    method: str,
    default_standard_error: float | None,
    status: EstimateStatus,
) -> SampleAncestryEstimate:
    """Convert one qpAdm estimate into the project estimate dataclass."""
    standard_error = (
        estimate.standard_error
        if estimate.standard_error is not None
        else default_standard_error
    )
    if standard_error is None:
        raise ValueError(
            f"qpAdm estimate for {estimate.sample_id} is missing standard error"
        )
    return SampleAncestryEstimate(
        status=status,
        sample_id=estimate.sample_id,
        source=source,
        estimate=estimate.steppe_fraction,
        standard_error=standard_error,
        method=method,
        note=_qpadm_note(estimate),
    )


def _qpadm_note(estimate: QpAdmEstimate) -> str:
    """Return a compact provenance note for one qpAdm estimate."""
    if estimate.p_value is None:
        return "source_table=qpAdm"
    return f"source_table=qpAdm; qpadm_pvalue={estimate.p_value:.12g}"


def _optional_cell(row: dict[str, str | None], column: str) -> str:
    """Return a stripped optional cell from a resolved qpAdm column."""
    value = row.get(column)
    if value is None:
        return ""
    return value.strip()


def _optional_float(row: dict[str, str | None], column: str | None) -> float | None:
    """Parse an optional float cell, returning `None` for placeholders."""
    if column is None:
        return None
    value = _optional_cell(row, column)
    if value in {"", ".."} or value.lower() in {"n/a", "na"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _normalized_name(value: str) -> str:
    """Normalize a header name for tolerant qpAdm column matching."""
    return " ".join(value.replace("_", " ").replace("-", " ").lower().split())
