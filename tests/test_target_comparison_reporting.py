"""Tests for target-comparison residual reporting."""

from pathlib import Path

import pytest

from indoeuropop.data.targets import TargetComparison, TargetDataset, TargetObservation
from indoeuropop.models import PopulationState, SimulationResult
from indoeuropop.reporting.target_comparison import (
    target_comparison_rows,
    target_comparisons_to_csv,
    write_target_comparisons_csv,
)


def _comparisons() -> tuple[TargetComparison, ...]:
    """Return one target comparison against a tiny simulation result."""
    result = SimulationResult(
        (3000, 2900),
        (
            PopulationState({"britain": {"local": 100, "steppe": 0}}),
            PopulationState({"britain": {"local": 80, "steppe": 20}}),
        ),
    )
    targets = TargetDataset.from_rows(
        [
            TargetObservation(
                status="synthetic",
                region="britain",
                source="steppe",
                time_bce=2900,
                mean=0.1,
                uncertainty=0.05,
                citation_key="synthetic",
                citation="Synthetic target",
                note="Example",
            )
        ]
    )
    return targets.compare(result)


def test_target_comparison_rows_include_residual_fields() -> None:
    """Residual rows should keep observed and predicted values together."""
    rows = target_comparison_rows(_comparisons())

    assert rows[0]["region"] == "britain"
    assert rows[0]["observed_mean"] == "0.1"
    assert rows[0]["predicted"] == "0.2"
    assert rows[0]["residual"] == "0.1"
    assert rows[0]["z_score"] == "2"


def test_target_comparisons_to_csv_writes_stable_header() -> None:
    """Residual CSV text should use stable column names."""
    output = target_comparisons_to_csv(_comparisons())

    assert output.startswith("target_index,status,region,source")
    assert "synthetic,britain,steppe,2900" in output


def test_write_target_comparisons_csv_creates_parent_directory(tmp_path: Path) -> None:
    """Residual CSV files should be written through the public helper."""
    output_path = tmp_path / "reports" / "residuals.csv"

    returned_path = write_target_comparisons_csv(_comparisons(), output_path)

    assert returned_path == output_path
    assert "predicted" in output_path.read_text(encoding="utf-8")


def test_target_comparison_reporting_rejects_empty_rows() -> None:
    """Empty comparison exports should fail clearly."""
    with pytest.raises(ValueError, match="at least one"):
        target_comparison_rows(())
