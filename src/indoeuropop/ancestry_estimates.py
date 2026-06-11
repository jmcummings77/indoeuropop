"""Sample-level ancestry estimates before target aggregation."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Literal, cast

EstimateStatus = Literal["synthetic", "published"]

ESTIMATE_STATUSES = frozenset({"synthetic", "published"})

REQUIRED_ANCESTRY_ESTIMATE_COLUMNS = frozenset(
    {
        "status",
        "sample_id",
        "source",
        "estimate",
        "standard_error",
        "method",
        "note",
    }
)


@dataclass(frozen=True)
class SampleAncestryEstimate:
    """One sample-level ancestry estimate for a modeled source.

    `estimate` and `standard_error` are proportions. The estimate is the
    sample-level ancestry value, while `standard_error` is the one-sigma
    uncertainty used later when aggregating samples into target observations.
    """

    status: EstimateStatus
    sample_id: str
    source: str
    estimate: float
    standard_error: float
    method: str
    note: str = ""

    def __post_init__(self) -> None:
        """Validate sample ancestry estimate fields."""
        if self.status not in ESTIMATE_STATUSES:
            raise ValueError("status must be 'synthetic' or 'published'")
        for field_name in ("sample_id", "source", "method"):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must be non-empty")
        if not isfinite(self.estimate) or not 0 <= self.estimate <= 1:
            raise ValueError("estimate must be a finite proportion")
        if (
            not isfinite(self.standard_error)
            or self.standard_error <= 0
            or self.standard_error > 1
        ):
            raise ValueError("standard_error must be a positive finite proportion")


@dataclass(frozen=True)
class SampleAncestryEstimateDataset:
    """A validated collection of sample-level ancestry estimates."""

    estimates: tuple[SampleAncestryEstimate, ...]

    @classmethod
    def from_rows(
        cls, rows: Iterable[SampleAncestryEstimate]
    ) -> SampleAncestryEstimateDataset:
        """Build a dataset from already validated estimate rows."""
        return cls(tuple(rows))

    def __post_init__(self) -> None:
        """Validate dataset-level estimate identity."""
        keys = [
            (estimate.sample_id, estimate.source, estimate.method)
            for estimate in self.estimates
        ]
        if len(set(keys)) != len(keys):
            raise ValueError(
                "sample_id, source, and method combinations must be unique"
            )

    @property
    def estimate_count(self) -> int:
        """Return the number of sample ancestry estimates."""
        return len(self.estimates)

    def require_estimates(self) -> SampleAncestryEstimateDataset:
        """Return this dataset after checking it contains at least one row."""
        if not self.estimates:
            raise ValueError("sample ancestry dataset must contain at least one row")
        return self

    def sample_ids(self) -> tuple[str, ...]:
        """Return unique sample IDs in estimate order."""
        return _unique(estimate.sample_id for estimate in self.estimates)

    def sources(self) -> tuple[str, ...]:
        """Return unique source labels in estimate order."""
        return _unique(estimate.source for estimate in self.estimates)

    def methods(self) -> tuple[str, ...]:
        """Return unique ancestry-estimation methods in estimate order."""
        return _unique(estimate.method for estimate in self.estimates)

    def filter(
        self,
        *,
        sample_id: str | None = None,
        source: str | None = None,
        method: str | None = None,
        status: EstimateStatus | None = None,
    ) -> SampleAncestryEstimateDataset:
        """Return estimates matching optional identity and status filters."""
        return SampleAncestryEstimateDataset.from_rows(
            estimate
            for estimate in self.estimates
            if (sample_id is None or estimate.sample_id == sample_id)
            and (source is None or estimate.source == source)
            and (method is None or estimate.method == method)
            and (status is None or estimate.status == status)
        )

    def estimate_for(
        self,
        *,
        sample_id: str,
        source: str,
        method: str,
    ) -> SampleAncestryEstimate:
        """Return one estimate by sample, source, and method."""
        matches = self.filter(
            sample_id=sample_id,
            source=source,
            method=method,
        ).estimates
        if not matches:
            raise ValueError(
                "missing ancestry estimate for "
                f"sample_id={sample_id}, source={source}, method={method}"
            )
        return matches[0]


def load_sample_ancestry_estimates(path: str | Path) -> SampleAncestryEstimateDataset:
    """Load sample-level ancestry estimates from a CSV file."""
    estimate_path = Path(path)
    with estimate_path.open(newline="", encoding="utf-8") as estimate_file:
        reader = csv.DictReader(estimate_file)
        if reader.fieldnames is None:
            raise ValueError("sample ancestry CSV must include a header row")
        missing_columns = REQUIRED_ANCESTRY_ESTIMATE_COLUMNS.difference(
            reader.fieldnames
        )
        if missing_columns:
            missing_text = ", ".join(sorted(missing_columns))
            raise ValueError(f"sample ancestry CSV missing columns: {missing_text}")
        estimates = [
            _estimate_from_row(row, line_number)
            for line_number, row in enumerate(reader, start=2)
        ]
    return SampleAncestryEstimateDataset.from_rows(estimates).require_estimates()


def _estimate_from_row(
    row: dict[str, str | None], line_number: int
) -> SampleAncestryEstimate:
    """Convert one CSV row into a sample ancestry estimate."""
    try:
        return SampleAncestryEstimate(
            status=_status(_cell(row, "status")),
            sample_id=_cell(row, "sample_id"),
            source=_cell(row, "source"),
            estimate=float(_cell(row, "estimate")),
            standard_error=float(_cell(row, "standard_error")),
            method=_cell(row, "method"),
            note=_optional_cell(row, "note"),
        )
    except ValueError as error:
        raise ValueError(
            f"invalid sample ancestry CSV row {line_number}: {error}"
        ) from error


def _cell(row: dict[str, str | None], column: str) -> str:
    """Return a stripped required CSV cell."""
    value = row.get(column)
    if value is None or value.strip() == "":
        raise ValueError(f"{column} is required")
    return value.strip()


def _optional_cell(row: dict[str, str | None], column: str) -> str:
    """Return a stripped optional CSV cell."""
    value = row.get(column)
    if value is None:
        return ""
    return value.strip()


def _status(value: str) -> EstimateStatus:
    """Validate and return an ancestry-estimate status."""
    if value not in ESTIMATE_STATUSES:
        raise ValueError("status must be 'synthetic' or 'published'")
    return cast(EstimateStatus, value)


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    """Return unique strings while preserving insertion order."""
    unique_values: list[str] = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)
    return tuple(unique_values)
