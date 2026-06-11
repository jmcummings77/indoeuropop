"""Download or materialize cataloged research data sources."""

from __future__ import annotations

import csv
import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from indoeuropop.data.data_sources import (
    DataSourceCatalog,
    DataSourceKind,
    DataSourceRecord,
    DataSourceStatus,
    sha256_file,
)

DOWNLOADABLE_STATUSES = frozenset({"external", "local"})
DOWNLOAD_MANIFEST_FIELDS = (
    "dataset_id",
    "kind",
    "status",
    "source_uri",
    "path",
    "checksum_sha256",
    "size_bytes",
    "verified",
)


@dataclass(frozen=True)
class DownloadOptions:
    """Controls for materializing cataloged data sources.

    Local catalog records are copied from `base_path`; external records are
    fetched from their URI. Existing output files are protected unless
    `overwrite` is true.
    """

    output_dir: Path
    base_path: Path = Path(".")
    overwrite: bool = False
    timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        """Validate downloader options."""
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


@dataclass(frozen=True)
class DownloadedSource:
    """One materialized data-source artifact."""

    dataset_id: str
    kind: DataSourceKind
    status: DataSourceStatus
    source_uri: str
    path: Path
    checksum_sha256: str
    size_bytes: int
    verified: bool


def downloadable_records(
    catalog: DataSourceCatalog,
    *,
    dataset_ids: Iterable[str] = (),
    kind: DataSourceKind | None = None,
    status: DataSourceStatus | None = None,
) -> tuple[DataSourceRecord, ...]:
    """Return catalog records selected for download or local materialization."""
    selected_ids = tuple(dataset_ids)
    if selected_ids:
        records = tuple(catalog.by_id(dataset_id) for dataset_id in selected_ids)
    else:
        records = catalog.records
    filtered = tuple(
        record
        for record in records
        if (kind is None or record.kind == kind)
        and (status is None or record.status == status)
    )
    planned = tuple(
        record.dataset_id for record in filtered if record.status == "planned"
    )
    if planned and (selected_ids or status == "planned"):
        planned_text = ", ".join(planned)
        raise ValueError(f"planned data sources cannot be downloaded: {planned_text}")
    return tuple(
        record for record in filtered if record.status in DOWNLOADABLE_STATUSES
    )


def download_catalog_sources(
    catalog: DataSourceCatalog,
    options: DownloadOptions,
    *,
    dataset_ids: Iterable[str] = (),
    kind: DataSourceKind | None = None,
    status: DataSourceStatus | None = None,
) -> tuple[DownloadedSource, ...]:
    """Materialize selected catalog records into the output directory."""
    records = downloadable_records(
        catalog,
        dataset_ids=dataset_ids,
        kind=kind,
        status=status,
    )
    if not records:
        raise ValueError("no downloadable data sources matched the selection")
    return tuple(download_data_source(record, options) for record in records)


def download_data_source(
    record: DataSourceRecord,
    options: DownloadOptions,
) -> DownloadedSource:
    """Materialize one data-source record into the output directory."""
    if record.status == "planned":
        raise ValueError("planned data sources cannot be downloaded")
    options.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = options.output_dir / _output_filename(record)
    if output_path.exists() and not options.overwrite:
        raise FileExistsError(f"output file already exists: {output_path}")
    if record.status == "local":
        _copy_local_source(record, options.base_path, output_path)
    else:
        _download_external_source(record, output_path, options.timeout_seconds)
    checksum = sha256_file(output_path)
    verified = not record.has_checksum or checksum == record.checksum_sha256
    if not verified:
        raise ValueError(
            f"checksum mismatch for downloaded source: {record.dataset_id}"
        )
    return DownloadedSource(
        dataset_id=record.dataset_id,
        kind=record.kind,
        status=record.status,
        source_uri=record.uri,
        path=output_path,
        checksum_sha256=checksum,
        size_bytes=output_path.stat().st_size,
        verified=verified,
    )


def downloaded_source_rows(
    sources: Iterable[DownloadedSource],
) -> tuple[dict[str, str], ...]:
    """Return downloaded-source records as manifest CSV rows."""
    return tuple(_downloaded_source_row(source) for source in sources)


def downloaded_sources_to_csv(sources: Iterable[DownloadedSource]) -> str:
    """Return downloaded-source records serialized as CSV text."""
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=DOWNLOAD_MANIFEST_FIELDS,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(downloaded_source_rows(sources))
    return output.getvalue()


def write_download_manifest_csv(
    sources: Iterable[DownloadedSource],
    path: str | Path,
) -> Path:
    """Write downloaded-source records as a CSV manifest."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(downloaded_sources_to_csv(sources), encoding="utf-8")
    return output_path


def _copy_local_source(
    record: DataSourceRecord,
    base_path: Path,
    output_path: Path,
) -> None:
    """Copy a local catalog record into the download cache."""
    source_path = Path(record.uri)
    if not source_path.is_absolute():
        source_path = base_path / source_path
    if not source_path.is_file():
        raise FileNotFoundError(f"local data source does not exist: {source_path}")
    shutil.copyfile(source_path, output_path)


def _download_external_source(
    record: DataSourceRecord,
    output_path: Path,
    timeout_seconds: float,
) -> None:
    """Download one external catalog record over a supported URI scheme."""
    parsed = urlparse(record.uri)
    if parsed.scheme in ("", "file"):
        source_path = Path(
            unquote(parsed.path if parsed.scheme == "file" else record.uri)
        )
        if not source_path.is_file():
            raise FileNotFoundError(
                f"external file source does not exist: {source_path}"
            )
        shutil.copyfile(source_path, output_path)
        return
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"unsupported data-source URI scheme: {parsed.scheme}")
    request = Request(record.uri, headers={"User-Agent": "indoeuropop/0.1"})
    with (
        urlopen(request, timeout=timeout_seconds) as response,
        output_path.open("wb") as output_file,
    ):
        shutil.copyfileobj(response, output_file)


def _output_filename(record: DataSourceRecord) -> str:
    """Return a stable output filename for one data-source record."""
    if record.download_filename:
        return record.download_filename
    parsed = urlparse(record.uri)
    basename = Path(unquote(parsed.path)).name
    if basename and not basename.startswith(":"):
        return basename
    return _safe_filename(record.dataset_id)


def _safe_filename(value: str) -> str:
    """Return a filesystem-friendly filename from a dataset identifier."""
    characters = [character if character.isalnum() else "-" for character in value]
    filename = "".join(characters).strip("-")
    return filename or "downloaded-source"


def _downloaded_source_row(source: DownloadedSource) -> dict[str, str]:
    """Return one downloaded-source manifest row."""
    return {
        "dataset_id": source.dataset_id,
        "kind": source.kind,
        "status": source.status,
        "source_uri": source.source_uri,
        "path": str(source.path),
        "checksum_sha256": source.checksum_sha256,
        "size_bytes": str(source.size_bytes),
        "verified": "true" if source.verified else "false",
    }
