"""Tests for converting qpAdm-style tables into sample ancestry estimates."""

from pathlib import Path

import pytest

from indoeuropop.ancestry_estimates import load_sample_ancestry_estimates
from indoeuropop.qpadm_estimates import (
    QpAdmEstimate,
    load_qpadm_estimate_table,
    load_qpadm_sample_ancestry_estimates,
    parse_qpadm_estimate_table,
    qpadm_estimates_to_sample_ancestry_dataset,
    write_qpadm_sample_ancestry_estimates_csv,
)


def _qpadm_csv() -> str:
    """Return a small qpAdm-like CSV table."""
    return "\n".join(
        (
            "Genetic ID,steppe_fraction,stderr,qpadm_pvalue",
            "I001,0.9,0.03,0.12",
            "I002,0.7,0.04,0.5",
            "I001,0.99,0.01,0.01",
            "BAD,1.5,0.1,0.2",
            "EMPTY,,0.1,0.2",
            "NOSE,0.5,,0.3",
            "BADSE,0.4,bad,0.3",
            "HIGHSE,0.6,2.0,2.0",
        )
    )


def test_qpadm_estimate_validation() -> None:
    """QpAdm estimates should validate finite proportions."""
    QpAdmEstimate("I001", 0.5, 0.1, 0.2)

    with pytest.raises(ValueError, match="sample_id"):
        QpAdmEstimate("", 0.5)
    with pytest.raises(ValueError, match="steppe_fraction"):
        QpAdmEstimate("I001", 1.2)
    with pytest.raises(ValueError, match="standard_error"):
        QpAdmEstimate("I001", 0.5, 0)
    with pytest.raises(ValueError, match="p_value"):
        QpAdmEstimate("I001", 0.5, 0.1, 1.2)


def test_parse_qpadm_estimate_table_reads_csv_and_skips_bad_rows() -> None:
    """The tolerant qpAdm parser should keep first valid sample occurrences."""
    estimates = parse_qpadm_estimate_table(_qpadm_csv().splitlines())

    assert tuple(estimate.sample_id for estimate in estimates) == (
        "I001",
        "I002",
        "NOSE",
        "BADSE",
        "HIGHSE",
    )
    assert estimates[0].steppe_fraction == pytest.approx(0.9)
    assert estimates[0].standard_error == pytest.approx(0.03)
    assert estimates[0].p_value == pytest.approx(0.12)
    assert estimates[2].standard_error is None
    assert estimates[4].standard_error is None
    assert estimates[4].p_value is None


def test_parse_qpadm_estimate_table_reads_tsv_without_optional_columns() -> None:
    """TSV qpAdm outputs without uncertainty should still parse raw estimates."""
    estimates = parse_qpadm_estimate_table(["sample_id\tsteppe", "S1\t0.5"])

    assert estimates == (QpAdmEstimate("S1", 0.5),)


def test_parse_qpadm_estimate_table_matches_descriptive_headers() -> None:
    """Substring header matching should handle verbose qpAdm table exports."""
    estimates = parse_qpadm_estimate_table(
        [
            "sample_id,qpAdm steppe weight,stderr,qpadm_pvalue",
            "S1,0.5,0.03",
        ]
    )

    assert estimates == (QpAdmEstimate("S1", 0.5, 0.03),)


def test_parse_qpadm_estimate_table_rejects_empty_or_missing_columns() -> None:
    """qpAdm tables need both sample and steppe columns."""
    with pytest.raises(ValueError, match="header"):
        parse_qpadm_estimate_table([])
    with pytest.raises(ValueError, match="sample ID and steppe"):
        parse_qpadm_estimate_table(["name,value", "I001,0.5"])


def test_load_qpadm_estimate_table_reads_file(tmp_path: Path) -> None:
    """QpAdm estimate tables should load from disk."""
    table_path = tmp_path / "qpadm.csv"
    table_path.write_text(_qpadm_csv(), encoding="utf-8")

    estimates = load_qpadm_estimate_table(table_path)

    assert estimates[1].sample_id == "I002"


def test_qpadm_estimates_convert_to_sample_ancestry_dataset() -> None:
    """QpAdm estimates should convert into target-pipeline estimate rows."""
    estimates = (QpAdmEstimate("I001", 0.9, 0.03, 0.12),)

    dataset = qpadm_estimates_to_sample_ancestry_dataset(
        estimates,
        source="steppe",
        method="qpAdm_v1",
    )

    assert dataset.estimate_count == 1
    assert dataset.estimates[0].status == "published"
    assert dataset.estimates[0].standard_error == pytest.approx(0.03)
    assert "qpadm_pvalue=0.12" in dataset.estimates[0].note


def test_qpadm_conversion_uses_default_standard_error() -> None:
    """A documented default standard error can fill uncertainty-free rows."""
    dataset = qpadm_estimates_to_sample_ancestry_dataset(
        (QpAdmEstimate("I001", 0.9),),
        default_standard_error=0.05,
    )

    assert dataset.estimates[0].standard_error == pytest.approx(0.05)


def test_qpadm_conversion_requires_standard_error_without_default() -> None:
    """Uncertainty-free qpAdm rows should not silently become target inputs."""
    with pytest.raises(ValueError, match="missing standard error"):
        qpadm_estimates_to_sample_ancestry_dataset((QpAdmEstimate("I001", 0.9),))


def test_qpadm_conversion_can_skip_missing_standard_errors() -> None:
    """Uncertainty-free qpAdm rows can be explicitly skipped."""
    dataset = qpadm_estimates_to_sample_ancestry_dataset(
        (QpAdmEstimate("I001", 0.9), QpAdmEstimate("I002", 0.7, 0.04)),
        skip_missing_standard_error=True,
    )

    assert dataset.sample_ids() == ("I002",)


def test_load_qpadm_sample_ancestry_estimates_filters_rows(
    tmp_path: Path,
) -> None:
    """Loading directly as sample estimates should preserve valid uncertainty rows."""
    table_path = tmp_path / "qpadm.csv"
    table_path.write_text(_qpadm_csv(), encoding="utf-8")

    dataset = load_qpadm_sample_ancestry_estimates(
        table_path,
        default_standard_error=0.05,
    )

    assert dataset.sample_ids() == ("I001", "I002", "NOSE", "BADSE", "HIGHSE")
    assert dataset.estimates[2].standard_error == pytest.approx(0.05)


def test_write_qpadm_sample_ancestry_estimates_csv_round_trips(
    tmp_path: Path,
) -> None:
    """The qpAdm writer should produce the project estimate CSV schema."""
    table_path = tmp_path / "qpadm.csv"
    output_path = tmp_path / "outputs" / "sample-ancestry.csv"
    table_path.write_text(_qpadm_csv(), encoding="utf-8")

    returned_path = write_qpadm_sample_ancestry_estimates_csv(
        table_path,
        output_path,
        default_standard_error=0.05,
    )
    loaded = load_sample_ancestry_estimates(output_path)

    assert returned_path == output_path
    assert loaded.estimate_count == 5
    assert loaded.estimates[0].method == "qpadm_steppe"
