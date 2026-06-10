"""Sample metadata records for future ancient-DNA ingestion."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Literal, cast

SampleMetadataStatus = Literal["synthetic", "published"]
SampleSex = Literal["female", "male", "unknown", "not_reported"]

SAMPLE_METADATA_STATUSES = frozenset({"synthetic", "published"})
SAMPLE_SEX_LABELS = frozenset({"female", "male", "unknown", "not_reported"})

REQUIRED_SAMPLE_METADATA_COLUMNS = frozenset(
    {
        "status",
        "dataset_id",
        "sample_id",
        "accession_id",
        "publication_key",
        "publication",
        "region",
        "site",
        "time_bce",
        "date_uncertainty",
        "sex",
        "method",
        "note",
    }
)


@dataclass(frozen=True)
class SampleMetadataRecord:
    """One ancient-DNA sample metadata row before regional aggregation."""

    status: SampleMetadataStatus
    dataset_id: str
    sample_id: str
    accession_id: str
    publication_key: str
    publication: str
    region: str
    site: str
    time_bce: float
    date_uncertainty: float
    sex: SampleSex
    method: str
    note: str = ""

    def __post_init__(self) -> None:
        """Validate sample metadata fields."""
        if self.status not in SAMPLE_METADATA_STATUSES:
            raise ValueError("status must be 'synthetic' or 'published'")
        if self.sex not in SAMPLE_SEX_LABELS:
            raise ValueError("sex label is not supported")
        for field_name in (
            "dataset_id",
            "sample_id",
            "accession_id",
            "publication_key",
            "publication",
            "region",
            "site",
            "method",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must be non-empty")
        if not isfinite(self.time_bce):
            raise ValueError("time_bce must be finite")
        if not isfinite(self.date_uncertainty) or self.date_uncertainty < 0:
            raise ValueError("date_uncertainty must be finite and non-negative")


@dataclass(frozen=True)
class RegionSampleCount:
    """Count of metadata rows for one modeled region."""

    region: str
    sample_count: int


@dataclass(frozen=True)
class SampleMetadataDataset:
    """A validated collection of sample metadata records."""

    records: tuple[SampleMetadataRecord, ...]

    @classmethod
    def from_rows(cls, rows: Iterable[SampleMetadataRecord]) -> SampleMetadataDataset:
        """Build a dataset from already validated sample metadata rows."""
        return cls(tuple(rows))

    def __post_init__(self) -> None:
        """Validate dataset-level uniqueness."""
        keys = [(record.dataset_id, record.sample_id) for record in self.records]
        if len(set(keys)) != len(keys):
            raise ValueError("sample_id values must be unique within each dataset")

    @property
    def sample_count(self) -> int:
        """Return the number of sample metadata records."""
        return len(self.records)

    def require_records(self) -> SampleMetadataDataset:
        """Return this dataset after checking it contains at least one row."""
        if not self.records:
            raise ValueError("sample metadata dataset must contain at least one row")
        return self

    def dataset_ids(self) -> tuple[str, ...]:
        """Return unique data-source identifiers in record order."""
        return _unique(record.dataset_id for record in self.records)

    def regions(self) -> tuple[str, ...]:
        """Return unique modeled region labels in record order."""
        return _unique(record.region for record in self.records)

    def publication_keys(self) -> tuple[str, ...]:
        """Return unique publication identifiers in record order."""
        return _unique(record.publication_key for record in self.records)

    def filter(
        self,
        *,
        dataset_id: str | None = None,
        region: str | None = None,
        status: SampleMetadataStatus | None = None,
    ) -> SampleMetadataDataset:
        """Return records matching optional dataset, region, and status filters."""
        return SampleMetadataDataset.from_rows(
            record
            for record in self.records
            if (dataset_id is None or record.dataset_id == dataset_id)
            and (region is None or record.region == region)
            and (status is None or record.status == status)
        )

    def counts_by_region(self) -> tuple[RegionSampleCount, ...]:
        """Return sample counts grouped by modeled region."""
        counts: dict[str, int] = {}
        for record in self.records:
            counts[record.region] = counts.get(record.region, 0) + 1
        return tuple(
            RegionSampleCount(region=region, sample_count=count)
            for region, count in counts.items()
        )

    def time_range_bce(self) -> tuple[float, float]:
        """Return the minimum and maximum sample dates in BCE."""
        self.require_records()
        times = [record.time_bce for record in self.records]
        return min(times), max(times)


def load_sample_metadata(path: str | Path) -> SampleMetadataDataset:
    """Load sample metadata from a CSV file."""
    metadata_path = Path(path)
    with metadata_path.open(newline="", encoding="utf-8") as metadata_file:
        reader = csv.DictReader(metadata_file)
        if reader.fieldnames is None:
            raise ValueError("sample metadata CSV must include a header row")
        missing_columns = REQUIRED_SAMPLE_METADATA_COLUMNS.difference(reader.fieldnames)
        if missing_columns:
            missing_text = ", ".join(sorted(missing_columns))
            raise ValueError(f"sample metadata CSV missing columns: {missing_text}")
        records = [
            _record_from_row(row, line_number)
            for line_number, row in enumerate(reader, start=2)
        ]
    return SampleMetadataDataset.from_rows(records).require_records()


def _record_from_row(
    row: dict[str, str | None], line_number: int
) -> SampleMetadataRecord:
    """Convert one CSV row into a sample metadata record."""
    try:
        return SampleMetadataRecord(
            status=_status(_cell(row, "status")),
            dataset_id=_cell(row, "dataset_id"),
            sample_id=_cell(row, "sample_id"),
            accession_id=_cell(row, "accession_id"),
            publication_key=_cell(row, "publication_key"),
            publication=_cell(row, "publication"),
            region=_cell(row, "region"),
            site=_cell(row, "site"),
            time_bce=float(_cell(row, "time_bce")),
            date_uncertainty=float(_cell(row, "date_uncertainty")),
            sex=_sex(_cell(row, "sex")),
            method=_cell(row, "method"),
            note=_optional_cell(row, "note"),
        )
    except ValueError as error:
        raise ValueError(
            f"invalid sample metadata CSV row {line_number}: {error}"
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


def _status(value: str) -> SampleMetadataStatus:
    """Validate and return a sample metadata status."""
    if value not in SAMPLE_METADATA_STATUSES:
        raise ValueError("status must be 'synthetic' or 'published'")
    return cast(SampleMetadataStatus, value)


def _sex(value: str) -> SampleSex:
    """Validate and return a sample sex label."""
    if value not in SAMPLE_SEX_LABELS:
        raise ValueError("sex label is not supported")
    return cast(SampleSex, value)


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    """Return unique strings while preserving insertion order."""
    unique_values: list[str] = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)
    return tuple(unique_values)
