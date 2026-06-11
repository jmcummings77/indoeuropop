"""CLI tests for reviewed target-decision filtering."""

from pathlib import Path

from pytest import CaptureFixture, raises

from indoeuropop.orchestration.cli import main


def test_cli_apply_target_decisions_writes_filtered_inputs(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should write decision-filtered sample and curation CSVs."""
    paths = _write_inputs(tmp_path)
    sample_output = tmp_path / "outputs" / "filtered-samples.csv"
    curation_output = tmp_path / "outputs" / "filtered-curation.csv"

    exit_code = main(
        [
            "apply-target-decisions",
            "--sample-metadata",
            str(paths["metadata"]),
            "--target-curation",
            str(paths["curation"]),
            "--target-decisions",
            str(paths["decisions"]),
            "--sample-metadata-out",
            str(sample_output),
            "--target-curation-out",
            str(curation_output),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "decision_filtered_sample_count=2" in captured.out
    assert "decision_deferred_target=target-drop" in captured.out
    assert "decision_undecided_target=target-undecided" in captured.out
    assert "target-drop" not in curation_output.read_text(encoding="utf-8")
    assert "S2" not in sample_output.read_text(encoding="utf-8")


def test_cli_apply_target_decisions_requires_initial_paths() -> None:
    """The CLI should reject incomplete decision-filtering arguments."""
    with raises(SystemExit) as exc_info:
        main(["apply-target-decisions"])
    assert exc_info.value.code == 2


def test_cli_apply_target_decisions_requires_output_paths(tmp_path: Path) -> None:
    """The CLI should reject missing decision-filtering output paths."""
    paths = _write_inputs(tmp_path)

    with raises(SystemExit) as sample_exc_info:
        main(
            [
                "apply-target-decisions",
                "--sample-metadata",
                str(paths["metadata"]),
                "--target-curation",
                str(paths["curation"]),
                "--target-decisions",
                str(paths["decisions"]),
            ]
        )
    with raises(SystemExit) as curation_exc_info:
        main(
            [
                "apply-target-decisions",
                "--sample-metadata",
                str(paths["metadata"]),
                "--target-curation",
                str(paths["curation"]),
                "--target-decisions",
                str(paths["decisions"]),
                "--sample-metadata-out",
                str(tmp_path / "samples.csv"),
            ]
        )

    assert sample_exc_info.value.code == 2
    assert curation_exc_info.value.code == 2


def _write_inputs(tmp_path: Path) -> dict[str, Path]:
    """Write compact target-decision CLI fixtures."""
    paths = {
        "metadata": tmp_path / "sample-metadata.csv",
        "curation": tmp_path / "target-curation.csv",
        "decisions": tmp_path / "target-decisions.csv",
    }
    paths["metadata"].write_text(
        "\n".join(
            (
                "status,dataset_id,sample_id,accession_id,publication_key,"
                "publication,region,site,time_bce,date_uncertainty,sex,method,note",
                "published,dataset,S1,A1,key,Publication,britain,Site,2500,50,"
                "unknown,method,",
                "published,dataset,S2,A2,key,Publication,britain,Site,2500,50,"
                "unknown,method,",
                "published,dataset,S3,A3,key,Publication,britain,Site,2500,50,"
                "unknown,method,",
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
                "published,target-keep,britain,steppe,2600,2400,S1,1,"
                "qpadm_steppe,unweighted_mean,key,Citation,",
                "published,target-drop,britain,steppe,2600,2400,S2,1,"
                "qpadm_steppe,unweighted_mean,key,Citation,",
                "published,target-undecided,britain,steppe,2600,2400,S3,1,"
                "qpadm_steppe,unweighted_mean,key,Citation,",
            )
        ),
        encoding="utf-8",
    )
    paths["decisions"].write_text(
        "\n".join(
            (
                "target_id,decision,reason,requested_group_id,reviewer,"
                "decision_date,note",
                "target-keep,retain,usable,Group,Reviewer,2026-06-11,",
                "target-drop,rerun_qpadm,needs rerun,Group,Reviewer,2026-06-11,",
            )
        ),
        encoding="utf-8",
    )
    return paths
