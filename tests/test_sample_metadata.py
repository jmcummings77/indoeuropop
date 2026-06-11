"""Tests for sample metadata staging records."""

from pathlib import Path

import pytest

from indoeuropop.data.sample_metadata import (
    SAMPLE_METADATA_COLUMNS,
    RegionSampleCount,
    SampleMetadataDataset,
    SampleMetadataRecord,
    load_sample_metadata,
    sample_metadata_rows,
    sample_metadata_to_csv,
    write_sample_metadata_csv,
)


def _record(
    sample_id: str,
    *,
    region: str = "britain",
    status: str = "synthetic",
    time_bce: float = 2900,
) -> SampleMetadataRecord:
    """Build one sample metadata record for tests."""
    return SampleMetadataRecord(
        status=status,  # type: ignore[arg-type]
        dataset_id="synthetic-samples",
        sample_id=sample_id,
        accession_id=f"accession-{sample_id}",
        publication_key="synthetic",
        publication="Synthetic sample metadata example",
        region=region,
        site="Example Site",
        time_bce=time_bce,
        date_uncertainty=50,
        sex="unknown",
        method="synthetic_metadata",
    )


def _csv_text(*rows: tuple[str, ...]) -> str:
    """Return sample metadata CSV text from rows of cell values."""
    header = ",".join(SAMPLE_METADATA_COLUMNS)
    return "\n".join((header, *((",".join(row)) for row in rows)))


def _csv_row(
    *,
    status: str = "synthetic",
    sample_id: str = "SYN001",
    time_bce: str = "2900",
    sex: str = "unknown",
    note: str = "Example row",
) -> tuple[str, ...]:
    """Return one complete sample metadata CSV row."""
    return (
        status,
        "synthetic-samples",
        sample_id,
        f"accession-{sample_id}",
        "synthetic",
        "Synthetic publication",
        "britain",
        "Example Site",
        time_bce,
        "50",
        sex,
        "synthetic_metadata",
        note,
    )


def test_sample_metadata_dataset_summarizes_records() -> None:
    """Sample metadata datasets should expose filters and simple summaries."""
    first = _record("SYN001", region="britain", time_bce=2900)
    second = _record("SYN002", region="iberia", time_bce=2700)
    dataset = SampleMetadataDataset.from_rows((first, second))

    assert dataset.sample_count == 2
    assert dataset.dataset_ids() == ("synthetic-samples",)
    assert dataset.regions() == ("britain", "iberia")
    assert dataset.publication_keys() == ("synthetic",)
    assert dataset.filter(region="britain").records == (first,)
    assert dataset.filter(dataset_id="synthetic-samples").sample_count == 2
    assert dataset.filter(status="synthetic").sample_count == 2
    assert dataset.counts_by_region() == (
        RegionSampleCount(region="britain", sample_count=1),
        RegionSampleCount(region="iberia", sample_count=1),
    )
    assert dataset.time_range_bce() == (2700, 2900)


def test_sample_metadata_dataset_rejects_duplicate_ids() -> None:
    """Sample IDs should be unique within each dataset."""
    with pytest.raises(ValueError, match="unique"):
        SampleMetadataDataset.from_rows((_record("SYN001"), _record("SYN001")))


def test_sample_metadata_dataset_requires_records() -> None:
    """Empty datasets should fail before summary use."""
    dataset = SampleMetadataDataset.from_rows(())

    with pytest.raises(ValueError, match="at least one"):
        dataset.require_records()
    with pytest.raises(ValueError, match="at least one"):
        dataset.time_range_bce()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": "unknown"},
        {"dataset_id": ""},
        {"sample_id": ""},
        {"accession_id": ""},
        {"publication_key": ""},
        {"publication": ""},
        {"region": ""},
        {"site": ""},
        {"method": ""},
        {"time_bce": float("nan")},
        {"date_uncertainty": -1.0},
        {"date_uncertainty": float("nan")},
        {"sex": "unsupported"},
    ],
)
def test_sample_metadata_record_rejects_invalid_fields(
    kwargs: dict[str, object],
) -> None:
    """Invalid sample metadata fields should fail at construction."""
    values = {
        "status": "synthetic",
        "dataset_id": "synthetic-samples",
        "sample_id": "SYN001",
        "accession_id": "synthetic-accession-1",
        "publication_key": "synthetic",
        "publication": "Synthetic sample metadata example",
        "region": "britain",
        "site": "Example Site",
        "time_bce": 2900.0,
        "date_uncertainty": 50.0,
        "sex": "unknown",
        "method": "synthetic_metadata",
    }
    values.update(kwargs)

    with pytest.raises(ValueError):
        SampleMetadataRecord(**values)  # type: ignore[arg-type]


def test_load_sample_metadata_reads_csv(tmp_path: Path) -> None:
    """Sample metadata CSV files should load into validated datasets."""
    metadata_path = tmp_path / "sample-metadata.csv"
    metadata_path.write_text(
        _csv_text(
            _csv_row(sample_id="SYN001", sex="female", note="First row"),
            _csv_row(sample_id="SYN002", time_bce="2850", sex="male", note=""),
        ),
        encoding="utf-8",
    )

    dataset = load_sample_metadata(metadata_path)

    assert dataset.sample_count == 2
    assert dataset.records[0].note == "First row"
    assert dataset.records[1].note == ""
    assert dataset.records[0].sex == "female"


def test_sample_metadata_csv_exports_round_trip(tmp_path: Path) -> None:
    """Sample metadata datasets should write the same schema they load."""
    dataset = SampleMetadataDataset.from_rows((_record("SYN001"),))
    output_path = tmp_path / "metadata" / "sample-metadata.csv"

    rows = sample_metadata_rows(dataset)
    csv_text = sample_metadata_to_csv(dataset)
    returned_path = write_sample_metadata_csv(dataset, output_path)
    loaded = load_sample_metadata(output_path)

    assert SAMPLE_METADATA_COLUMNS[0] == "status"
    assert rows[0]["time_bce"] == "2900"
    assert csv_text.startswith("status,dataset_id,sample_id")
    assert returned_path == output_path
    assert loaded.records == dataset.records


def test_load_sample_metadata_rejects_missing_header(tmp_path: Path) -> None:
    """CSV files without a header should fail clearly."""
    metadata_path = tmp_path / "sample-metadata.csv"
    metadata_path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="header"):
        load_sample_metadata(metadata_path)


def test_load_sample_metadata_rejects_missing_columns(tmp_path: Path) -> None:
    """CSV files missing required columns should fail clearly."""
    metadata_path = tmp_path / "sample-metadata.csv"
    metadata_path.write_text("status,dataset_id\nsynthetic,data\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing columns"):
        load_sample_metadata(metadata_path)


def test_load_sample_metadata_reports_row_errors(tmp_path: Path) -> None:
    """CSV row errors should include the row number."""
    metadata_path = tmp_path / "sample-metadata.csv"
    metadata_path.write_text(
        _csv_text(
            _csv_row(time_bce="not-a-date", note=""),
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="row 2"):
        load_sample_metadata(metadata_path)


@pytest.mark.parametrize(
    "row",
    [
        ("synthetic", "synthetic-samples", "", "accession-1"),
        ("unknown", "synthetic-samples", "SYN001", "accession-1"),
        ("synthetic", "synthetic-samples", "SYN001", "accession-1", "bad-sex"),
    ],
)
def test_load_sample_metadata_reports_parser_validation_errors(
    tmp_path: Path,
    row: tuple[str, ...],
) -> None:
    """CSV parser-specific validators should report line-aware failures."""
    metadata_path = tmp_path / "sample-metadata.csv"
    if len(row) == 4:
        status, dataset_id, sample_id, accession_id = row
        csv_row = (
            status,
            dataset_id,
            sample_id,
            accession_id,
            "synthetic",
            "Synthetic publication",
            "britain",
            "Example Site",
            "2900",
            "50",
            "unknown",
            "synthetic_metadata",
            "Example row",
        )
    else:
        status, dataset_id, sample_id, accession_id, sex = row
        csv_row = (
            status,
            dataset_id,
            sample_id,
            accession_id,
            "synthetic",
            "Synthetic publication",
            "britain",
            "Example Site",
            "2900",
            "50",
            sex,
            "synthetic_metadata",
            "Example row",
        )
    metadata_path.write_text(_csv_text(csv_row), encoding="utf-8")

    with pytest.raises(ValueError, match="row 2"):
        load_sample_metadata(metadata_path)


def test_load_sample_metadata_handles_missing_optional_note(tmp_path: Path) -> None:
    """Rows shorter than the optional note column should get an empty note."""
    metadata_path = tmp_path / "sample-metadata.csv"
    metadata_path.write_text(
        _csv_text(_csv_row()[:-1]),
        encoding="utf-8",
    )

    dataset = load_sample_metadata(metadata_path)

    assert dataset.records[0].note == ""
