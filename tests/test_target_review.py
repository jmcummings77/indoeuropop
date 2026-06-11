"""Tests for target residual review reports."""

from pathlib import Path

import pytest

from indoeuropop.reporting.target_review import (
    TargetResidualReview,
    TargetResidualReviewRow,
    load_target_residual_review,
    load_target_residual_review_rows,
    target_residual_review_markdown,
    write_target_residual_review_markdown,
)


def _residual_csv() -> str:
    """Return target residual CSV text for review tests."""
    return "\n".join(
        (
            "target_index,status,region,source,time_bce,observed_mean,uncertainty,"
            "predicted,residual,z_score,citation_key,citation,note",
            "1,published,central_europe,steppe,2235,0.02,0.1,0.5,0.48,4.8,key,"
            "Citation,requested_group_id=Germany_StkrStraubing_BellBeaker; "
            "target_id=target-1",
            "2,published,britain,steppe,2172,0.42,0.2,0.44,0.02,0.1,key,"
            "Citation,requested_group_id=England_BellBeaker; target_id=target-2",
        )
    )


def test_load_target_residual_review_rows_extracts_groups(tmp_path: Path) -> None:
    """Residual review rows should parse numeric fields and group IDs."""
    residuals_path = tmp_path / "target-residuals.csv"
    residuals_path.write_text(_residual_csv(), encoding="utf-8")

    rows = load_target_residual_review_rows(residuals_path)

    assert len(rows) == 2
    assert rows[0].requested_group_id == "Germany_StkrStraubing_BellBeaker"
    assert rows[0].abs_z_score == 4.8


def test_target_residual_review_markdown_ranks_outliers(tmp_path: Path) -> None:
    """Markdown reports should summarize outliers and region diagnostics."""
    residuals_path = tmp_path / "target-residuals.csv"
    diagnostics_path = tmp_path / "diagnostics.json"
    residuals_path.write_text(_residual_csv(), encoding="utf-8")
    diagnostics_path.write_text(
        '{"requested_target_count": 38, "retained_target_count": 12, '
        '"dropped_target_count": 26, "retained_sample_count": 63, '
        '"target_observation_count": 12}',
        encoding="utf-8",
    )

    review = load_target_residual_review(
        residuals_path,
        diagnostics_path=diagnostics_path,
        outlier_z_threshold=2.0,
    )
    markdown = target_residual_review_markdown(review)

    assert len(review.outliers) == 1
    assert "top_outlier_group: Germany_StkrStraubing_BellBeaker" in markdown
    assert "Review qpAdm model choices" in markdown
    assert "| central_europe | 1 | 0.48 | 4.8 |" in markdown
    assert "- dropped_target_count: 26" in markdown


def test_write_target_residual_review_markdown_creates_parent(tmp_path: Path) -> None:
    """Review markdown should be writable through the public helper."""
    residuals_path = tmp_path / "target-residuals.csv"
    output_path = tmp_path / "reports" / "target-review.md"
    residuals_path.write_text(_residual_csv(), encoding="utf-8")
    review = load_target_residual_review(residuals_path)

    returned_path = write_target_residual_review_markdown(review, output_path)

    assert returned_path == output_path
    assert output_path.read_text(encoding="utf-8").startswith("# Target Residual")


def test_target_residual_review_recommends_dropped_target_review(
    tmp_path: Path,
) -> None:
    """Dropped-target-heavy runs should recommend target coverage review."""
    residuals_path = tmp_path / "target-residuals.csv"
    residuals_path.write_text(
        _residual_csv().replace("4.8", "0.8").replace("0.48", "0.08"),
        encoding="utf-8",
    )
    rows = load_target_residual_review_rows(residuals_path)

    review = TargetResidualReview(rows=rows, diagnostics={"dropped_target_count": 5})

    assert review.outliers == ()
    assert "dropped target rows" in review.recommendation


def test_target_residual_review_recommends_parameter_refinement(
    tmp_path: Path,
) -> None:
    """Runs without outliers or heavy drops can move to parameter refinement."""
    residuals_path = tmp_path / "target-residuals.csv"
    residuals_path.write_text(
        _residual_csv().replace("4.8", "0.8").replace("0.48", "0.08"),
        encoding="utf-8",
    )
    rows = load_target_residual_review_rows(residuals_path)

    review = TargetResidualReview(rows=rows)

    assert "parameter-range refinement" in review.recommendation


def test_target_residual_review_validates_inputs(tmp_path: Path) -> None:
    """Residual review loaders should reject malformed inputs clearly."""
    residuals_path = tmp_path / "target-residuals.csv"
    residuals_path.write_text("target_index,region\n", encoding="utf-8")
    empty_path = tmp_path / "empty.csv"
    empty_path.write_text("", encoding="utf-8")
    header_only_path = tmp_path / "header-only.csv"
    header_only_path.write_text(
        _residual_csv().splitlines()[0] + "\n", encoding="utf-8"
    )
    invalid_row_path = tmp_path / "invalid-row.csv"
    invalid_row_path.write_text(
        _residual_csv().replace("central_europe", "", 1),
        encoding="utf-8",
    )
    diagnostics_path = tmp_path / "diagnostics.json"
    diagnostics_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="missing columns"):
        load_target_residual_review_rows(residuals_path)
    with pytest.raises(ValueError, match="header"):
        load_target_residual_review_rows(empty_path)
    with pytest.raises(ValueError, match="at least one row"):
        load_target_residual_review_rows(header_only_path)
    with pytest.raises(ValueError, match="invalid target residual"):
        load_target_residual_review_rows(invalid_row_path)
    with pytest.raises(ValueError, match="JSON"):
        load_target_residual_review(
            tmp_path / "missing.csv", diagnostics_path=diagnostics_path
        )
    valid_rows = load_target_residual_review_rows(
        _write_residual_csv(tmp_path, _residual_csv())
    )
    with pytest.raises(ValueError, match="at least one residual"):
        TargetResidualReview(rows=())
    with pytest.raises(ValueError, match="positive"):
        TargetResidualReview(rows=valid_rows, outlier_z_threshold=0)


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"target_index": 0}, "target_index"),
        ({"region": ""}, "region"),
        ({"time_bce": float("nan")}, "time_bce"),
        ({"uncertainty": 0.0}, "uncertainty"),
    ],
)
def test_target_residual_review_row_validates_fields(
    kwargs: dict[str, object], match: str
) -> None:
    """Review rows should reject invalid scalar fields."""
    values = {
        "target_index": 1,
        "region": "central_europe",
        "source": "steppe",
        "time_bce": 2235.0,
        "observed_mean": 0.02,
        "uncertainty": 0.1,
        "predicted": 0.5,
        "residual": 0.48,
        "z_score": 4.8,
        "requested_group_id": "Germany_StkrStraubing_BellBeaker",
    }
    values.update(kwargs)

    with pytest.raises(ValueError, match=match):
        TargetResidualReviewRow(**values)  # type: ignore[arg-type]


def test_target_residual_review_handles_missing_group_note(tmp_path: Path) -> None:
    """Rows without requested group notes should still load for review."""
    residuals_path = tmp_path / "target-residuals.csv"
    residuals_path.write_text(
        _residual_csv().replace(
            "requested_group_id=Germany_StkrStraubing_BellBeaker; target_id=target-1",
            "",
        ),
        encoding="utf-8",
    )

    rows = load_target_residual_review_rows(residuals_path)

    assert rows[0].requested_group_id == ""


def _write_residual_csv(tmp_path: Path, contents: str) -> Path:
    """Write residual CSV contents for validation tests."""
    residuals_path = tmp_path / "valid-target-residuals.csv"
    residuals_path.write_text(contents, encoding="utf-8")
    return residuals_path
