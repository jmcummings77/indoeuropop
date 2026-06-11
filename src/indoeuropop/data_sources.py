"""Catalogs for external and local research data sources."""

from __future__ import annotations

import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, cast

DataSourceKind = Literal["target_csv", "sample_metadata_csv", "aadr", "poseidon"]
DataSourceStatus = Literal["planned", "local", "external"]

DATA_SOURCE_KINDS = frozenset({"target_csv", "sample_metadata_csv", "aadr", "poseidon"})
DATA_SOURCE_STATUSES = frozenset({"planned", "local", "external"})


@dataclass(frozen=True)
class DataSourceRecord:
    """Metadata for one research data source.

    A record describes where data came from or where a future ingestion layer
    should look. It does not imply the data have been downloaded, curated, or
    accepted as evidence for a model run.
    """

    dataset_id: str
    kind: DataSourceKind
    status: DataSourceStatus
    citation_key: str
    citation: str
    uri: str = ""
    download_filename: str = ""
    checksum_sha256: str = ""
    license_note: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        """Validate and normalize data-source metadata."""
        for field_name in ("dataset_id", "citation_key", "citation"):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must be non-empty")
        if self.kind not in DATA_SOURCE_KINDS:
            raise ValueError("kind is not supported")
        if self.status not in DATA_SOURCE_STATUSES:
            raise ValueError("status is not supported")
        if self.status != "planned" and not self.uri:
            raise ValueError("uri is required for local and external data sources")
        if Path(self.download_filename).name != self.download_filename:
            raise ValueError("download_filename must not include directories")
        object.__setattr__(
            self,
            "checksum_sha256",
            _normalized_checksum(self.checksum_sha256),
        )

    @property
    def has_checksum(self) -> bool:
        """Return whether this record includes a SHA-256 checksum."""
        return self.checksum_sha256 != ""


@dataclass(frozen=True)
class DataSourceCatalog:
    """A validated collection of data-source records."""

    records: tuple[DataSourceRecord, ...]

    @classmethod
    def from_records(cls, records: Iterable[DataSourceRecord]) -> DataSourceCatalog:
        """Build a catalog from validated records."""
        return cls(tuple(records))

    def __post_init__(self) -> None:
        """Validate catalog-level uniqueness."""
        dataset_ids = [record.dataset_id for record in self.records]
        if len(set(dataset_ids)) != len(dataset_ids):
            raise ValueError("dataset_id values must be unique")

    def ids(self) -> tuple[str, ...]:
        """Return dataset identifiers in catalog order."""
        return tuple(record.dataset_id for record in self.records)

    def by_id(self, dataset_id: str) -> DataSourceRecord:
        """Return one record by dataset identifier."""
        for record in self.records:
            if record.dataset_id == dataset_id:
                return record
        raise KeyError(dataset_id)

    def filter(
        self,
        *,
        kind: DataSourceKind | None = None,
        status: DataSourceStatus | None = None,
    ) -> DataSourceCatalog:
        """Return records matching optional kind and status filters."""
        return DataSourceCatalog.from_records(
            record
            for record in self.records
            if (kind is None or record.kind == kind)
            and (status is None or record.status == status)
        )


def load_data_source_catalog(path: str | Path) -> DataSourceCatalog:
    """Load a data-source catalog from a TOML file."""
    catalog_path = Path(path)
    with catalog_path.open("rb") as catalog_file:
        raw_catalog = tomllib.load(catalog_file)
    records = (_record_from_mapping(item) for item in _data_source_tables(raw_catalog))
    return DataSourceCatalog.from_records(records)


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 digest for a local file."""
    digest = sha256()
    with Path(path).open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_record_checksum(
    record: DataSourceRecord, *, base_path: str | Path = "."
) -> bool:
    """Return whether a local data-source file matches its registered checksum."""
    if record.status != "local":
        raise ValueError("only local data sources can be checksum-verified")
    if not record.has_checksum:
        raise ValueError("record does not include checksum_sha256")
    source_path = Path(record.uri)
    if not source_path.is_absolute():
        source_path = Path(base_path) / source_path
    return sha256_file(source_path) == record.checksum_sha256


def _data_source_tables(raw_catalog: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Return data-source tables from raw TOML data."""
    value = raw_catalog.get("data_sources")
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("data_sources must be a list of tables")
    return tuple(value)


def _record_from_mapping(raw_record: dict[str, Any]) -> DataSourceRecord:
    """Build a data-source record from one TOML table."""
    return DataSourceRecord(
        dataset_id=_required_text(raw_record, "dataset_id"),
        kind=_kind(_required_text(raw_record, "kind")),
        status=_status(_required_text(raw_record, "status")),
        citation_key=_required_text(raw_record, "citation_key"),
        citation=_required_text(raw_record, "citation"),
        uri=_optional_text(raw_record, "uri"),
        download_filename=_optional_text(raw_record, "download_filename"),
        checksum_sha256=_optional_text(raw_record, "checksum_sha256"),
        license_note=_optional_text(raw_record, "license_note"),
        notes=_optional_text(raw_record, "notes"),
    )


def _required_text(raw_record: dict[str, Any], key: str) -> str:
    """Return a non-empty string field from a raw TOML table."""
    value = _optional_text(raw_record, key)
    if value == "":
        raise ValueError(f"{key} must be non-empty")
    return value


def _optional_text(raw_record: dict[str, Any], key: str) -> str:
    """Return an optional string field from a raw TOML table."""
    value = raw_record.get(key, "")
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value.strip()


def _kind(value: str) -> DataSourceKind:
    """Validate and return a data-source kind."""
    if value not in DATA_SOURCE_KINDS:
        raise ValueError("kind is not supported")
    return cast(DataSourceKind, value)


def _status(value: str) -> DataSourceStatus:
    """Validate and return a data-source status."""
    if value not in DATA_SOURCE_STATUSES:
        raise ValueError("status is not supported")
    return cast(DataSourceStatus, value)


def _normalized_checksum(value: str) -> str:
    """Return a normalized SHA-256 checksum or raise for malformed text."""
    if value == "":
        return ""
    normalized = value.lower()
    is_hex_digest = len(normalized) == 64 and all(
        character in "0123456789abcdef" for character in normalized
    )
    if not is_hex_digest:
        raise ValueError("checksum_sha256 must be a 64-character hex digest")
    return normalized
