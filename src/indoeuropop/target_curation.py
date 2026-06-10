"""Target curation metadata linking samples to target observations."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Literal, cast

from indoeuropop.sample_metadata import SampleMetadataDataset

CurationStatus = Literal["synthetic", "published"]

CURATION_STATUSES = frozenset({"synthetic", "published"})

REQUIRED_CURATION_COLUMNS = frozenset(
    {
        "status",
        "target_id",
        "region",
        "source",
        "start_bce",
        "end_bce",
        "sample_ids",
        "sample_count",
        "ancestry_method",
        "aggregation_method",
        "citation_key",
        "citation",
        "note",
    }
)


@dataclass(frozen=True)
class TargetCurationRecord:
    """Metadata documenting how a target observation should be curated."""

    status: CurationStatus
    target_id: str
    region: str
    source: str
    start_bce: float
    end_bce: float
    sample_ids: tuple[str, ...]
    sample_count: int
    ancestry_method: str
    aggregation_method: str
    citation_key: str
    citation: str
    note: str = ""

    def __post_init__(self) -> None:
        """Validate curation metadata fields."""
        if self.status not in CURATION_STATUSES:
            raise ValueError("status must be 'synthetic' or 'published'")
        for field_name in (
            "target_id",
            "region",
            "source",
            "ancestry_method",
            "aggregation_method",
            "citation_key",
            "citation",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must be non-empty")
        if not isfinite(self.start_bce) or not isfinite(self.end_bce):
            raise ValueError("start_bce and end_bce must be finite")
        if self.start_bce < self.end_bce:
            raise ValueError("start_bce must be greater than or equal to end_bce")
        if self.sample_count <= 0:
            raise ValueError("sample_count must be positive")
        if not self.sample_ids:
            raise ValueError("sample_ids must contain at least one sample")
        if len(set(self.sample_ids)) != len(self.sample_ids):
            raise ValueError("sample_ids must be unique within a target")
        if self.sample_count != len(self.sample_ids):
            raise ValueError("sample_count must match the number of sample_ids")


@dataclass(frozen=True)
class TargetCurationDataset:
    """A validated collection of target curation records."""

    records: tuple[TargetCurationRecord, ...]

    @classmethod
    def from_rows(cls, rows: Iterable[TargetCurationRecord]) -> TargetCurationDataset:
        """Build a dataset from validated curation records."""
        return cls(tuple(rows))

    def __post_init__(self) -> None:
        """Validate dataset-level uniqueness."""
        target_ids = [record.target_id for record in self.records]
        if len(set(target_ids)) != len(target_ids):
            raise ValueError("target_id values must be unique")

    def require_records(self) -> TargetCurationDataset:
        """Return this dataset after checking it contains at least one row."""
        if not self.records:
            raise ValueError("target curation dataset must contain at least one row")
        return self

    def target_ids(self) -> tuple[str, ...]:
        """Return target identifiers in dataset order."""
        return tuple(record.target_id for record in self.records)

    def regions(self) -> tuple[str, ...]:
        """Return unique region labels in record order."""
        return _unique(record.region for record in self.records)

    def sources(self) -> tuple[str, ...]:
        """Return unique source labels in record order."""
        return _unique(record.source for record in self.records)

    def sample_ids(self) -> tuple[str, ...]:
        """Return unique sample identifiers referenced by curation records."""
        return _unique(
            sample_id for record in self.records for sample_id in record.sample_ids
        )

    def filter(
        self,
        *,
        region: str | None = None,
        source: str | None = None,
        status: CurationStatus | None = None,
    ) -> TargetCurationDataset:
        """Return records matching optional region, source, and status filters."""
        return TargetCurationDataset.from_rows(
            record
            for record in self.records
            if (region is None or record.region == region)
            and (source is None or record.source == source)
            and (status is None or record.status == status)
        )

    def missing_sample_ids(
        self, sample_metadata: SampleMetadataDataset
    ) -> tuple[str, ...]:
        """Return referenced sample IDs absent from sample metadata."""
        available = {record.sample_id for record in sample_metadata.records}
        return tuple(
            sample_id for sample_id in self.sample_ids() if sample_id not in available
        )


def load_target_curation(path: str | Path) -> TargetCurationDataset:
    """Load target curation metadata from a CSV file."""
    curation_path = Path(path)
    with curation_path.open(newline="", encoding="utf-8") as curation_file:
        reader = csv.DictReader(curation_file)
        if reader.fieldnames is None:
            raise ValueError("target curation CSV must include a header row")
        missing_columns = REQUIRED_CURATION_COLUMNS.difference(reader.fieldnames)
        if missing_columns:
            missing_text = ", ".join(sorted(missing_columns))
            raise ValueError(f"target curation CSV missing columns: {missing_text}")
        records = [
            _record_from_row(row, line_number)
            for line_number, row in enumerate(reader, start=2)
        ]
    return TargetCurationDataset.from_rows(records).require_records()


def _record_from_row(
    row: dict[str, str | None], line_number: int
) -> TargetCurationRecord:
    """Convert one CSV row into target curation metadata."""
    try:
        return TargetCurationRecord(
            status=_status(_cell(row, "status")),
            target_id=_cell(row, "target_id"),
            region=_cell(row, "region"),
            source=_cell(row, "source"),
            start_bce=float(_cell(row, "start_bce")),
            end_bce=float(_cell(row, "end_bce")),
            sample_ids=_sample_ids(_cell(row, "sample_ids")),
            sample_count=int(_cell(row, "sample_count")),
            ancestry_method=_cell(row, "ancestry_method"),
            aggregation_method=_cell(row, "aggregation_method"),
            citation_key=_cell(row, "citation_key"),
            citation=_cell(row, "citation"),
            note=_optional_cell(row, "note"),
        )
    except ValueError as error:
        raise ValueError(
            f"invalid target curation CSV row {line_number}: {error}"
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


def _status(value: str) -> CurationStatus:
    """Validate and return a target curation status."""
    if value not in CURATION_STATUSES:
        raise ValueError("status must be 'synthetic' or 'published'")
    return cast(CurationStatus, value)


def _sample_ids(value: str) -> tuple[str, ...]:
    """Parse semicolon-delimited sample IDs from a CSV cell."""
    return tuple(
        sample_id.strip() for sample_id in value.split(";") if sample_id.strip()
    )


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    """Return unique strings while preserving insertion order."""
    unique_values: list[str] = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)
    return tuple(unique_values)
