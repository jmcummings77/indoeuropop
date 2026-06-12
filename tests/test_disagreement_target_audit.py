"""Tests for batch audits of structural SMC disagreement targets."""

from __future__ import annotations

from math import nan
from pathlib import Path

import pytest
from pytest import CaptureFixture

from indoeuropop.data.target_curation import TargetCurationRecord
from indoeuropop.orchestration.cli import main
from indoeuropop.reporting.disagreement_target_audit import (
    disagreement_target_audit_sample_rows,
    disagreement_target_audit_samples_to_csv,
    load_disagreement_target_curation_audit,
    write_disagreement_target_audit_samples_csv,
)
from indoeuropop.reporting.disagreement_target_audit_models import (
    DisagreementTargetCurationAudit,
    DisagreementTargetCurationAuditReport,
    target_curation_sample_flags,
)
from indoeuropop.reporting.disagreement_target_audit_report import (
    disagreement_target_audit_markdown,
    write_disagreement_target_audit_markdown,
)
from indoeuropop.reporting.target_audit import TargetCurationAuditSample


def test_disagreement_target_audit_joins_samples_and_writes_outputs(
    tmp_path: Path,
) -> None:
    """Batch audits should join disagreement targets to sample-level evidence."""
    paths = _write_batch_inputs(tmp_path)

    report = _load_report(paths)
    rows = disagreement_target_audit_sample_rows(report)
    csv_text = disagreement_target_audit_samples_to_csv(report)
    markdown = disagreement_target_audit_markdown(report)
    csv_path = tmp_path / "reports" / "samples.csv"
    markdown_path = tmp_path / "reports" / "audit.md"

    assert report.target_count == 2
    assert report.sample_count == 3
    assert report.issue_target_count == 2
    assert report.ranked_audits[0].requested_group_id == "GroupA"
    assert rows[0]["sample_id"] == "S1"
    assert rows[1]["has_metadata"] == "false"
    assert rows[1]["sample_flags"] == "missing_metadata|missing_estimate"
    assert "sample_metadata_note" in csv_text
    assert "Structural SMC Disagreement Target Audit" in markdown
    assert "high_se" in markdown
    assert write_disagreement_target_audit_samples_csv(report, csv_path) == csv_path
    assert write_disagreement_target_audit_markdown(report, markdown_path) == (
        markdown_path
    )
    assert csv_path.read_text(encoding="utf-8") == csv_text
    assert markdown_path.read_text(encoding="utf-8") == markdown


def test_disagreement_target_audit_models_expose_review_branches() -> None:
    """Manual audits should expose every recommendation branch."""
    missing = _manual_audit(
        samples=(_sample("S1", estimate=None),),
    )
    critical = _manual_audit(
        samples=(_sample("S1", metadata_note="assessment=CRITICAL"),),
    )
    identical = _manual_audit(
        samples=(
            _sample("S1", estimate=0.2, standard_error=0.1),
            _sample("S2", estimate=0.2, standard_error=0.1),
        ),
    )
    out_of_window = _manual_audit(samples=(_sample("S1", time_bce=2100),))
    clean = _manual_audit(samples=(_sample("S1"),))
    mismatch = _manual_audit(
        publication_keys="Pub1",
        curation=_curation(sample_ids=("S1",), sample_count=1),
        samples=(_sample("S1"), _sample("S2", publication_key="Pub2")),
    )

    assert "Fix missing joins" in missing.recommendation
    assert "CRITICAL" in critical.recommendation
    assert identical.all_estimates_identical is True
    assert "qpAdm source model" in identical.recommendation
    assert "chronology/window" in out_of_window.recommendation
    assert "scenario review" in clean.recommendation
    assert any("sample_count" in issue for issue in mismatch.issues)
    assert any("multiple publication" in issue for issue in mismatch.issues)
    assert any("not all in target notes" in issue for issue in mismatch.issues)
    assert target_curation_sample_flags(out_of_window, out_of_window.samples[0]) == (
        "out_of_window",
    )
    assert "No curation issues detected." in disagreement_target_audit_markdown(
        DisagreementTargetCurationAuditReport((clean,))
    )


def test_disagreement_target_audit_validates_model_values() -> None:
    """Audit dataclasses should reject malformed values."""
    with pytest.raises(ValueError, match="fold_name"):
        _manual_audit(fold_name="")
    with pytest.raises(ValueError, match="observed_mean"):
        _manual_audit(observed_mean=nan)
    with pytest.raises(ValueError, match="uncertainty"):
        _manual_audit(uncertainty=0)
    with pytest.raises(ValueError, match="at least one sample"):
        _manual_audit(samples=())


@pytest.mark.parametrize(
    ("writer", "expected"),
    [
        (lambda path: path.write_text("", encoding="utf-8"), "header row"),
        (
            lambda path: path.write_text("fold_name,target_id\nfold,target\n"),
            "missing columns",
        ),
        (
            lambda path: path.write_text(_disagreement_header() + "\n"),
            "at least one row",
        ),
    ],
)
def test_disagreement_target_audit_rejects_bad_disagreement_csv(
    tmp_path: Path,
    writer: object,
    expected: str,
) -> None:
    """Batch audits should reject malformed disagreement CSVs clearly."""
    paths = _write_batch_inputs(tmp_path)
    assert callable(writer)
    writer(paths["disagreement"])

    with pytest.raises(ValueError, match=expected):
        _load_report(paths)


def test_disagreement_target_audit_rejects_missing_curation(
    tmp_path: Path,
) -> None:
    """Every disagreement row should have matching target curation."""
    paths = _write_batch_inputs(tmp_path)
    paths["curation"].write_text(
        _curation_csv().replace("target-a", "target-missing"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="target_id=target-a"):
        _load_report(paths)


def test_cli_audit_structural_smc_disagreement_targets_writes_outputs(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should write batch audit CSV and Markdown outputs."""
    paths = _write_batch_inputs(tmp_path)
    csv_path = tmp_path / "batch-samples.csv"
    markdown_path = tmp_path / "batch-audit.md"

    exit_code = main(
        [
            "audit-structured-smc-disagreement-targets",
            "--smc-disagreement-csv",
            str(paths["disagreement"]),
            "--target-curation",
            str(paths["curation"]),
            "--sample-metadata",
            str(paths["metadata"]),
            "--ancestry-estimates",
            str(paths["estimates"]),
            "--disagreement-target-audit-csv",
            str(csv_path),
            "--disagreement-target-audit-md",
            str(markdown_path),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"disagreement_target_audit_csv={csv_path}" in captured.out
    assert f"disagreement_target_audit_report={markdown_path}" in captured.out
    assert "disagreement_target_count=2" in captured.out
    assert "GroupA" in markdown_path.read_text(encoding="utf-8")


def test_cli_audit_structural_smc_disagreement_targets_can_print_markdown(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should print Markdown when no batch report path is supplied."""
    paths = _write_batch_inputs(tmp_path)

    exit_code = main(
        [
            "audit-structured-smc-disagreement-targets",
            "--smc-disagreement-csv",
            str(paths["disagreement"]),
            "--target-curation",
            str(paths["curation"]),
            "--sample-metadata",
            str(paths["metadata"]),
            "--ancestry-estimates",
            str(paths["estimates"]),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "# Structural SMC Disagreement Target Audit" in captured.out
    assert "disagreement_target_sample_count=3" in captured.out


def test_cli_audit_structural_smc_disagreement_targets_requires_inputs() -> None:
    """The CLI should reject missing batch-audit inputs."""
    with pytest.raises(SystemExit) as exc_info:
        main(["audit-structured-smc-disagreement-targets"])
    assert exc_info.value.code == 2


def _load_report(paths: dict[str, Path]) -> DisagreementTargetCurationAuditReport:
    """Load a batch audit report from fixture paths."""
    return load_disagreement_target_curation_audit(
        disagreement_csv=paths["disagreement"],
        curation_path=paths["curation"],
        sample_metadata_path=paths["metadata"],
        ancestry_estimates_path=paths["estimates"],
    )


def _write_batch_inputs(tmp_path: Path) -> dict[str, Path]:
    """Write compact batch-audit CSV fixtures."""
    paths = {
        "disagreement": tmp_path / "disagreements.csv",
        "curation": tmp_path / "target-curation.csv",
        "metadata": tmp_path / "metadata.csv",
        "estimates": tmp_path / "estimates.csv",
    }
    paths["disagreement"].write_text(_disagreement_csv(), encoding="utf-8")
    paths["curation"].write_text(_curation_csv(), encoding="utf-8")
    paths["metadata"].write_text(_metadata_csv(), encoding="utf-8")
    paths["estimates"].write_text(_estimates_csv(), encoding="utf-8")
    return paths


def _disagreement_csv() -> str:
    """Return structural SMC disagreement rows for two targets."""
    return "\n".join(
        (
            _disagreement_header(),
            "fold-a,target-a,GroupA,Pub1|Pub2,region,steppe,2300,0.5,0.2,"
            "0.1,0.3,0.2,structured_pulse",
            "fold-b,target-b,GroupB,PubB,region,steppe,2250,0.4,0.1,"
            "0.2,0.1,-0.1,child_override",
        )
    )


def _disagreement_header() -> str:
    """Return required disagreement-target audit columns."""
    return (
        "fold_name,target_id,requested_group_id,publication_keys,region,source,"
        "time_bce,observed_mean,uncertainty,"
        "structured_pulse_absolute_mean_residual,"
        "child_override_absolute_mean_residual,"
        "child_minus_structured_pulse_abs_residual_delta,"
        "target_preferred_candidate"
    )


def _curation_csv() -> str:
    """Return target curation rows for batch audit tests."""
    return "\n".join(
        (
            "status,target_id,region,source,start_bce,end_bce,sample_ids,"
            "sample_count,ancestry_method,aggregation_method,citation_key,citation,"
            "note",
            "published,target-a,region,steppe,2350,2200,S1;S2,2,qpadm_steppe,"
            "unweighted_mean,key,Citation,requested_group_id=GroupA",
            "published,target-b,region,steppe,2350,2200,B1,1,qpadm_steppe,"
            "unweighted_mean,key,Citation,requested_group_id=GroupB",
        )
    )


def _metadata_csv() -> str:
    """Return sample metadata with one missing row in target A."""
    return "\n".join(
        (
            "status,dataset_id,sample_id,accession_id,publication_key,publication,"
            "region,site,time_bce,date_uncertainty,sex,method,note",
            "published,aadr,S1,1,Pub1,doi,region,Site A,2250,20,female,aadr,"
            "assessment=Pass",
            "published,aadr,B1,2,PubB,doi,region,Site | B,2100,10,male,aadr,"
            "assessment=CRITICAL",
        )
    )


def _estimates_csv() -> str:
    """Return sample ancestry estimates with one missing row and one missing p-value."""
    return "\n".join(
        (
            "status,sample_id,source,estimate,standard_error,method,note",
            "published,S1,steppe,0.2,0.3,qpadm_steppe,"
            "source_table=qpAdm; qpadm_pvalue=0.5",
            "published,B1,steppe,0.4,0.1,qpadm_steppe,source_table=qpAdm",
        )
    )


def _manual_audit(
    *,
    fold_name: str = "fold",
    observed_mean: float = 0.5,
    uncertainty: float = 0.1,
    publication_keys: str = "Pub1|Pub2",
    curation: TargetCurationRecord | None = None,
    samples: tuple[TargetCurationAuditSample, ...] | None = None,
) -> DisagreementTargetCurationAudit:
    """Return a directly constructed disagreement target audit."""
    return DisagreementTargetCurationAudit(
        fold_name=fold_name,
        target_id="target",
        requested_group_id="group",
        target_preferred_candidate="structured_pulse",
        child_minus_structured_pulse_abs_residual_delta=0.2,
        observed_mean=observed_mean,
        uncertainty=uncertainty,
        publication_keys=publication_keys,
        structured_pulse_absolute_mean_residual=0.1,
        child_override_absolute_mean_residual=0.3,
        curation=curation or _curation(),
        samples=(_sample("S1"),) if samples is None else samples,
    )


def _curation(
    *,
    sample_ids: tuple[str, ...] = ("S1",),
    sample_count: int = 1,
) -> TargetCurationRecord:
    """Return one manual target curation record."""
    return TargetCurationRecord(
        status="published",
        target_id="target",
        region="region",
        source="steppe",
        start_bce=2350,
        end_bce=2200,
        sample_ids=sample_ids,
        sample_count=sample_count,
        ancestry_method="qpadm_steppe",
        aggregation_method="unweighted_mean",
        citation_key="key",
        citation="Citation",
        note="requested_group_id=group",
    )


def _sample(
    sample_id: str,
    *,
    time_bce: float | None = 2250,
    publication_key: str = "Pub1",
    estimate: float | None = 0.2,
    standard_error: float | None = 0.1,
    metadata_note: str = "assessment=Pass",
) -> TargetCurationAuditSample:
    """Return one manual joined sample audit row."""
    return TargetCurationAuditSample(
        sample_id=sample_id,
        time_bce=time_bce,
        date_uncertainty=10 if time_bce is not None else None,
        sex="female",
        site="Site",
        publication_key=publication_key,
        estimate=estimate,
        standard_error=standard_error,
        qpadm_pvalue=0.5 if estimate is not None else None,
        metadata_note=metadata_note if time_bce is not None else "",
        estimate_note="source_table=qpAdm" if estimate is not None else "",
    )
