"""Validation helpers for tracked curation-decision metadata."""

from __future__ import annotations

import json
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from indoeuropop.data.data_sources import sha256_file

CURATION_DECISION_STATUSES = frozenset(
    {"review_candidate", "superseded_review_candidate"}
)


@dataclass(frozen=True)
class CurationDecisionRecord:
    """Loaded review metadata for one curation file."""

    path: Path
    relative_path: str
    review: Mapping[str, Any]

    @property
    def status(self) -> str:
        """Return the curation status label."""
        return _text(self.review, "status")

    def text(self, key: str) -> str:
        """Return one string metadata field."""
        return _text(self.review, key)

    def path_text(self, key: str) -> str:
        """Return one relative path metadata field."""
        return _normalized_path_text(self.text(key))


@dataclass(frozen=True)
class CurationDecisionValidationReport:
    """Result from validating curation-decision metadata."""

    records: tuple[CurationDecisionRecord, ...]
    issues: tuple[str, ...]

    @property
    def valid(self) -> bool:
        """Return whether validation found no issues."""
        return not self.issues

    def require_valid(self) -> CurationDecisionValidationReport:
        """Return this report or raise a compact validation error."""
        if self.issues:
            issue_text = "; ".join(self.issues)
            raise ValueError(f"curation decision validation failed: {issue_text}")
        return self


def load_curation_decision_record(
    path: str | Path,
    *,
    project_root: str | Path = ".",
) -> CurationDecisionRecord:
    """Load review metadata from one curation TOML file."""
    root = Path(project_root).resolve()
    absolute_path = _absolute_path(path, root)
    with absolute_path.open("rb") as input_file:
        raw_payload = tomllib.load(input_file)
    review = raw_payload.get("review", {})
    if not isinstance(review, dict):
        raise ValueError("review must be a TOML table")
    return CurationDecisionRecord(
        path=absolute_path,
        relative_path=_relative_path_text(absolute_path, root),
        review=review,
    )


def validate_curation_decision_files(
    paths: Iterable[str | Path],
    *,
    project_root: str | Path = ".",
    require_artifacts: bool = False,
) -> CurationDecisionValidationReport:
    """Validate promoted and superseded curation-decision metadata.

    Set `require_artifacts` when local generated results are available. In that
    mode, active review candidates must point at existing validation artifacts,
    and the delta manifest must still match each referenced artifact checksum.
    """
    root = Path(project_root).resolve()
    records = tuple(
        load_curation_decision_record(path, project_root=root) for path in paths
    )
    issue_collector: list[str] = []
    record_by_path = {record.relative_path: record for record in records}
    active_records = tuple(
        record
        for record in records
        if _optional_text(record.review, "status") == "review_candidate"
    )

    _validate_active_count(active_records, issue_collector)
    for record in records:
        _validate_record_shape(record, issue_collector)
    for record in active_records:
        issue_collector.extend(
            _active_record_issues(record, record_by_path, root, require_artifacts)
        )
    for record in records:
        if _optional_text(record.review, "status") == "superseded_review_candidate":
            issue_collector.extend(
                _superseded_record_issues(record, record_by_path, root)
            )

    return CurationDecisionValidationReport(records, tuple(issue_collector))


def _validate_active_count(
    active_records: tuple[CurationDecisionRecord, ...],
    issue_collector: list[str],
) -> None:
    """Append an issue unless exactly one active review candidate is present."""
    if len(active_records) != 1:
        issue_collector.append("expected exactly one active review_candidate")


def _validate_record_shape(
    record: CurationDecisionRecord,
    issue_collector: list[str],
) -> None:
    """Append field-level issues for malformed review metadata."""
    for key in (
        "status",
        "decision_record",
        "fit_metric",
        "baseline_validation_fit_csv",
        "override_validation_fit_csv",
        "acceptance_gate",
    ):
        _append_text_issue(record, key, issue_collector)
    status = _optional_text(record.review, "status")
    if status and status not in CURATION_DECISION_STATUSES:
        issue_collector.append(f"{record.relative_path}: status is not supported")
    for key in ("protected_holdouts", "priority_holdouts"):
        if not _text_tuple(record.review, key):
            issue_collector.append(f"{record.relative_path}: {key} must be non-empty")


def _append_text_issue(
    record: CurationDecisionRecord,
    key: str,
    issue_collector: list[str],
) -> None:
    """Append an issue when a metadata field is not non-empty text."""
    value = record.review.get(key)
    if not isinstance(value, str) or not value.strip():
        issue_collector.append(f"{record.relative_path}: {key} must be non-empty text")


def _active_record_issues(
    record: CurationDecisionRecord,
    record_by_path: Mapping[str, CurationDecisionRecord],
    root: Path,
    require_artifacts: bool,
) -> tuple[str, ...]:
    """Return issues for one active review candidate."""
    issues: list[str] = []
    superseded_path = _optional_path_text(record.review, "supersedes")
    if not superseded_path:
        issues.append(f"{record.relative_path}: supersedes must be declared")
    else:
        superseded_record = record_by_path.get(superseded_path)
        if superseded_record is None:
            issues.append(f"{record.relative_path}: supersedes unknown curation file")
        elif (
            _optional_text(superseded_record.review, "status")
            != "superseded_review_candidate"
        ):
            issues.append(
                f"{superseded_path}: status must be superseded_review_candidate"
            )
        elif _optional_path_text(superseded_record.review, "superseded_by") != (
            record.relative_path
        ):
            issues.append(f"{superseded_path}: superseded_by must point to active file")
    issues.extend(_decision_record_issues(record, root))
    if require_artifacts:
        issues.extend(_artifact_issues(record, root))
    return tuple(issues)


def _superseded_record_issues(
    record: CurationDecisionRecord,
    record_by_path: Mapping[str, CurationDecisionRecord],
    root: Path,
) -> tuple[str, ...]:
    """Return issues for one superseded review candidate."""
    issues: list[str] = []
    active_path = _optional_path_text(record.review, "superseded_by")
    if not active_path:
        issues.append(f"{record.relative_path}: superseded_by must be declared")
    else:
        active_record = record_by_path.get(active_path)
        if active_record is None:
            issues.append(
                f"{record.relative_path}: superseded_by unknown curation file"
            )
        elif _optional_text(active_record.review, "status") != "review_candidate":
            issues.append(f"{active_path}: status must be review_candidate")
    issues.extend(_decision_record_issues(record, root))
    return tuple(issues)


def _decision_record_issues(
    record: CurationDecisionRecord,
    root: Path,
) -> tuple[str, ...]:
    """Return issues for a linked decision-record document."""
    decision_record = _optional_path_text(record.review, "decision_record")
    if not decision_record:
        return ()
    decision_path = root / decision_record
    if not decision_path.exists():
        return (f"{record.relative_path}: decision_record does not exist",)
    return ()


def _artifact_issues(record: CurationDecisionRecord, root: Path) -> tuple[str, ...]:
    """Return missing or stale artifact issues for an active candidate."""
    issues: list[str] = []
    for key in ("baseline_validation_fit_csv", "override_validation_fit_csv"):
        artifact_text = _optional_path_text(record.review, key)
        if not artifact_text:
            continue
        artifact_path = root / artifact_text
        if not artifact_path.exists():
            issues.append(f"{record.relative_path}: {key} does not exist")
    delta_report = _optional_path_text(record.review, "source_delta_report")
    if not delta_report:
        issues.append(f"{record.relative_path}: source_delta_report must be declared")
        return tuple(issues)
    delta_report_path = root / delta_report
    if not delta_report_path.exists():
        issues.append(f"{record.relative_path}: source_delta_report does not exist")
    source_report = _optional_path_text(record.review, "source_report")
    if source_report and not (root / source_report).exists():
        issues.append(f"{record.relative_path}: source_report does not exist")
    manifest_path = _manifest_path(delta_report_path)
    if not manifest_path.exists():
        issues.append(f"{record.relative_path}: source_delta_report manifest missing")
        return tuple(issues)
    issues.extend(_manifest_artifact_issues(record, root, manifest_path))
    return tuple(issues)


def _manifest_artifact_issues(
    record: CurationDecisionRecord,
    root: Path,
    manifest_path: Path,
) -> tuple[str, ...]:
    """Return issues when manifest artifact paths or checksums do not match."""
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = {
        artifact["name"]: artifact
        for artifact in payload.get("artifacts", [])
        if isinstance(artifact, dict) and isinstance(artifact.get("name"), str)
    }
    issues: list[str] = []
    for name, review_key in (
        ("baseline_validation_fit_csv", "baseline_validation_fit_csv"),
        ("override_validation_fit_csv", "override_validation_fit_csv"),
    ):
        artifact = artifacts.get(name)
        expected_path = _optional_path_text(record.review, review_key)
        if not expected_path:
            continue
        if artifact is None:
            issues.append(f"{record.relative_path}: manifest missing {name}")
            continue
        if artifact.get("path") != expected_path:
            issues.append(f"{record.relative_path}: manifest {name} path is stale")
            continue
        artifact_path = root / expected_path
        if not artifact_path.exists():
            continue
        actual_checksum = sha256_file(artifact_path)
        if artifact.get("checksum_sha256") != actual_checksum:
            issues.append(f"{record.relative_path}: manifest {name} checksum is stale")
    return tuple(issues)


def _manifest_path(report_path: Path) -> Path:
    """Return the manifest path convention for a generated Markdown report."""
    return report_path.with_name(f"{report_path.stem}-manifest.json")


def _absolute_path(path: str | Path, root: Path) -> Path:
    """Return an absolute path resolved against a project root."""
    raw_path = Path(path)
    if raw_path.is_absolute():
        return raw_path
    return root / raw_path


def _relative_path_text(path: Path, root: Path) -> str:
    """Return a POSIX path relative to the project root."""
    return path.relative_to(root).as_posix()


def _normalized_path_text(value: str) -> str:
    """Return a normalized POSIX path string."""
    return Path(value).as_posix()


def _optional_path_text(raw_payload: Mapping[str, Any], key: str) -> str:
    """Return an optional normalized path value."""
    value = raw_payload.get(key, "")
    if isinstance(value, str):
        stripped_value = value.strip()
        if stripped_value:
            return _normalized_path_text(stripped_value)
    return ""


def _optional_text(raw_payload: Mapping[str, Any], key: str) -> str:
    """Return optional stripped text from TOML metadata."""
    value = raw_payload.get(key, "")
    if isinstance(value, str):
        return value.strip()
    return ""


def _text(raw_payload: Mapping[str, Any], key: str) -> str:
    """Return a required text value from TOML metadata."""
    value = raw_payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    normalized_value = value.strip()
    if not normalized_value:
        raise ValueError(f"{key} must be non-empty")
    return normalized_value


def _text_tuple(raw_payload: Mapping[str, Any], key: str) -> tuple[str, ...]:
    """Return a required list of non-empty text values."""
    value = raw_payload.get(key)
    if not isinstance(value, list):
        return ()
    text_values = tuple(item.strip() for item in value if isinstance(item, str))
    if len(text_values) != len(value) or any(not item for item in text_values):
        return ()
    return text_values
