"""Tests for sample-level ancestry estimate records."""

from pathlib import Path

import pytest

from indoeuropop.data.ancestry_estimates import (
    ANCESTRY_ESTIMATE_COLUMNS,
    SampleAncestryEstimate,
    SampleAncestryEstimateDataset,
    load_sample_ancestry_estimates,
    sample_ancestry_estimate_rows,
    sample_ancestry_estimates_to_csv,
    write_sample_ancestry_estimates_csv,
)


def _estimate(
    sample_id: str = "SYN001",
    *,
    source: str = "steppe",
    method: str = "synthetic_ancestry_estimate",
    status: str = "synthetic",
) -> SampleAncestryEstimate:
    """Build one sample ancestry estimate for tests."""
    return SampleAncestryEstimate(
        status=status,  # type: ignore[arg-type]
        sample_id=sample_id,
        source=source,
        estimate=0.2,
        standard_error=0.05,
        method=method,
        note="Example estimate",
    )


def _csv_text(*rows: tuple[str, ...]) -> str:
    """Return sample ancestry estimate CSV text from rows of cell values."""
    header = ",".join(ANCESTRY_ESTIMATE_COLUMNS)
    return "\n".join((header, *((",".join(row)) for row in rows)))


def _csv_row(
    *,
    status: str = "synthetic",
    sample_id: str = "SYN001",
    estimate: str = "0.2",
    standard_error: str = "0.05",
    note: str = "Example estimate",
) -> tuple[str, ...]:
    """Return one complete sample ancestry estimate CSV row."""
    return (
        status,
        sample_id,
        "steppe",
        estimate,
        standard_error,
        "synthetic_ancestry_estimate",
        note,
    )


def test_sample_ancestry_estimate_dataset_summarizes_records() -> None:
    """Estimate datasets should expose filters and identity summaries."""
    first = _estimate("SYN001")
    second = _estimate("SYN002", source="local", method="qpadm_like")
    dataset = SampleAncestryEstimateDataset.from_rows((first, second))

    assert dataset.estimate_count == 2
    assert dataset.sample_ids() == ("SYN001", "SYN002")
    assert dataset.sources() == ("steppe", "local")
    assert dataset.methods() == ("synthetic_ancestry_estimate", "qpadm_like")
    assert dataset.filter(source="steppe").estimates == (first,)
    assert dataset.filter(status="synthetic").estimate_count == 2
    assert (
        dataset.estimate_for(
            sample_id="SYN002",
            source="local",
            method="qpadm_like",
        )
        == second
    )


def test_sample_ancestry_estimate_dataset_rejects_duplicate_keys() -> None:
    """Sample, source, and method identify one estimate row."""
    with pytest.raises(ValueError, match="unique"):
        SampleAncestryEstimateDataset.from_rows((_estimate(), _estimate()))


def test_sample_ancestry_estimate_dataset_requires_estimates() -> None:
    """Empty estimate datasets should fail before pipeline use."""
    dataset = SampleAncestryEstimateDataset.from_rows(())

    with pytest.raises(ValueError, match="at least one"):
        dataset.require_estimates()


def test_sample_ancestry_estimate_dataset_reports_missing_estimate() -> None:
    """Lookup failures should include the missing estimate identity."""
    dataset = SampleAncestryEstimateDataset.from_rows((_estimate(),))

    with pytest.raises(ValueError, match="missing ancestry estimate"):
        dataset.estimate_for(
            sample_id="SYN002",
            source="steppe",
            method="synthetic_ancestry_estimate",
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": "unknown"},
        {"sample_id": ""},
        {"source": ""},
        {"method": ""},
        {"estimate": -0.1},
        {"estimate": 1.1},
        {"estimate": float("nan")},
        {"standard_error": 0.0},
        {"standard_error": 1.1},
        {"standard_error": float("nan")},
    ],
)
def test_sample_ancestry_estimate_rejects_invalid_fields(
    kwargs: dict[str, object],
) -> None:
    """Invalid estimate fields should fail at construction."""
    values = {
        "status": "synthetic",
        "sample_id": "SYN001",
        "source": "steppe",
        "estimate": 0.2,
        "standard_error": 0.05,
        "method": "synthetic_ancestry_estimate",
    }
    values.update(kwargs)

    with pytest.raises(ValueError):
        SampleAncestryEstimate(**values)  # type: ignore[arg-type]


def test_load_sample_ancestry_estimates_reads_csv(tmp_path: Path) -> None:
    """Sample ancestry estimate CSV files should load into datasets."""
    estimate_path = tmp_path / "sample-ancestry.csv"
    estimate_path.write_text(
        _csv_text(
            _csv_row(sample_id="SYN001", note="First row"),
            _csv_row(sample_id="SYN002", estimate="0.3", note=""),
        ),
        encoding="utf-8",
    )

    dataset = load_sample_ancestry_estimates(estimate_path)

    assert dataset.estimate_count == 2
    assert dataset.estimates[0].note == "First row"
    assert dataset.estimates[1].note == ""
    assert dataset.estimates[1].estimate == 0.3


def test_sample_ancestry_estimates_csv_exports_round_trip(tmp_path: Path) -> None:
    """Sample ancestry estimates should export through the public schema."""
    output_path = tmp_path / "outputs" / "sample-ancestry.csv"
    dataset = SampleAncestryEstimateDataset.from_rows((_estimate(),))

    returned_path = write_sample_ancestry_estimates_csv(dataset, output_path)
    output_text = sample_ancestry_estimates_to_csv(dataset)
    rows = sample_ancestry_estimate_rows(dataset)
    loaded = load_sample_ancestry_estimates(output_path)

    assert returned_path == output_path
    assert output_text.startswith("status,sample_id,source")
    assert rows[0]["estimate"] == "0.2"
    assert loaded.estimates[0].note == "Example estimate"


def test_load_sample_ancestry_estimates_rejects_missing_header(
    tmp_path: Path,
) -> None:
    """CSV files without a header should fail clearly."""
    estimate_path = tmp_path / "sample-ancestry.csv"
    estimate_path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="header"):
        load_sample_ancestry_estimates(estimate_path)


def test_load_sample_ancestry_estimates_rejects_missing_columns(
    tmp_path: Path,
) -> None:
    """CSV files missing required columns should fail clearly."""
    estimate_path = tmp_path / "sample-ancestry.csv"
    estimate_path.write_text("status,sample_id\nsynthetic,SYN001\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing columns"):
        load_sample_ancestry_estimates(estimate_path)


@pytest.mark.parametrize(
    "row",
    [
        _csv_row(status="unknown"),
        _csv_row(sample_id=""),
        _csv_row(estimate="not-a-number"),
        _csv_row(standard_error="0"),
    ],
)
def test_load_sample_ancestry_estimates_reports_row_errors(
    tmp_path: Path, row: tuple[str, ...]
) -> None:
    """CSV row errors should include row number context."""
    estimate_path = tmp_path / "sample-ancestry.csv"
    estimate_path.write_text(_csv_text(row), encoding="utf-8")

    with pytest.raises(ValueError, match="row 2"):
        load_sample_ancestry_estimates(estimate_path)


def test_load_sample_ancestry_estimates_handles_missing_optional_note(
    tmp_path: Path,
) -> None:
    """Rows shorter than the optional note column should get an empty note."""
    estimate_path = tmp_path / "sample-ancestry.csv"
    estimate_path.write_text(_csv_text(_csv_row()[:-1]), encoding="utf-8")

    dataset = load_sample_ancestry_estimates(estimate_path)

    assert dataset.estimates[0].note == ""


def test_example_sample_ancestry_estimates_load() -> None:
    """The checked-in estimate example should follow the estimate schema."""
    dataset = load_sample_ancestry_estimates(
        "examples/sample-ancestry-estimates.example.csv"
    )

    assert dataset.sample_ids() == ("SYN001",)
    assert dataset.sources() == ("steppe",)
