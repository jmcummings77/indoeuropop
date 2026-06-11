"""Tests for target curation audit reports."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from indoeuropop.data.target_curation import TargetCurationRecord
from indoeuropop.reporting.target_audit import (
    TargetCurationAudit,
    TargetCurationAuditSample,
    load_target_curation_audit,
)
from indoeuropop.reporting.target_audit_report import (
    target_curation_audit_markdown,
    write_target_curation_audit_markdown,
)
from indoeuropop.reporting.target_review import TargetResidualReviewRow


@dataclass(frozen=True)
class AuditInputPaths:
    """Paths for a complete curation audit fixture."""

    residuals_path: Path
    curation_path: Path
    sample_metadata_path: Path
    ancestry_estimates_path: Path


def test_load_target_curation_audit_joins_top_outlier(tmp_path: Path) -> None:
    """The audit should join residual, curation, metadata, and qpAdm estimates."""
    paths = _write_audit_inputs(tmp_path)

    audit = _load_audit(paths)
    markdown = target_curation_audit_markdown(audit)

    assert audit.target_id == "target-stkr"
    assert audit.requested_group_id == "Germany_StkrStraubing_BellBeaker"
    assert audit.all_estimates_identical is True
    assert audit.critical_sample_ids == ("I3592.AG",)
    assert audit.publication_keys == ("OlaldeReichNature2018", "SjogrenHeydPLosOne2020")
    assert "replicated group-level estimates" in audit.recommendation
    assert "all_estimates_identical: true" in markdown
    assert "AADR metadata marks samples as CRITICAL" in markdown
    assert "I3592.AG" in markdown


def test_target_curation_audit_writes_markdown(tmp_path: Path) -> None:
    """The public writer should create parent directories."""
    audit = _load_audit(_write_audit_inputs(tmp_path))
    output_path = tmp_path / "reports" / "audit.md"

    returned_path = write_target_curation_audit_markdown(audit, output_path)

    assert returned_path == output_path
    assert output_path.read_text(encoding="utf-8").startswith("# Target Curation")


def test_load_target_curation_audit_can_select_requested_group(
    tmp_path: Path,
) -> None:
    """Audits should be selectable by requested group ID."""
    paths = _write_audit_inputs(tmp_path)

    audit = _load_audit(
        paths,
        requested_group_id="England_BellBeaker",
    )

    assert audit.target_id == "target-england"
    assert audit.recommendation == (
        "No curation blocker found; this target can move to scenario review."
    )


def test_target_curation_audit_reports_missing_join_inputs(
    tmp_path: Path,
) -> None:
    """Missing metadata or estimate joins should become audit findings."""
    paths = _write_audit_inputs(
        tmp_path,
        metadata_text=_metadata_csv().replace(
            "published,aadr,S2,2,SjogrenHeydPLosOne2020,doi,central_europe,"
            "Site,2250,50,male,aadr,"
            "group_id=Germany_StkrStraubing_BellBeaker; assessment=Pass\n",
            "",
        ),
        estimates_text=_estimates_csv().replace(
            "published,S1,steppe,0.02,0.3,qpadm_steppe,"
            "source_table=qpAdm; qpadm_pvalue=0.5\n",
            "",
        ),
    )

    audit = _load_audit(paths)

    assert audit.missing_metadata_ids == ("S2",)
    assert audit.missing_estimate_ids == ("S1",)
    assert "Fix target input joins" in audit.recommendation
    assert any("missing metadata" in issue for issue in audit.issues)
    assert any("missing ancestry estimates" in issue for issue in audit.issues)


def test_target_curation_audit_reports_manual_edge_cases() -> None:
    """Manual audits should expose window and sample-count inconsistencies."""
    audit = TargetCurationAudit(
        residual=_residual_row(z_score=0.5),
        curation=_curation_record(sample_ids=("S1",), sample_count=1),
        samples=(
            TargetCurationAuditSample(
                sample_id="S1",
                time_bce=2100,
                date_uncertainty=10,
                sex="female",
                site="Site",
                publication_key="Pub1",
                estimate=0.2,
                standard_error=0.1,
                qpadm_pvalue=0.4,
            ),
            TargetCurationAuditSample(
                sample_id="S2",
                time_bce=2250,
                date_uncertainty=10,
                sex="male",
                site="Other",
                publication_key="Pub2",
                estimate=0.4,
                standard_error=0.1,
                qpadm_pvalue=0.5,
            ),
        ),
    )

    assert any("sample_count" in issue for issue in audit.issues)
    assert any("outside the curation window" in issue for issue in audit.issues)
    assert "Pub1, Pub2" in target_curation_audit_markdown(audit)


def test_target_curation_audit_reports_no_issues() -> None:
    """A clean non-outlier target should render an explicit no-issue check."""
    audit = TargetCurationAudit(
        residual=_residual_row(z_score=0.5),
        curation=_curation_record(sample_ids=("S1",), sample_count=1),
        samples=(
            TargetCurationAuditSample(
                sample_id="S1",
                time_bce=2250,
                date_uncertainty=10,
                sex="female",
                site="Site",
                publication_key="Pub1",
                estimate=0.2,
                standard_error=0.1,
                qpadm_pvalue=0.4,
            ),
        ),
    )

    markdown = target_curation_audit_markdown(audit)

    assert audit.issues == ()
    assert "No curation issues detected." in markdown
    assert audit.recommendation == (
        "No curation blocker found; this target can move to scenario review."
    )


def test_target_curation_audit_recommends_critical_sample_review() -> None:
    """A CRITICAL sample should be surfaced when no stronger issue applies."""
    audit = TargetCurationAudit(
        residual=_residual_row(z_score=0.5),
        curation=_curation_record(sample_ids=("S1",), sample_count=1),
        samples=(
            TargetCurationAuditSample(
                sample_id="S1",
                time_bce=2250,
                date_uncertainty=10,
                sex="unknown",
                site="Site",
                publication_key="Pub1",
                estimate=0.2,
                standard_error=0.1,
                qpadm_pvalue=0.4,
                metadata_note="assessment=CRITICAL",
            ),
        ),
    )

    assert audit.recommendation == (
        "Decide whether CRITICAL AADR samples should be excluded or caveated."
    )


def test_target_curation_audit_validation_and_selection_errors(
    tmp_path: Path,
) -> None:
    """Audit loaders and dataclasses should reject malformed input clearly."""
    paths = _write_audit_inputs(tmp_path)
    no_target_residuals = tmp_path / "no-target-residuals.csv"
    no_curation_residuals = tmp_path / "no-curation-residuals.csv"
    no_target_residuals.write_text(
        _residual_csv().replace("target_id=target-stkr", ""),
        encoding="utf-8",
    )
    no_curation_residuals.write_text(
        _residual_csv().replace("target-stkr", "target-missing", 1),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="no residual row matched"):
        _load_audit(paths, requested_group_id="missing")
    with pytest.raises(ValueError, match="multiple residual rows"):
        _load_audit(paths, target_id="target-stkr")
    with pytest.raises(ValueError, match="target_id is required"):
        _load_audit(
            AuditInputPaths(
                no_target_residuals,
                paths.curation_path,
                paths.sample_metadata_path,
                paths.ancestry_estimates_path,
            )
        )
    with pytest.raises(ValueError, match="no target curation row"):
        _load_audit(
            AuditInputPaths(
                no_curation_residuals,
                paths.curation_path,
                paths.sample_metadata_path,
                paths.ancestry_estimates_path,
            )
        )
    with pytest.raises(ValueError, match="sample_id"):
        TargetCurationAuditSample("", None, None, "", "", "", None, None, None)
    with pytest.raises(ValueError, match="time_bce"):
        TargetCurationAuditSample(
            "S1", float("nan"), None, "", "", "", None, None, None
        )
    with pytest.raises(ValueError, match="estimate"):
        TargetCurationAuditSample("S1", None, None, "", "", "", 2.0, None, None)
    with pytest.raises(ValueError, match="standard_error"):
        TargetCurationAuditSample("S1", None, None, "", "", "", None, 0.0, None)
    with pytest.raises(ValueError, match="at least one sample"):
        TargetCurationAudit(_residual_row(), _curation_record(), ())
    with pytest.raises(ValueError, match="positive"):
        TargetCurationAudit(
            _residual_row(),
            _curation_record(),
            (
                TargetCurationAuditSample(
                    "S1", None, None, "", "", "", None, None, None
                ),
            ),
            outlier_z_threshold=0,
        )
    missing_time_audit = TargetCurationAudit(
        _residual_row(z_score=0.5),
        _curation_record(),
        (
            TargetCurationAuditSample(
                "S1", None, None, "unknown", "", "", 0.2, 0.1, None
            ),
        ),
    )
    assert "metadata_time_range_bce: missing" in target_curation_audit_markdown(
        missing_time_audit
    )


def _load_audit(
    paths: AuditInputPaths,
    *,
    target_id: str | None = None,
    requested_group_id: str | None = None,
) -> TargetCurationAudit:
    """Load an audit from fixture paths with optional selection arguments."""
    return load_target_curation_audit(
        residuals_path=paths.residuals_path,
        curation_path=paths.curation_path,
        sample_metadata_path=paths.sample_metadata_path,
        ancestry_estimates_path=paths.ancestry_estimates_path,
        target_id=target_id,
        requested_group_id=requested_group_id,
    )


def _write_audit_inputs(
    tmp_path: Path,
    *,
    metadata_text: str | None = None,
    estimates_text: str | None = None,
) -> AuditInputPaths:
    """Write a complete set of audit CSV fixtures."""
    paths = AuditInputPaths(
        residuals_path=tmp_path / "target-residuals.csv",
        curation_path=tmp_path / "target-curation.csv",
        sample_metadata_path=tmp_path / "sample-metadata.csv",
        ancestry_estimates_path=tmp_path / "sample-estimates.csv",
    )
    paths.residuals_path.write_text(_residual_csv(), encoding="utf-8")
    paths.curation_path.write_text(_curation_csv(), encoding="utf-8")
    paths.sample_metadata_path.write_text(
        _metadata_csv() if metadata_text is None else metadata_text,
        encoding="utf-8",
    )
    paths.ancestry_estimates_path.write_text(
        _estimates_csv() if estimates_text is None else estimates_text,
        encoding="utf-8",
    )
    return paths


def _residual_csv() -> str:
    """Return residual CSV text with one duplicated target ID for error tests."""
    return "\n".join(
        (
            "target_index,status,region,source,time_bce,observed_mean,uncertainty,"
            "predicted,residual,z_score,citation_key,citation,note",
            "1,published,central_europe,steppe,2235,0.02,0.1,0.5,0.48,4.8,key,"
            "Citation,requested_group_id=Germany_StkrStraubing_BellBeaker; "
            "target_id=target-stkr",
            "2,published,britain,steppe,2172,0.42,0.2,0.44,0.02,0.1,key,"
            "Citation,requested_group_id=England_BellBeaker; target_id=target-england",
            "3,published,central_europe,steppe,2236,0.03,0.1,0.5,0.47,4.7,key,"
            "Citation,requested_group_id=Germany_StkrStraubing_BellBeaker_o; "
            "target_id=target-stkr",
        )
    )


def _curation_csv() -> str:
    """Return target-curation CSV text for audit tests."""
    return "\n".join(
        (
            "status,target_id,region,source,start_bce,end_bce,sample_ids,"
            "sample_count,ancestry_method,aggregation_method,citation_key,citation,note",
            "published,target-stkr,central_europe,steppe,2300,2200,S1;S2;I3592.AG,3,"
            "qpadm_steppe,unweighted_mean,key,Citation,"
            "requested_group_id=Germany_StkrStraubing_BellBeaker",
            "published,target-england,britain,steppe,2200,2100,E1,1,qpadm_steppe,"
            "unweighted_mean,key,Citation,requested_group_id=England_BellBeaker",
        )
    )


def _metadata_csv() -> str:
    """Return sample-metadata CSV text for audit tests."""
    return "\n".join(
        (
            "status,dataset_id,sample_id,accession_id,publication_key,publication,"
            "region,site,time_bce,date_uncertainty,sex,method,note",
            "published,aadr,S1,1,OlaldeReichNature2018,doi,central_europe,Site,"
            "2250,50,female,aadr,group_id=Germany_StkrStraubing_BellBeaker; "
            "assessment=Pass",
            "published,aadr,S2,2,SjogrenHeydPLosOne2020,doi,central_europe,Site,"
            "2250,50,male,aadr,group_id=Germany_StkrStraubing_BellBeaker; "
            "assessment=Pass",
            "published,aadr,I3592.AG,3,OlaldeReichNature2018,doi,central_europe,"
            "Site,2250,50,unknown,aadr,"
            "group_id=Germany_StkrStraubing_BellBeaker; assessment=CRITICAL",
            "published,aadr,E1,4,Pub1,doi,britain,England,2150,20,female,aadr,"
            "group_id=England_BellBeaker; assessment=Pass",
        )
    )


def _estimates_csv() -> str:
    """Return sample-ancestry estimate CSV text for audit tests."""
    return "\n".join(
        (
            "status,sample_id,source,estimate,standard_error,method,note",
            "published,S1,steppe,0.02,0.3,qpadm_steppe,"
            "source_table=qpAdm; qpadm_pvalue=0.5",
            "published,S2,steppe,0.02,0.3,qpadm_steppe,"
            "source_table=qpAdm; qpadm_pvalue=0.5",
            "published,I3592.AG,steppe,0.02,0.3,qpadm_steppe,"
            "source_table=qpAdm; qpadm_pvalue=0.5",
            "published,E1,steppe,0.3,0.1,qpadm_steppe,"
            "source_table=qpAdm; qpadm_pvalue=0.8",
        )
    )


def _residual_row(z_score: float = 4.8) -> TargetResidualReviewRow:
    """Return a residual row for manual audit tests."""
    return TargetResidualReviewRow(
        target_index=1,
        region="central_europe",
        source="steppe",
        time_bce=2235,
        observed_mean=0.2,
        uncertainty=0.1,
        predicted=0.5,
        residual=0.3,
        z_score=z_score,
        requested_group_id="group",
        note="target_id=target",
    )


def _curation_record(
    *,
    sample_ids: tuple[str, ...] = ("S1",),
    sample_count: int = 1,
) -> TargetCurationRecord:
    """Return a target curation record for manual audit tests."""
    return TargetCurationRecord(
        status="published",
        target_id="target",
        region="central_europe",
        source="steppe",
        start_bce=2300,
        end_bce=2200,
        sample_ids=sample_ids,
        sample_count=sample_count,
        ancestry_method="qpadm_steppe",
        aggregation_method="unweighted_mean",
        citation_key="key",
        citation="Citation",
    )
