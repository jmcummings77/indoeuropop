"""Tests for data-source catalog metadata."""

from pathlib import Path

import pytest

from indoeuropop.data_sources import (
    DataSourceCatalog,
    DataSourceRecord,
    load_data_source_catalog,
    sha256_file,
    verify_record_checksum,
)


def test_data_source_catalog_filters_and_finds_records() -> None:
    """Catalogs should preserve order and expose simple filters."""
    local = DataSourceRecord(
        dataset_id="synthetic-target-example",
        kind="target_csv",
        status="local",
        citation_key="synthetic",
        citation="Synthetic target example",
        uri="examples/target-observations.example.csv",
    )
    planned = DataSourceRecord(
        dataset_id="planned-aadr-metadata",
        kind="aadr",
        status="planned",
        citation_key="aadr",
        citation="AADR release to be selected in a later phase",
    )
    catalog = DataSourceCatalog.from_records((local, planned))

    assert catalog.ids() == ("synthetic-target-example", "planned-aadr-metadata")
    assert catalog.by_id("synthetic-target-example") == local
    assert catalog.filter(kind="aadr").records == (planned,)
    assert catalog.filter(status="local").records == (local,)
    with pytest.raises(KeyError):
        catalog.by_id("missing")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"dataset_id": ""},
        {"kind": "unknown"},
        {"status": "unknown"},
        {"citation_key": ""},
        {"citation": ""},
        {"status": "local", "uri": ""},
        {"download_filename": "nested/source.csv"},
        {"checksum_sha256": "not-a-checksum"},
    ],
)
def test_data_source_record_rejects_invalid_metadata(
    kwargs: dict[str, str],
) -> None:
    """Malformed source metadata should fail before ingestion code sees it."""
    values = {
        "dataset_id": "example",
        "kind": "target_csv",
        "status": "planned",
        "citation_key": "key",
        "citation": "Citation",
    }
    values.update(kwargs)

    with pytest.raises(ValueError):
        DataSourceRecord(**values)  # type: ignore[arg-type]


def test_data_source_catalog_rejects_duplicate_ids() -> None:
    """Catalog identifiers should be unique."""
    first = DataSourceRecord(
        dataset_id="duplicate",
        kind="target_csv",
        status="planned",
        citation_key="first",
        citation="First citation",
    )
    second = DataSourceRecord(
        dataset_id="duplicate",
        kind="poseidon",
        status="planned",
        citation_key="second",
        citation="Second citation",
    )

    with pytest.raises(ValueError, match="unique"):
        DataSourceCatalog.from_records((first, second))


def test_load_data_source_catalog_reads_toml(tmp_path: Path) -> None:
    """Catalog TOML should load into validated records."""
    catalog_path = tmp_path / "data-sources.toml"
    checksum = "BB2B1F4C719FE7A8D649918C377EC58736857D95A15C5820A0295D0012AC160C"
    catalog_path.write_text(
        f"""
        [[data_sources]]
        dataset_id = "synthetic-target-example"
        kind = "target_csv"
        status = "local"
        citation_key = "synthetic"
        citation = "Synthetic target example"
        uri = "examples/target-observations.example.csv"
        download_filename = "targets.csv"
        checksum_sha256 = "{checksum}"
        license_note = "Example-only data"
        notes = "Not historical evidence"
        """,
        encoding="utf-8",
    )

    catalog = load_data_source_catalog(catalog_path)
    record = catalog.by_id("synthetic-target-example")

    assert record.kind == "target_csv"
    assert record.status == "local"
    assert record.has_checksum
    assert record.download_filename == "targets.csv"
    assert record.checksum_sha256 == (
        "bb2b1f4c719fe7a8d649918c377ec58736857d95a15c5820a0295d0012ac160c"
    )
    assert record.license_note == "Example-only data"
    assert record.notes == "Not historical evidence"


def test_load_data_source_catalog_rejects_malformed_toml(tmp_path: Path) -> None:
    """Catalog loader should reject missing or malformed data_sources tables."""
    catalog_path = tmp_path / "data-sources.toml"
    catalog_path.write_text("data_sources = {}", encoding="utf-8")

    with pytest.raises(ValueError, match="data_sources"):
        load_data_source_catalog(catalog_path)


@pytest.mark.parametrize(
    "table_text,match",
    [
        (
            """
            [[data_sources]]
            kind = "target_csv"
            status = "planned"
            citation_key = "key"
            citation = "Citation"
            """,
            "dataset_id",
        ),
        (
            """
            [[data_sources]]
            dataset_id = "example"
            kind = 7
            status = "planned"
            citation_key = "key"
            citation = "Citation"
            """,
            "kind",
        ),
        (
            """
            [[data_sources]]
            dataset_id = "example"
            kind = "unknown"
            status = "planned"
            citation_key = "key"
            citation = "Citation"
            """,
            "kind",
        ),
        (
            """
            [[data_sources]]
            dataset_id = "example"
            kind = "target_csv"
            status = "unknown"
            citation_key = "key"
            citation = "Citation"
            """,
            "status",
        ),
    ],
)
def test_load_data_source_catalog_rejects_invalid_records(
    tmp_path: Path,
    table_text: str,
    match: str,
) -> None:
    """Catalog loader should report invalid record fields from TOML."""
    catalog_path = tmp_path / "data-sources.toml"
    catalog_path.write_text(table_text, encoding="utf-8")

    with pytest.raises(ValueError, match=match):
        load_data_source_catalog(catalog_path)


def test_sha256_file_and_record_verification(tmp_path: Path) -> None:
    """Local source checksums should be reproducible and verifiable."""
    data_path = tmp_path / "input.csv"
    data_path.write_text("status,region\nsynthetic,britain\n", encoding="utf-8")
    checksum = sha256_file(data_path)
    record = DataSourceRecord(
        dataset_id="local-input",
        kind="target_csv",
        status="local",
        citation_key="local",
        citation="Local input",
        uri="input.csv",
        checksum_sha256=checksum,
    )

    assert verify_record_checksum(record, base_path=tmp_path)


def test_verify_record_checksum_rejects_non_verifiable_records() -> None:
    """Checksum verification should only run for local records with checksums."""
    planned = DataSourceRecord(
        dataset_id="planned",
        kind="aadr",
        status="planned",
        citation_key="planned",
        citation="Planned source",
    )
    local_without_checksum = DataSourceRecord(
        dataset_id="local",
        kind="target_csv",
        status="local",
        citation_key="local",
        citation="Local source",
        uri="input.csv",
    )

    with pytest.raises(ValueError, match="local"):
        verify_record_checksum(planned)
    with pytest.raises(ValueError, match="checksum"):
        verify_record_checksum(local_without_checksum)
