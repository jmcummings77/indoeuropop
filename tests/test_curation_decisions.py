"""Tests for curation-decision metadata validation."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from indoeuropop.data.curation_decisions import (
    load_curation_decision_record,
    validate_curation_decision_files,
)
from indoeuropop.data.data_sources import sha256_file


def test_checked_in_central_europe_curation_decisions_validate() -> None:
    """The promoted central-Europe override should have live local artifacts."""
    report = validate_curation_decision_files(
        (
            "curation/aadr-v66-central-europe-child-overrides.toml",
            "curation/aadr-v66-central-europe-child-overrides-interaction-best.toml",
        ),
        require_artifacts=True,
    )

    assert report.valid
    assert len(report.records) == 2
    assert report.require_valid() is report


def test_curation_decision_record_loads_relative_metadata(
    tmp_path: Path,
) -> None:
    """One curation record should expose normalized path metadata."""
    _write_valid_curation_pair(tmp_path)
    record = load_curation_decision_record(
        tmp_path / "curation" / "active.toml",
        project_root=tmp_path,
    )

    assert record.relative_path == "curation/active.toml"
    assert record.status == "review_candidate"
    assert record.text("decision_record") == "docs/decision.md"
    assert record.path_text("decision_record") == "docs/decision.md"


def test_curation_decision_validator_accepts_promoted_pair(tmp_path: Path) -> None:
    """A reciprocal active/superseded pair with matching artifacts should pass."""
    superseded_path, active_path = _write_valid_curation_pair(tmp_path)

    report = validate_curation_decision_files(
        (superseded_path, active_path),
        project_root=tmp_path,
        require_artifacts=True,
    )

    assert report.valid
    assert report.issues == ()


def test_curation_decision_report_raises_for_invalid_metadata(tmp_path: Path) -> None:
    """Invalid reports should raise one compact validation error on demand."""
    superseded_path, _ = _write_valid_curation_pair(tmp_path)
    report = validate_curation_decision_files(
        (superseded_path,),
        project_root=tmp_path,
    )

    assert not report.valid
    with pytest.raises(ValueError, match="expected exactly one active"):
        report.require_valid()


def test_load_curation_decision_record_rejects_non_table_review(
    tmp_path: Path,
) -> None:
    """The review metadata block must be a TOML table."""
    bad_path = tmp_path / "bad.toml"
    bad_path.write_text("review = 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="review must be"):
        load_curation_decision_record(bad_path, project_root=tmp_path)


def test_curation_decision_record_rejects_missing_text(tmp_path: Path) -> None:
    """Direct metadata accessors should fail loudly for absent text fields."""
    _write_valid_curation_pair(tmp_path)
    record = load_curation_decision_record(
        "curation/active.toml",
        project_root=tmp_path,
    )

    with pytest.raises(ValueError, match="must be a string"):
        record.text("missing")


def test_curation_decision_record_rejects_empty_required_text(tmp_path: Path) -> None:
    """Direct status access should reject blank status values."""
    bad_path = tmp_path / "bad.toml"
    bad_path.write_text("[review]\nstatus = ''\n", encoding="utf-8")
    record = load_curation_decision_record(bad_path, project_root=tmp_path)

    with pytest.raises(ValueError, match="must be non-empty"):
        _ = record.status


def test_curation_decision_validator_reports_malformed_shape(
    tmp_path: Path,
) -> None:
    """Malformed review metadata should produce field-level issues."""
    bad_path = tmp_path / "curation" / "bad.toml"
    bad_path.parent.mkdir()
    bad_path.write_text(
        """
        [review]
        status = 1
        decision_record = 1
        fit_metric = ""
        protected_holdouts = "britain"
        priority_holdouts = [1]
        baseline_validation_fit_csv = ""
        override_validation_fit_csv = ""
        acceptance_gate = ""
        """,
        encoding="utf-8",
    )

    report = validate_curation_decision_files((bad_path,), project_root=tmp_path)

    assert any("expected exactly one active" in issue for issue in report.issues)
    assert any("status must be non-empty text" in issue for issue in report.issues)
    assert any(
        "decision_record must be non-empty text" in issue for issue in report.issues
    )
    assert any(
        "priority_holdouts must be non-empty" in issue for issue in report.issues
    )


def test_curation_decision_validator_reports_unsupported_status(
    tmp_path: Path,
) -> None:
    """Unknown status labels should be reported separately from shape errors."""
    bad_path = tmp_path / "curation" / "bad.toml"
    bad_path.parent.mkdir()
    bad_path.write_text(
        """
        [review]
        status = "draft"
        decision_record = "docs/decision.md"
        fit_metric = "root_mean_squared_error"
        protected_holdouts = ["britain"]
        priority_holdouts = ["central_europe__example"]
        baseline_validation_fit_csv = "results/baseline.csv"
        override_validation_fit_csv = "results/override.csv"
        acceptance_gate = "indoeuropop review-override-deltas"
        """,
        encoding="utf-8",
    )

    report = validate_curation_decision_files((bad_path,), project_root=tmp_path)

    assert any("status is not supported" in issue for issue in report.issues)


@pytest.mark.parametrize(
    ("mutator", "expected"),
    [
        (
            lambda root: _rewrite_active(root, supersedes=""),
            "supersedes must be declared",
        ),
        (
            lambda root: _rewrite_active(root, supersedes="curation/missing.toml"),
            "supersedes unknown curation file",
        ),
        (
            lambda root: _rewrite_superseded(root, status="review_candidate"),
            "status must be superseded_review_candidate",
        ),
        (
            lambda root: _rewrite_superseded(
                root, superseded_by="curation/missing.toml"
            ),
            "superseded_by unknown curation file",
        ),
        (
            lambda root: _rewrite_superseded(root, superseded_by=""),
            "superseded_by must be declared",
        ),
        (
            lambda root: _rewrite_active(root, status="superseded_review_candidate"),
            "expected exactly one active review_candidate",
        ),
    ],
)
def test_curation_decision_validator_reports_bad_lineage(
    tmp_path: Path,
    mutator: Callable[[Path], None],
    expected: str,
) -> None:
    """The active and superseded files should point at each other."""
    superseded_path, active_path = _write_valid_curation_pair(tmp_path)
    mutator(tmp_path)

    report = validate_curation_decision_files(
        (superseded_path, active_path),
        project_root=tmp_path,
    )

    assert any(expected in issue for issue in report.issues)


@pytest.mark.parametrize(
    ("mutator", "expected"),
    [
        (
            lambda root: (root / "docs" / "decision.md").unlink(),
            "decision_record does not exist",
        ),
        (
            lambda root: (root / "results" / "baseline.csv").unlink(),
            "baseline_validation_fit_csv does not exist",
        ),
        (
            lambda root: (root / "results" / "override.csv").unlink(),
            "override_validation_fit_csv does not exist",
        ),
        (
            lambda root: _rewrite_active(root, source_delta_report=""),
            "source_delta_report must be declared",
        ),
        (
            lambda root: (root / "results" / "delta.md").unlink(),
            "source_delta_report does not exist",
        ),
        (
            lambda root: _rewrite_active(root, source_report="results/missing.md"),
            "source_report does not exist",
        ),
        (
            lambda root: _rewrite_active(root, decision_record=""),
            "decision_record must be non-empty text",
        ),
        (
            lambda root: _rewrite_active(root, baseline_validation_fit_csv=""),
            "baseline_validation_fit_csv must be non-empty text",
        ),
        (
            lambda root: (root / "results" / "delta-manifest.json").unlink(),
            "source_delta_report manifest missing",
        ),
        (
            lambda root: _write_delta_manifest(root, include_override=False),
            "manifest missing override_validation_fit_csv",
        ),
        (
            lambda root: _write_delta_manifest(root, baseline_path="results/stale.csv"),
            "manifest baseline_validation_fit_csv path is stale",
        ),
        (
            lambda root: (root / "results" / "baseline.csv").write_text(
                "changed\n",
                encoding="utf-8",
            ),
            "manifest baseline_validation_fit_csv checksum is stale",
        ),
        (
            lambda root: _rewrite_active(root, same_baseline_head_to_head_report=""),
            "same_baseline_head_to_head_report must be declared",
        ),
        (
            lambda root: (root / "results" / "head-to-head.md").unlink(),
            "same_baseline_head_to_head_report does not exist",
        ),
        (
            lambda root: (root / "results" / "head-to-head-manifest.json").unlink(),
            "same_baseline_head_to_head_report manifest missing",
        ),
        (
            lambda root: _write_head_to_head_manifest(root, include_report=False),
            "manifest missing head_to_head_report_md",
        ),
        (
            lambda root: _write_head_to_head_manifest(
                root, report_path="results/stale-head-to-head.md"
            ),
            "manifest head_to_head_report_md path is stale",
        ),
        (
            lambda root: (root / "results" / "head-to-head.md").write_text(
                "changed\n",
                encoding="utf-8",
            ),
            "manifest head_to_head_report_md checksum is stale",
        ),
        (
            lambda root: _write_head_to_head_manifest(root, include_missing=True),
            "manifest debug_config path does not exist",
        ),
        (
            lambda root: _write_head_to_head_manifest(root, malformed_report=True),
            "manifest head_to_head_report_md is malformed",
        ),
    ],
)
def test_curation_decision_validator_reports_missing_or_stale_artifacts(
    tmp_path: Path,
    mutator: Callable[[Path], None],
    expected: str,
) -> None:
    """Strict artifact checks should catch missing files and stale manifests."""
    superseded_path, active_path = _write_valid_curation_pair(tmp_path)
    mutator(tmp_path)

    report = validate_curation_decision_files(
        (superseded_path, active_path),
        project_root=tmp_path,
        require_artifacts=True,
    )

    assert any(expected in issue for issue in report.issues)


def _write_valid_curation_pair(root: Path) -> tuple[Path, Path]:
    """Write a valid active/superseded curation pair under a temp root."""
    (root / "curation").mkdir(exist_ok=True)
    (root / "docs").mkdir(exist_ok=True)
    (root / "results").mkdir(exist_ok=True)
    (root / "docs" / "decision.md").write_text("# Decision\n", encoding="utf-8")
    (root / "results" / "baseline.csv").write_text("metric\n1\n", encoding="utf-8")
    (root / "results" / "override.csv").write_text("metric\n0\n", encoding="utf-8")
    (root / "results" / "delta.md").write_text("# Delta\n", encoding="utf-8")
    (root / "results" / "source.md").write_text("# Source\n", encoding="utf-8")
    (root / "results" / "head-to-head.md").write_text(
        "# Head to head\n", encoding="utf-8"
    )
    _write_delta_manifest(root)
    _write_head_to_head_manifest(root)
    _rewrite_superseded(root)
    _rewrite_active(root)
    return root / "curation" / "superseded.toml", root / "curation" / "active.toml"


def _rewrite_active(
    root: Path,
    *,
    status: str = "review_candidate",
    supersedes: str = "curation/superseded.toml",
    decision_record: str = "docs/decision.md",
    source_report: str = "results/source.md",
    source_delta_report: str = "results/delta.md",
    same_baseline_head_to_head_report: str = "results/head-to-head.md",
    baseline_validation_fit_csv: str = "results/baseline.csv",
) -> None:
    """Write the active curation file with selected metadata changes."""
    supersedes_line = f'supersedes = "{supersedes}"\n' if supersedes else ""
    decision_record_line = (
        f'decision_record = "{decision_record}"\n' if decision_record else ""
    )
    source_delta_line = (
        f'source_delta_report = "{source_delta_report}"\n'
        if source_delta_report
        else ""
    )
    source_report_line = f'source_report = "{source_report}"\n' if source_report else ""
    head_to_head_line = (
        f"same_baseline_head_to_head_report = "
        f'"{same_baseline_head_to_head_report}"\n'
        if same_baseline_head_to_head_report
        else ""
    )
    (root / "curation" / "active.toml").write_text(
        _review_toml(
            status=status,
            extra=(
                f"{supersedes_line}"
                f"{decision_record_line}"
                f"{source_report_line}"
                f"{source_delta_line}"
                f"{head_to_head_line}"
            ),
            baseline_validation_fit_csv=baseline_validation_fit_csv,
        ),
        encoding="utf-8",
    )


def _rewrite_superseded(
    root: Path,
    *,
    status: str = "superseded_review_candidate",
    superseded_by: str = "curation/active.toml",
) -> None:
    """Write the superseded curation file with selected metadata changes."""
    superseded_by_line = f'superseded_by = "{superseded_by}"\n' if superseded_by else ""
    (root / "curation" / "superseded.toml").write_text(
        _review_toml(
            status=status,
            extra=f'{superseded_by_line}decision_record = "docs/decision.md"\n',
        ),
        encoding="utf-8",
    )


def _review_toml(
    *,
    status: str,
    extra: str,
    baseline_validation_fit_csv: str = "results/baseline.csv",
) -> str:
    """Return shared review metadata TOML for curation decision tests."""
    baseline_line = (
        f'baseline_validation_fit_csv = "{baseline_validation_fit_csv}"'
        if baseline_validation_fit_csv
        else ""
    )
    return f"""
    [review]
    status = "{status}"
    {extra}
    fit_metric = "root_mean_squared_error"
    protected_degradation_tolerance = 0.0
    protected_holdouts = ["britain"]
    priority_holdouts = ["central_europe__example"]
    {baseline_line}
    override_validation_fit_csv = "results/override.csv"
    acceptance_gate = "indoeuropop review-override-deltas"
    """


def _write_delta_manifest(
    root: Path,
    *,
    include_override: bool = True,
    baseline_path: str = "results/baseline.csv",
) -> None:
    """Write a delta manifest matching the synthetic artifact files."""
    artifacts = [
        _artifact(root, "baseline_validation_fit_csv", baseline_path),
    ]
    if include_override:
        artifacts.append(
            _artifact(root, "override_validation_fit_csv", "results/override.csv")
        )
    (root / "results" / "delta-manifest.json").write_text(
        json.dumps({"artifacts": artifacts}),
        encoding="utf-8",
    )


def _write_head_to_head_manifest(
    root: Path,
    *,
    include_report: bool = True,
    report_path: str = "results/head-to-head.md",
    include_missing: bool = False,
    malformed_report: bool = False,
) -> None:
    """Write a head-to-head manifest for synthetic artifact checks."""
    artifacts: list[dict[str, str]] = []
    if include_report:
        if malformed_report:
            artifacts.append({"name": "head_to_head_report_md"})
        else:
            artifacts.append(_artifact(root, "head_to_head_report_md", report_path))
    if include_missing:
        artifacts.append(
            {
                "name": "debug_config",
                "path": "results/missing-config.toml",
                "checksum_sha256": "",
            }
        )
    (root / "results" / "head-to-head-manifest.json").write_text(
        json.dumps({"artifacts": artifacts}),
        encoding="utf-8",
    )


def _artifact(root: Path, name: str, path: str) -> dict[str, str]:
    """Return one manifest artifact entry."""
    artifact_path = root / path
    checksum = sha256_file(artifact_path) if artifact_path.exists() else ""
    return {
        "name": name,
        "path": path,
        "checksum_sha256": checksum,
    }
