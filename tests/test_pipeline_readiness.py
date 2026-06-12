"""Tests for real-pipeline readiness reports and CLI wiring."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from pytest import CaptureFixture

from indoeuropop.data.data_sources import sha256_file
from indoeuropop.orchestration.cli import main
from indoeuropop.reporting.readiness import (
    load_real_pipeline_readiness,
    real_pipeline_readiness_markdown,
    write_real_pipeline_readiness_markdown,
)
from indoeuropop.reporting.readiness_checks import (
    _max_text,
    _mean_text,
    _optional_int,
    _relative_path,
)
from indoeuropop.reporting.readiness_models import (
    PipelineArtifactRequirement,
    PipelineArtifactStatus,
    ReadinessMetric,
)


def test_real_pipeline_readiness_reports_ready_fixture(tmp_path: Path) -> None:
    """A complete tiny pipeline tree should be reported as ready."""
    _write_ready_tree(tmp_path)

    report = load_real_pipeline_readiness(tmp_path)
    metric_values = {metric.name: metric.value for metric in report.metrics}
    markdown = real_pipeline_readiness_markdown(report)
    output_path = write_real_pipeline_readiness_markdown(
        report,
        tmp_path / "results" / "pipeline-readiness.md",
    )

    assert report.ready
    assert metric_values["local_data_source_count"] == "1"
    assert metric_values["present_local_data_source_count"] == "1"
    assert metric_values["real_aadr_target_observation_count"] == "1"
    assert metric_values["qpadm_rerun_accepted_target_observation_count"] == "2"
    assert metric_values["accepted_target_row_count"] == "2"
    assert metric_values["override_mean_validation_delta"] == "-0.025000"
    assert metric_values["override_priority_mean_delta"] == "-0.050000"
    assert metric_values["override_protected_max_delta"] == "0.000000"
    assert metric_values["override_protected_degraded"] == "false"
    assert any(status.role == "source_data" for status in report.artifacts)
    assert "Status: ready" in markdown
    assert "No readiness blockers detected" in markdown
    assert output_path.read_text(encoding="utf-8") == markdown


def test_cli_review_pipeline_readiness_writes_report(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should write a readiness report and print machine-readable lines."""
    _write_ready_tree(tmp_path)
    report_path = tmp_path / "reports" / "readiness.md"

    exit_code = main(
        [
            "review-pipeline-readiness",
            "--project-root",
            str(tmp_path),
            "--readiness-report-md",
            str(report_path),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"readiness_report={report_path}" in captured.out
    assert "pipeline_ready=true" in captured.out
    assert "readiness_issue_count=0" in captured.out
    assert "readiness_metric=accepted_target_row_count,value=2" in captured.out
    assert "Status: ready" in report_path.read_text(encoding="utf-8")


def test_cli_review_pipeline_readiness_prints_blocked_report(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The CLI should return nonzero and print issues when artifacts are absent."""
    exit_code = main(
        [
            "review-pipeline-readiness",
            "--project-root",
            str(tmp_path),
            "--data-sources",
            str(tmp_path / "missing.toml"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Status: blocked" in captured.out
    assert "pipeline_ready=false" in captured.out
    assert "readiness_issue=" in captured.out


def test_readiness_reports_missing_and_inconsistent_artifacts(
    tmp_path: Path,
) -> None:
    """Missing source files and mismatched diagnostics should block readiness."""
    _write_ready_tree(tmp_path)
    _write_json(
        tmp_path / "results/qpadm-rerun/qpadm-rerun-diagnostics.json",
        {"accepted_target_observation_count": 3},
    )
    (tmp_path / "data" / "tiny.anno").unlink()

    report = load_real_pipeline_readiness(tmp_path)

    assert not report.ready
    assert any(
        "missing local data source: data/tiny.anno" in issue for issue in report.issues
    )
    assert any(
        "does not match accepted_target_row_count" in issue for issue in report.issues
    )


def test_readiness_handles_optional_artifacts_and_skipped_catalog(
    tmp_path: Path,
) -> None:
    """Optional missing artifacts and disabled source catalogs should be allowed."""
    report = load_real_pipeline_readiness(
        tmp_path,
        data_source_catalog=None,
        required_artifacts=(
            PipelineArtifactRequirement(
                "optional note",
                Path("missing-note.md"),
                "note",
                required=False,
            ),
        ),
        curation_decision_files=(),
        require_curation_artifacts=False,
    )

    assert report.artifacts[0].status == "optional-missing"
    assert any("expected exactly one active" in issue for issue in report.issues)


def test_readiness_reports_invalid_diagnostics_and_csv_inputs(
    tmp_path: Path,
) -> None:
    """Malformed diagnostics and CSV artifacts should become readiness issues."""
    _write_text(
        tmp_path / "results/real-aadr-comparison/aadr-target-diagnostics.json",
        "{",
    )
    _write_json(tmp_path / "results/qpadm-rerun/qpadm-rerun-diagnostics.json", [])
    _write_text(
        tmp_path / "results/real-aadr-comparison/aadr-target-observations.csv",
        "",
    )
    _write_text(
        tmp_path
        / "results/qpadm-rerun/central-europe-curated-vs-interaction-best-delta.csv",
        "validation_delta,priority,protected,protected_degraded\n",
    )

    report = load_real_pipeline_readiness(
        tmp_path,
        data_source_catalog=None,
        required_artifacts=(),
        curation_decision_files=(tmp_path / "missing.toml",),
    )

    assert any("invalid JSON diagnostics" in issue for issue in report.issues)
    assert any("is not an object" in issue for issue in report.issues)
    assert any("invalid CSV artifact" in issue for issue in report.issues)
    assert any("has no rows" in issue for issue in report.issues)
    assert any("No such file" in issue for issue in report.issues)


def test_readiness_reports_invalid_catalog_and_override_delta(
    tmp_path: Path,
) -> None:
    """Invalid source catalogs and malformed override deltas should be reported."""
    _write_text(
        tmp_path / "curation/local-aadr-v66-data-sources.toml", "data_sources=1\n"
    )
    _write_text(
        tmp_path
        / "results/qpadm-rerun/central-europe-curated-vs-interaction-best-delta.csv",
        "priority,protected,protected_degraded\ntrue,false,false\n",
    )

    report = load_real_pipeline_readiness(
        tmp_path,
        required_artifacts=(),
        curation_decision_files=(tmp_path / "missing.toml",),
    )

    assert any("data source catalog invalid" in issue for issue in report.issues)
    assert any("invalid override delta CSV" in issue for issue in report.issues)


def test_readiness_dataclasses_validate_inputs(tmp_path: Path) -> None:
    """Small readiness dataclasses should reject malformed values."""
    present = PipelineArtifactStatus("label", "path", "role", True, True, 3)
    missing = PipelineArtifactStatus("label", "path", "role", True, False)
    optional = PipelineArtifactStatus("label", "path", "role", False, False)

    assert present.status == "present"
    assert missing.status == "missing"
    assert optional.status == "optional-missing"
    assert _optional_int(None) is None
    assert _optional_int("not-an-int") is None
    assert _optional_int("4") == 4
    assert _mean_text(()) == "0.000000"
    assert _max_text(()) == "0.000000"
    assert _relative_path(tmp_path.parent / "outside.txt", tmp_path).endswith(
        "outside.txt"
    )
    with pytest.raises(ValueError, match="label"):
        PipelineArtifactRequirement("", Path("x"), "role")
    with pytest.raises(ValueError, match="role"):
        PipelineArtifactRequirement("label", Path("x"), "")
    with pytest.raises(ValueError, match="path"):
        PipelineArtifactRequirement("label", cast(Path, ""), "role")
    with pytest.raises(ValueError, match="metric name"):
        ReadinessMetric("", "1", "source")
    with pytest.raises(ValueError, match="metric value"):
        ReadinessMetric("name", "", "source")
    with pytest.raises(ValueError, match="metric source"):
        ReadinessMetric("name", "1", "")

    report = load_real_pipeline_readiness(
        tmp_path,
        data_source_catalog=None,
        required_artifacts=(
            PipelineArtifactRequirement(
                "outside root",
                tmp_path.parent / "outside.txt",
                "external",
                required=False,
            ),
        ),
        curation_decision_files=(),
        require_curation_artifacts=False,
    )
    assert report.artifacts[0].relative_path.endswith("outside.txt")


def _write_ready_tree(root: Path) -> None:
    """Write a tiny complete readiness fixture below a temporary project root."""
    baseline_fit = (
        root / "results/qpadm-rerun/central-europe-curated-validation-fit.csv"
    )
    override_fit = (
        root / "results/qpadm-rerun/central-europe-interaction-best-validation-fit.csv"
    )
    _write_source_catalog(root)
    _write_standard_outputs(root)
    _write_text(baseline_fit, "holdout_field,holdout_value,rank\nregion,britain,1\n")
    _write_text(override_fit, "holdout_field,holdout_value,rank\nregion,britain,1\n")
    _write_text(root / "docs/central-europe-override-decision.md", "# Decision\n")
    _write_text(
        root
        / "results/qpadm-rerun/central-europe-curated-vs-interaction-best-delta.md",
        "# Delta\n",
    )
    delta_manifest = (
        root
        / "results/qpadm-rerun"
        / "central-europe-curated-vs-interaction-best-delta-manifest.json"
    )
    _write_json(
        delta_manifest,
        {
            "artifacts": [
                _artifact("baseline_validation_fit_csv", baseline_fit, root),
                _artifact("override_validation_fit_csv", override_fit, root),
            ]
        },
    )
    head_to_head_report = (
        root
        / "results/qpadm-rerun"
        / "central-europe-structured-pulse-vs-child-head-to-head.md"
    )
    head_to_head_manifest = (
        root
        / "results/qpadm-rerun"
        / "central-europe-structured-pulse-vs-child-head-to-head-manifest.json"
    )
    _write_text(head_to_head_report, "# Head to Head\n")
    _write_json(
        head_to_head_manifest,
        {"artifacts": [_artifact("head_to_head_report_md", head_to_head_report, root)]},
    )
    _write_curation_pair(root)


def _write_standard_outputs(root: Path) -> None:
    """Write conventional diagnostics and result artifacts for readiness tests."""
    _write_json(
        root / "results/real-aadr-comparison/aadr-target-diagnostics.json",
        {
            "selected_sample_count": 4,
            "retained_target_count": 1,
            "target_observation_count": 1,
            "decision_deferred_target_count": 0,
        },
    )
    _write_json(
        root / "results/qpadm-rerun/qpadm-rerun-diagnostics.json",
        {
            "baseline_target_observation_count": 1,
            "post_target_observation_count": 2,
            "accepted_target_observation_count": 2,
            "rescued_target_count": 1,
        },
    )
    _write_text(
        root / "results/real-aadr-comparison/aadr-target-observations.csv",
        _target_csv(("britain",)),
    )
    _write_text(
        root / "results/qpadm-rerun/accepted-target-observations.csv",
        _target_csv(("britain", "central_europe")),
    )
    _write_text(
        root / "results/qpadm-rerun/central-europe-structured-targets.csv",
        _target_csv(("britain", "central_europe", "central_child")),
    )
    _write_text(
        root / "results/qpadm-rerun/accepted-validation-fit.csv",
        "holdout_field,holdout_value,rank\nregion,britain,1\n",
    )
    _write_json(
        root / "results/real-aadr-comparison/target-comparison-manifest.json", {}
    )
    _write_json(root / "results/qpadm-rerun/accepted-validation-manifest.json", {})
    _write_text(
        root
        / "results/qpadm-rerun/central-europe-curated-vs-interaction-best-delta.csv",
        (
            "validation_delta,priority,protected,protected_degraded\n"
            "0.0,false,true,false\n"
            "-0.05,true,false,false\n"
        ),
    )


def _write_source_catalog(root: Path) -> None:
    """Write one local source-data catalog record and its tiny file."""
    _write_text(root / "data/tiny.anno", "sample\n")
    _write_text(
        root / "curation/local-aadr-v66-data-sources.toml",
        """
        [[data_sources]]
        dataset_id = "tiny-aadr"
        kind = "aadr"
        status = "local"
        citation_key = "tiny"
        citation = "Tiny local source."
        uri = "data/tiny.anno"
        download_filename = "tiny.anno"
        """,
    )


def _write_curation_pair(root: Path) -> None:
    """Write reciprocal active and superseded curation-decision files."""
    common = """
        decision_record = "docs/central-europe-override-decision.md"
        fit_metric = "root_mean_squared_error"
        protected_holdouts = ["britain"]
        priority_holdouts = ["central_europe__priority"]
        baseline_validation_fit_csv = \
"results/qpadm-rerun/central-europe-curated-validation-fit.csv"
        override_validation_fit_csv = \
"results/qpadm-rerun/central-europe-interaction-best-validation-fit.csv"
        acceptance_gate = "indoeuropop review-override-deltas"
    """
    _write_text(
        root / "curation/aadr-v66-central-europe-child-overrides.toml",
        f"""
        [review]
        status = "superseded_review_candidate"
        superseded_by = \
"curation/aadr-v66-central-europe-child-overrides-interaction-best.toml"
        {common}
        """,
    )
    _write_text(
        root / "curation/aadr-v66-central-europe-child-overrides-interaction-best.toml",
        f"""
        [review]
        status = "review_candidate"
        supersedes = "curation/aadr-v66-central-europe-child-overrides.toml"
        source_delta_report = \
"results/qpadm-rerun/central-europe-curated-vs-interaction-best-delta.md"
        same_baseline_head_to_head_report = \
"results/qpadm-rerun/central-europe-structured-pulse-vs-child-head-to-head.md"
        {common}
        """,
    )


def _target_csv(regions: tuple[str, ...]) -> str:
    """Return a tiny target-observation CSV for the requested regions."""
    rows = ["status,region,source,time_bce,mean,uncertainty,citation_key,citation,note"]
    rows.extend(
        f"published,{region},steppe,2200,0.5,0.1,key,citation,note"
        for region in regions
    )
    return "\n".join(rows) + "\n"


def _artifact(name: str, path: Path, root: Path) -> dict[str, str]:
    """Return one minimal manifest artifact payload."""
    return {
        "name": name,
        "path": path.relative_to(root).as_posix(),
        "checksum_sha256": sha256_file(path),
    }


def _write_json(path: Path, payload: object) -> None:
    """Write JSON to a test fixture path."""
    _write_text(path, json.dumps(payload))


def _write_text(path: Path, text: str) -> None:
    """Write text to a test fixture path, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
