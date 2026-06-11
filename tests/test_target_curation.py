"""Tests for target curation metadata."""

from pathlib import Path

import pytest

from indoeuropop.sample_metadata import SampleMetadataDataset, SampleMetadataRecord
from indoeuropop.target_curation import (
    TARGET_CURATION_COLUMNS,
    TargetCurationDataset,
    TargetCurationRecord,
    load_target_curation,
    target_curation_rows,
    target_curation_to_csv,
    write_target_curation_csv,
)


def _record(
    target_id: str = "target-1",
    *,
    region: str = "britain",
    source: str = "steppe",
    sample_ids: tuple[str, ...] = ("SYN001", "SYN002"),
    note: str = "",
) -> TargetCurationRecord:
    """Build one target curation record for tests."""
    return TargetCurationRecord(
        status="synthetic",
        target_id=target_id,
        region=region,
        source=source,
        start_bce=3000,
        end_bce=2800,
        sample_ids=sample_ids,
        sample_count=len(sample_ids),
        ancestry_method="synthetic_ancestry_estimate",
        aggregation_method="synthetic_mean",
        citation_key="synthetic-curation",
        citation="Synthetic curation example",
        note=note,
    )


def _sample_metadata() -> SampleMetadataDataset:
    """Return sample metadata referenced by curation records."""
    return SampleMetadataDataset.from_rows(
        (
            _sample_record("SYN001"),
            _sample_record("SYN002"),
        )
    )


def _sample_record(sample_id: str) -> SampleMetadataRecord:
    """Build one synthetic sample metadata record."""
    return SampleMetadataRecord(
        status="synthetic",
        dataset_id="synthetic-samples",
        sample_id=sample_id,
        accession_id=f"accession-{sample_id}",
        publication_key="synthetic",
        publication="Synthetic sample metadata example",
        region="britain",
        site="Example Site",
        time_bce=2900,
        date_uncertainty=50,
        sex="unknown",
        method="synthetic_metadata",
    )


def _csv_row(
    *,
    status: str = "synthetic",
    target_id: str = "target-1",
    sample_ids: str = "SYN001;SYN002",
    sample_count: str = "2",
    note: str = "Example curation row",
) -> tuple[str, ...]:
    """Return one complete target curation CSV row."""
    return (
        status,
        target_id,
        "britain",
        "steppe",
        "3000",
        "2800",
        sample_ids,
        sample_count,
        "synthetic_ancestry_estimate",
        "synthetic_mean",
        "synthetic-curation",
        "Synthetic curation example",
        note,
    )


def _csv_text(*rows: tuple[str, ...]) -> str:
    """Return target curation CSV text from rows of cell values."""
    header = ",".join(TARGET_CURATION_COLUMNS)
    return "\n".join((header, *((",".join(row)) for row in rows)))


def test_target_curation_dataset_summarizes_records() -> None:
    """Curation datasets should expose filters and sample references."""
    first = _record("target-1", region="britain")
    second = _record("target-2", region="iberia", sample_ids=("SYN003",))
    dataset = TargetCurationDataset.from_rows((first, second))

    assert dataset.target_ids() == ("target-1", "target-2")
    assert dataset.regions() == ("britain", "iberia")
    assert dataset.sources() == ("steppe",)
    assert dataset.sample_ids() == ("SYN001", "SYN002", "SYN003")
    assert dataset.filter(region="britain").records == (first,)
    assert dataset.filter(source="steppe").records == (first, second)
    assert dataset.filter(status="synthetic").records == (first, second)
    assert dataset.missing_sample_ids(_sample_metadata()) == ("SYN003",)


def test_target_curation_dataset_rejects_duplicate_ids() -> None:
    """Target IDs should be unique within a curation dataset."""
    with pytest.raises(ValueError, match="unique"):
        TargetCurationDataset.from_rows((_record("target-1"), _record("target-1")))


def test_target_curation_dataset_requires_records() -> None:
    """Empty curation datasets should fail before use."""
    dataset = TargetCurationDataset.from_rows(())

    with pytest.raises(ValueError, match="at least one"):
        dataset.require_records()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": "unknown"},
        {"target_id": ""},
        {"region": ""},
        {"source": ""},
        {"ancestry_method": ""},
        {"aggregation_method": ""},
        {"citation_key": ""},
        {"citation": ""},
        {"start_bce": float("nan")},
        {"end_bce": float("nan")},
        {"start_bce": 2700, "end_bce": 3000},
        {"sample_ids": ()},
        {"sample_ids": ("SYN001", "SYN001")},
        {"sample_count": 0},
        {"sample_count": 3},
    ],
)
def test_target_curation_record_rejects_invalid_fields(
    kwargs: dict[str, object],
) -> None:
    """Invalid target curation fields should fail at construction."""
    values = {
        "status": "synthetic",
        "target_id": "target-1",
        "region": "britain",
        "source": "steppe",
        "start_bce": 3000.0,
        "end_bce": 2800.0,
        "sample_ids": ("SYN001", "SYN002"),
        "sample_count": 2,
        "ancestry_method": "synthetic_ancestry_estimate",
        "aggregation_method": "synthetic_mean",
        "citation_key": "synthetic-curation",
        "citation": "Synthetic curation example",
    }
    values.update(kwargs)

    with pytest.raises(ValueError):
        TargetCurationRecord(**values)  # type: ignore[arg-type]


def test_load_target_curation_reads_csv(tmp_path: Path) -> None:
    """Target curation CSV files should load into validated datasets."""
    curation_path = tmp_path / "target-curation.csv"
    curation_path.write_text(
        _csv_text(_csv_row(note="First row"), _csv_row(target_id="target-2", note="")),
        encoding="utf-8",
    )

    dataset = load_target_curation(curation_path)

    assert dataset.target_ids() == ("target-1", "target-2")
    assert dataset.records[0].sample_ids == ("SYN001", "SYN002")
    assert dataset.records[0].note == "First row"
    assert dataset.records[1].note == ""


def test_target_curation_csv_exports_round_trip(tmp_path: Path) -> None:
    """Target curation rows should export and load through the public schema."""
    output_path = tmp_path / "outputs" / "target-curation.csv"
    dataset = TargetCurationDataset.from_rows((_record(note="Exported row"),))

    returned_path = write_target_curation_csv(dataset, output_path)
    output_text = target_curation_to_csv(dataset)
    rows = target_curation_rows(dataset)
    loaded = load_target_curation(output_path)

    assert returned_path == output_path
    assert output_text.startswith("status,target_id,region")
    assert rows[0]["sample_ids"] == "SYN001;SYN002"
    assert loaded.records[0].note == "Exported row"


def test_load_target_curation_rejects_missing_header(tmp_path: Path) -> None:
    """CSV files without a header should fail clearly."""
    curation_path = tmp_path / "target-curation.csv"
    curation_path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="header"):
        load_target_curation(curation_path)


def test_load_target_curation_rejects_missing_columns(tmp_path: Path) -> None:
    """CSV files missing required columns should fail clearly."""
    curation_path = tmp_path / "target-curation.csv"
    curation_path.write_text("status,target_id\nsynthetic,target-1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing columns"):
        load_target_curation(curation_path)


@pytest.mark.parametrize(
    "row",
    [
        _csv_row(status="unknown"),
        _csv_row(target_id=""),
        _csv_row(sample_ids=""),
        _csv_row(sample_count="not-an-int"),
    ],
)
def test_load_target_curation_reports_row_errors(
    tmp_path: Path, row: tuple[str, ...]
) -> None:
    """CSV row errors should include the row number."""
    curation_path = tmp_path / "target-curation.csv"
    curation_path.write_text(_csv_text(row), encoding="utf-8")

    with pytest.raises(ValueError, match="row 2"):
        load_target_curation(curation_path)


def test_load_target_curation_handles_missing_optional_note(tmp_path: Path) -> None:
    """Rows shorter than the optional note column should get an empty note."""
    curation_path = tmp_path / "target-curation.csv"
    curation_path.write_text(_csv_text(_csv_row()[:-1]), encoding="utf-8")

    dataset = load_target_curation(curation_path)

    assert dataset.records[0].note == ""
