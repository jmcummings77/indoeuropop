"""Generated artifact manifest checks for curation review metadata."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from indoeuropop.data.data_sources import sha256_file

HEAD_TO_HEAD_REPORT_ARTIFACT_NAME = "head_to_head_report_md"
HEAD_TO_HEAD_REPORT_REVIEW_KEY = "same_baseline_head_to_head_report"
VALIDATION_ARTIFACTS = (
    ("baseline_validation_fit_csv", "baseline_validation_fit_csv"),
    ("override_validation_fit_csv", "override_validation_fit_csv"),
)


def artifact_manifest_path(report_path: Path) -> Path:
    """Return the manifest path convention for a generated Markdown report."""
    return report_path.with_name(f"{report_path.stem}-manifest.json")


def validation_manifest_artifact_issues(
    record_relative_path: str,
    review: Mapping[str, Any],
    root: Path,
    manifest_path: Path,
) -> tuple[str, ...]:
    """Return stale validation artifact issues from a delta manifest."""
    artifacts = _manifest_artifacts(manifest_path)
    issues: list[str] = []
    for name, review_key in VALIDATION_ARTIFACTS:
        expected_path = _review_path_text(review, review_key)
        if expected_path:
            issues.extend(
                _expected_artifact_path_issues(
                    record_relative_path,
                    artifacts,
                    name,
                    expected_path,
                )
            )
    issues.extend(_manifest_checksum_issues(record_relative_path, root, artifacts))
    return tuple(issues)


def same_baseline_head_to_head_artifact_issues(
    record_relative_path: str,
    review: Mapping[str, Any],
    root: Path,
) -> tuple[str, ...]:
    """Return issues for the same-baseline head-to-head report manifest."""
    report_text = _review_path_text(review, HEAD_TO_HEAD_REPORT_REVIEW_KEY)
    if not report_text:
        return (
            f"{record_relative_path}: {HEAD_TO_HEAD_REPORT_REVIEW_KEY} "
            "must be declared",
        )

    issues: list[str] = []
    report_path = root / report_text
    if not report_path.exists():
        issues.append(
            f"{record_relative_path}: {HEAD_TO_HEAD_REPORT_REVIEW_KEY} does not exist"
        )

    manifest_path = artifact_manifest_path(report_path)
    if not manifest_path.exists():
        issues.append(
            f"{record_relative_path}: {HEAD_TO_HEAD_REPORT_REVIEW_KEY} "
            "manifest missing"
        )
        return tuple(issues)

    artifacts = _manifest_artifacts(manifest_path)
    issues.extend(
        _expected_artifact_path_issues(
            record_relative_path,
            artifacts,
            HEAD_TO_HEAD_REPORT_ARTIFACT_NAME,
            report_text,
        )
    )
    issues.extend(_manifest_checksum_issues(record_relative_path, root, artifacts))
    return tuple(issues)


def _manifest_artifacts(manifest_path: Path) -> dict[str, Mapping[str, Any]]:
    """Return manifest artifacts keyed by artifact name."""
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        artifact["name"]: artifact
        for artifact in payload.get("artifacts", [])
        if isinstance(artifact, dict) and isinstance(artifact.get("name"), str)
    }


def _expected_artifact_path_issues(
    record_relative_path: str,
    artifacts: Mapping[str, Mapping[str, Any]],
    name: str,
    expected_path: str,
) -> tuple[str, ...]:
    """Return missing or stale path issues for one expected artifact."""
    artifact = artifacts.get(name)
    if artifact is None:
        return (f"{record_relative_path}: manifest missing {name}",)
    if artifact.get("path") != expected_path:
        return (f"{record_relative_path}: manifest {name} path is stale",)
    return ()


def _manifest_checksum_issues(
    record_relative_path: str,
    root: Path,
    artifacts: Mapping[str, Mapping[str, Any]],
) -> tuple[str, ...]:
    """Return stale or missing file issues for every manifest artifact."""
    issues: list[str] = []
    for name, artifact in artifacts.items():
        path_text = artifact.get("path")
        checksum = artifact.get("checksum_sha256")
        if not isinstance(path_text, str) or not isinstance(checksum, str):
            issues.append(f"{record_relative_path}: manifest {name} is malformed")
            continue
        artifact_path = root / path_text
        if not artifact_path.exists():
            issues.append(
                f"{record_relative_path}: manifest {name} path does not exist"
            )
            continue
        if sha256_file(artifact_path) != checksum:
            issues.append(f"{record_relative_path}: manifest {name} checksum is stale")
    return tuple(issues)


def _review_path_text(raw_payload: Mapping[str, Any], key: str) -> str:
    """Return an optional normalized path value from review metadata."""
    value = raw_payload.get(key, "")
    if isinstance(value, str):
        stripped_value = value.strip()
        if stripped_value:
            return Path(stripped_value).as_posix()
    return ""
