"""CLI tests for target curation audit reports."""

from pathlib import Path

from pytest import CaptureFixture, raises

from indoeuropop.orchestration.cli import main


def test_cli_audit_target_curation_writes_markdown(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should write a target curation audit report."""
    paths = _write_cli_inputs(tmp_path)
    output_path = tmp_path / "reports" / "audit.md"

    exit_code = main(
        [
            "audit-target-curation",
            "--target-residuals",
            str(paths["residuals"]),
            "--target-curation",
            str(paths["curation"]),
            "--sample-metadata",
            str(paths["metadata"]),
            "--ancestry-estimates",
            str(paths["estimates"]),
            "--target-audit-md",
            str(output_path),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"target_audit={output_path}" in captured.out
    assert "target_id=target-stkr" in captured.out
    assert "sample_count=1" in captured.out
    assert "Germany_StkrStraubing_BellBeaker" in output_path.read_text(encoding="utf-8")


def test_cli_audit_target_curation_can_print_markdown(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should print audit Markdown when no output path is supplied."""
    paths = _write_cli_inputs(tmp_path)

    exit_code = main(
        [
            "audit-target-curation",
            "--target-residuals",
            str(paths["residuals"]),
            "--target-curation",
            str(paths["curation"]),
            "--sample-metadata",
            str(paths["metadata"]),
            "--ancestry-estimates",
            str(paths["estimates"]),
            "--target-id",
            "target-stkr",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "# Target Curation Audit" in captured.out
    assert "missing_metadata_count=0" in captured.out


def test_cli_audit_target_curation_requires_inputs() -> None:
    """The CLI should reject missing audit input paths."""
    with raises(SystemExit) as exc_info:
        main(["audit-target-curation"])
    assert exc_info.value.code == 2


def _write_cli_inputs(tmp_path: Path) -> dict[str, Path]:
    """Write compact audit input CSV files for CLI tests."""
    paths = {
        "residuals": tmp_path / "target-residuals.csv",
        "curation": tmp_path / "target-curation.csv",
        "metadata": tmp_path / "metadata.csv",
        "estimates": tmp_path / "estimates.csv",
    }
    paths["residuals"].write_text(
        "\n".join(
            (
                "target_index,status,region,source,time_bce,observed_mean,"
                "uncertainty,predicted,residual,z_score,citation_key,citation,note",
                "1,published,central_europe,steppe,2235,0.02,0.1,0.5,0.48,4.8,"
                "key,Citation,requested_group_id=Germany_StkrStraubing_BellBeaker; "
                "target_id=target-stkr",
            )
        ),
        encoding="utf-8",
    )
    paths["curation"].write_text(
        "\n".join(
            (
                "status,target_id,region,source,start_bce,end_bce,sample_ids,"
                "sample_count,ancestry_method,aggregation_method,citation_key,"
                "citation,note",
                "published,target-stkr,central_europe,steppe,2300,2200,S1,1,"
                "qpadm_steppe,unweighted_mean,key,Citation,"
                "requested_group_id=Germany_StkrStraubing_BellBeaker",
            )
        ),
        encoding="utf-8",
    )
    paths["metadata"].write_text(
        "\n".join(
            (
                "status,dataset_id,sample_id,accession_id,publication_key,"
                "publication,region,site,time_bce,date_uncertainty,sex,method,note",
                "published,aadr,S1,1,Pub1,doi,central_europe,Site,2250,50,"
                "female,aadr,assessment=Pass",
            )
        ),
        encoding="utf-8",
    )
    paths["estimates"].write_text(
        "\n".join(
            (
                "status,sample_id,source,estimate,standard_error,method,note",
                "published,S1,steppe,0.02,0.3,qpadm_steppe,"
                "source_table=qpAdm; qpadm_pvalue=0.5",
            )
        ),
        encoding="utf-8",
    )
    return paths
