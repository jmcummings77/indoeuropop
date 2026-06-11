"""Reviewed qpAdm rerun planning from target-decision files."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Literal

from indoeuropop.data.target_curation import (
    TargetCurationDataset,
    TargetCurationRecord,
    load_target_curation,
)
from indoeuropop.data.target_decisions import (
    TargetDecisionDataset,
    TargetDecisionRecord,
    load_target_decisions,
)

QPADM_RERUN_MANIFEST_SCHEMA_VERSION = 1

QpAdmRerunFailureReason = Literal[
    "invalid_steppe_fraction",
    "invalid_standard_error",
    "replicated_group_level_estimates",
    "incomplete_qpadm_evidence",
]

QPADM_RERUN_GROUP_COLUMNS = (
    "region",
    "aadr_group_id",
    "failure_reason",
    "target_id",
    "sample_count",
)


@dataclass(frozen=True)
class QpAdmRerunTarget:
    """One target group that needs an external qpAdm rerun or review."""

    target_id: str
    requested_group_id: str
    region: str
    sample_count: int
    failure_reason: QpAdmRerunFailureReason
    decision_reason: str
    note: str = ""

    def __post_init__(self) -> None:
        """Validate rerun-target fields."""
        for field_name in (
            "target_id",
            "requested_group_id",
            "region",
            "failure_reason",
            "decision_reason",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must be non-empty")
        if self.sample_count <= 0:
            raise ValueError("sample_count must be positive")


@dataclass(frozen=True)
class QpAdmRerunGroup:
    """Rerun targets grouped by a shared failure reason."""

    failure_reason: QpAdmRerunFailureReason
    targets: tuple[QpAdmRerunTarget, ...]

    def __post_init__(self) -> None:
        """Validate rerun-group contents."""
        if not self.targets:
            raise ValueError("targets must contain at least one rerun target")
        for target in self.targets:
            if target.failure_reason != self.failure_reason:
                raise ValueError("all targets must match the group failure reason")


@dataclass(frozen=True)
class QpAdmRerunManifest:
    """A grouped manifest for external qpAdm reruns."""

    targets: tuple[QpAdmRerunTarget, ...]

    def __post_init__(self) -> None:
        """Validate the manifest contains rerun work."""
        if not self.targets:
            raise ValueError("rerun manifest must contain at least one target")

    @property
    def groups(self) -> tuple[QpAdmRerunGroup, ...]:
        """Return rerun targets grouped by failure reason in first-seen order."""
        groups: list[QpAdmRerunGroup] = []
        for failure_reason in _unique(target.failure_reason for target in self.targets):
            groups.append(
                QpAdmRerunGroup(
                    failure_reason=failure_reason,
                    targets=tuple(
                        target
                        for target in self.targets
                        if target.failure_reason == failure_reason
                    ),
                )
            )
        return tuple(groups)


def build_qpadm_rerun_manifest(
    curation: TargetCurationDataset,
    decisions: TargetDecisionDataset,
) -> QpAdmRerunManifest:
    """Build a rerun manifest from curation rows and reviewed decisions."""
    curation_by_id = _curation_by_target_id(curation.require_records().records)
    rerun_targets = tuple(
        _rerun_target(decision, curation_by_id)
        for decision in decisions.require_records().records
        if decision.decision == "rerun_qpadm"
    )
    return QpAdmRerunManifest(rerun_targets)


def load_qpadm_rerun_manifest_inputs(
    *,
    curation_path: str | Path,
    decisions_path: str | Path,
) -> QpAdmRerunManifest:
    """Load target curation and decisions, then build a rerun manifest."""
    return build_qpadm_rerun_manifest(
        load_target_curation(curation_path),
        load_target_decisions(decisions_path),
    )


def qpadm_rerun_manifest_payload(manifest: QpAdmRerunManifest) -> dict[str, object]:
    """Return a JSON-ready rerun manifest payload."""
    return {
        "schema_version": QPADM_RERUN_MANIFEST_SCHEMA_VERSION,
        "kind": "qpadm_rerun_manifest",
        "target_count": len(manifest.targets),
        "failure_groups": [
            {
                "failure_reason": group.failure_reason,
                "target_count": len(group.targets),
                "targets": [_target_payload(target) for target in group.targets],
            }
            for group in manifest.groups
        ],
    }


def write_qpadm_rerun_manifest_json(
    manifest: QpAdmRerunManifest, path: str | Path
) -> Path:
    """Write a rerun manifest JSON file and return the output path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(qpadm_rerun_manifest_payload(manifest), indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def qpadm_rerun_group_rows(
    manifest: QpAdmRerunManifest,
) -> tuple[dict[str, str], ...]:
    """Return rerun targets as annotated AADR group-selection rows."""
    return tuple(
        {
            "region": target.region,
            "aadr_group_id": target.requested_group_id,
            "failure_reason": target.failure_reason,
            "target_id": target.target_id,
            "sample_count": str(target.sample_count),
        }
        for target in manifest.targets
    )


def qpadm_rerun_groups_tsv(manifest: QpAdmRerunManifest) -> str:
    """Return an annotated TSV usable as an AADR group-selection file."""
    output = StringIO()
    writer = csv.DictWriter(
        output,
        delimiter="\t",
        fieldnames=QPADM_RERUN_GROUP_COLUMNS,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(qpadm_rerun_group_rows(manifest))
    return output.getvalue()


def write_qpadm_rerun_groups_tsv(
    manifest: QpAdmRerunManifest, path: str | Path
) -> Path:
    """Write annotated rerun group selections and return the output path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(qpadm_rerun_groups_tsv(manifest), encoding="utf-8")
    return output_path


def _rerun_target(
    decision: TargetDecisionRecord,
    curation_by_id: dict[str, TargetCurationRecord],
) -> QpAdmRerunTarget:
    """Return one rerun target from a reviewed decision."""
    curation = curation_by_id.get(decision.target_id)
    if curation is None:
        raise ValueError(
            f"target decision references unknown target {decision.target_id}"
        )
    requested_group_id = decision.requested_group_id or _requested_group_id(curation)
    return QpAdmRerunTarget(
        target_id=decision.target_id,
        requested_group_id=requested_group_id,
        region=curation.region,
        sample_count=curation.sample_count,
        failure_reason=_failure_reason(decision),
        decision_reason=decision.reason,
        note=decision.note,
    )


def _target_payload(target: QpAdmRerunTarget) -> dict[str, object]:
    """Return one rerun target as a JSON-ready mapping."""
    return {
        "target_id": target.target_id,
        "requested_group_id": target.requested_group_id,
        "region": target.region,
        "sample_count": target.sample_count,
        "decision_reason": target.decision_reason,
        "note": target.note,
    }


def _failure_reason(decision: TargetDecisionRecord) -> QpAdmRerunFailureReason:
    """Classify a rerun decision into a compact failure reason."""
    text = f"{decision.reason} {decision.note}".lower()
    if "steppe fraction" in text and "outside 0-1" in text:
        return "invalid_steppe_fraction"
    if "standard error" in text and "outside 0-1" in text:
        return "invalid_standard_error"
    if "identical replicated" in text or "group-level" in text:
        return "replicated_group_level_estimates"
    return "incomplete_qpadm_evidence"


def _curation_by_target_id(
    records: tuple[TargetCurationRecord, ...],
) -> dict[str, TargetCurationRecord]:
    """Return curation records keyed by target ID."""
    return {record.target_id: record for record in records}


def _requested_group_id(record: TargetCurationRecord) -> str:
    """Extract the requested AADR group ID from a curation note."""
    prefix = "requested_group_id="
    for part in record.note.split(";"):
        cleaned = part.strip()
        if cleaned.startswith(prefix):
            return cleaned.removeprefix(prefix)
    raise ValueError(f"target {record.target_id} is missing requested_group_id")


def _unique(
    values: Iterable[QpAdmRerunFailureReason],
) -> tuple[QpAdmRerunFailureReason, ...]:
    """Return unique failure reasons while preserving insertion order."""
    unique_values: list[QpAdmRerunFailureReason] = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)
    return tuple(unique_values)
