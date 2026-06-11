"""Tests for catalog-driven source data downloads."""

from __future__ import annotations

import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from indoeuropop.data.data_sources import (
    DataSourceCatalog,
    DataSourceRecord,
    sha256_file,
)
from indoeuropop.data.source_downloader import (
    DownloadOptions,
    _output_filename,
    _safe_filename,
    download_catalog_sources,
    download_data_source,
    downloadable_records,
    downloaded_source_rows,
    downloaded_sources_to_csv,
    write_download_manifest_csv,
)


def _record(
    dataset_id: str = "source-1",
    *,
    status: str = "local",
    uri: str = "source.csv",
    checksum_sha256: str = "",
) -> DataSourceRecord:
    """Return one data-source record for downloader tests."""
    return DataSourceRecord(
        dataset_id=dataset_id,
        kind="sample_metadata_csv",
        status=status,  # type: ignore[arg-type]
        citation_key="source",
        citation="Source citation",
        uri=uri,
        checksum_sha256=checksum_sha256,
    )


def _planned_record(dataset_id: str = "planned-aadr") -> DataSourceRecord:
    """Return one planned data-source record for downloader tests."""
    return DataSourceRecord(
        dataset_id=dataset_id,
        kind="aadr",
        status="planned",
        citation_key="planned",
        citation="Planned source",
    )


def _write_source(tmp_path: Path, name: str = "source.csv") -> Path:
    """Write one tiny source file and return its path."""
    source_path = tmp_path / name
    source_path.write_text("sample_id,region\nI001,britain\n", encoding="utf-8")
    return source_path


def test_download_options_rejects_invalid_timeout(tmp_path: Path) -> None:
    """Downloader options should reject non-positive timeouts."""
    with pytest.raises(ValueError, match="timeout"):
        DownloadOptions(output_dir=tmp_path, timeout_seconds=0)


def test_downloadable_records_filters_and_skips_planned_by_default() -> None:
    """Unfiltered downloads should ignore planned placeholders."""
    local = _record("local", status="local")
    external = _record("external", status="external", uri="file:///tmp/source.csv")
    planned = _planned_record()
    catalog = DataSourceCatalog.from_records((local, external, planned))

    assert downloadable_records(catalog) == (local, external)
    assert downloadable_records(catalog, kind="sample_metadata_csv") == (
        local,
        external,
    )


def test_downloadable_records_rejects_explicit_planned_selection() -> None:
    """Explicit planned selections should fail instead of silently skipping."""
    catalog = DataSourceCatalog.from_records((_planned_record(),))

    with pytest.raises(ValueError, match="planned"):
        downloadable_records(catalog, dataset_ids=("planned-aadr",))
    with pytest.raises(ValueError, match="planned"):
        downloadable_records(catalog, status="planned")


def test_download_catalog_sources_rejects_empty_selection() -> None:
    """A download request should fail when no materializable records match."""
    catalog = DataSourceCatalog.from_records((_planned_record(),))

    with pytest.raises(ValueError, match="no downloadable"):
        download_catalog_sources(catalog, DownloadOptions(output_dir=Path("unused")))


def test_download_data_source_copies_local_record(tmp_path: Path) -> None:
    """Local catalog records should be copied into the output directory."""
    source_path = _write_source(tmp_path)
    record = _record(uri=source_path.name, checksum_sha256=sha256_file(source_path))
    output_dir = tmp_path / "downloads"

    downloaded = download_data_source(
        record,
        DownloadOptions(output_dir=output_dir, base_path=tmp_path),
    )

    assert downloaded.dataset_id == "source-1"
    assert downloaded.path == output_dir / source_path.name
    assert downloaded.path.read_text(encoding="utf-8") == source_path.read_text(
        encoding="utf-8"
    )
    assert downloaded.verified
    assert downloaded.checksum_sha256 == sha256_file(source_path)
    assert downloaded.size_bytes == source_path.stat().st_size


def test_download_data_source_protects_existing_outputs(tmp_path: Path) -> None:
    """Existing output files should require explicit overwrite."""
    source_path = _write_source(tmp_path)
    record = _record(uri=source_path.name)
    output_dir = tmp_path / "downloads"
    output_dir.mkdir()
    (output_dir / source_path.name).write_text("existing\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already exists"):
        download_data_source(
            record,
            DownloadOptions(output_dir=output_dir, base_path=tmp_path),
        )

    downloaded = download_data_source(
        record,
        DownloadOptions(output_dir=output_dir, base_path=tmp_path, overwrite=True),
    )

    assert downloaded.path.read_text(encoding="utf-8").startswith("sample_id")


def test_download_data_source_rejects_missing_local_file(tmp_path: Path) -> None:
    """Local records should fail clearly when their source path is absent."""
    record = _record(uri="missing.csv")

    with pytest.raises(FileNotFoundError, match="does not exist"):
        download_data_source(
            record,
            DownloadOptions(output_dir=tmp_path / "downloads", base_path=tmp_path),
        )


def test_download_data_source_rejects_planned_records(tmp_path: Path) -> None:
    """Planned records should not be materialized directly."""
    with pytest.raises(ValueError, match="planned"):
        download_data_source(
            _planned_record(),
            DownloadOptions(output_dir=tmp_path / "downloads"),
        )


def test_download_data_source_rejects_checksum_mismatch(tmp_path: Path) -> None:
    """Downloaded files should be checked when a catalog checksum is present."""
    source_path = _write_source(tmp_path)
    bad_checksum = "0" * 64
    record = _record(uri=source_path.name, checksum_sha256=bad_checksum)

    with pytest.raises(ValueError, match="checksum mismatch"):
        download_data_source(
            record,
            DownloadOptions(output_dir=tmp_path / "downloads", base_path=tmp_path),
        )


def test_download_external_file_uri(tmp_path: Path) -> None:
    """External file URIs should be materialized without network access."""
    source_path = _write_source(tmp_path)
    record = _record(
        status="external",
        uri=source_path.absolute().as_uri(),
    )

    downloaded = download_data_source(
        record,
        DownloadOptions(output_dir=tmp_path / "downloads"),
    )

    assert downloaded.status == "external"
    assert downloaded.path.read_text(encoding="utf-8").startswith("sample_id")


def test_download_external_file_uri_rejects_missing_file(tmp_path: Path) -> None:
    """External file URI downloads should fail for absent files."""
    record = _record(
        status="external",
        uri=(tmp_path / "missing.csv").absolute().as_uri(),
    )

    with pytest.raises(FileNotFoundError, match="does not exist"):
        download_data_source(record, DownloadOptions(output_dir=tmp_path / "out"))


def test_download_external_rejects_unsupported_scheme(tmp_path: Path) -> None:
    """Only file and HTTP-family external URI schemes should be supported."""
    record = _record(status="external", uri="ftp://example.com/source.csv")

    with pytest.raises(ValueError, match="unsupported"):
        download_data_source(record, DownloadOptions(output_dir=tmp_path / "out"))


def test_download_external_http_uri(tmp_path: Path) -> None:
    """HTTP downloads should stream source bytes into the output directory."""
    source_dir = tmp_path / "served"
    source_dir.mkdir()
    source_path = _write_source(source_dir)
    server = _http_server(source_dir)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        record = _record(
            status="external",
            uri=f"http://127.0.0.1:{server.server_port}/{source_path.name}",
        )

        downloaded = download_data_source(
            record,
            DownloadOptions(output_dir=tmp_path / "downloads"),
        )
    finally:
        server.shutdown()
        thread.join()
        server.server_close()

    assert downloaded.path.name == source_path.name
    assert downloaded.checksum_sha256 == sha256_file(source_path)


def test_download_catalog_sources_and_manifest_csv(tmp_path: Path) -> None:
    """Catalog downloads should support repeated IDs and audit manifests."""
    source_path = _write_source(tmp_path)
    record = _record("local-source", uri=source_path.name)
    catalog = DataSourceCatalog.from_records((record, _planned_record()))
    manifest_path = tmp_path / "manifests" / "downloads.csv"

    (downloaded,) = download_catalog_sources(
        catalog,
        DownloadOptions(output_dir=tmp_path / "downloads", base_path=tmp_path),
        dataset_ids=("local-source",),
    )
    rows = downloaded_source_rows((downloaded,))
    csv_text = downloaded_sources_to_csv((downloaded,))
    returned_path = write_download_manifest_csv((downloaded,), manifest_path)

    assert rows[0]["dataset_id"] == "local-source"
    assert rows[0]["verified"] == "true"
    assert csv_text.startswith("dataset_id,kind,status,source_uri")
    assert returned_path == manifest_path
    assert manifest_path.read_text(encoding="utf-8") == csv_text


def test_output_filename_falls_back_to_dataset_id_for_api_urls() -> None:
    """API-style URLs should use stable dataset IDs for output names."""
    record = _record(
        dataset_id="aadr-release",
        status="external",
        uri="https://dataverse.harvard.edu/api/access/dataset/:persistentId/",
    )

    assert _output_filename(record) == "aadr-release"
    assert (
        _output_filename(
            DataSourceRecord(
                dataset_id="aadr-release",
                kind="aadr",
                status="external",
                citation_key="aadr",
                citation="AADR citation",
                uri=record.uri,
                download_filename="aadr-release.zip",
            )
        )
        == "aadr-release.zip"
    )
    assert _safe_filename("AADR release/2026") == "AADR-release-2026"
    assert _safe_filename("...") == "downloaded-source"


def _http_server(source_dir: Path) -> ThreadingHTTPServer:
    """Return a local HTTP server rooted at a source directory."""
    handler = functools.partial(
        SimpleHTTPRequestHandler,
        directory=str(source_dir),
    )
    return ThreadingHTTPServer(("127.0.0.1", 0), handler)
