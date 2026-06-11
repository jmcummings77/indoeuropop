"""Experiment manifests for reproducible IndoEuroPop workflow outputs."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from indoeuropop.data.data_sources import sha256_file
from indoeuropop.reporting.provenance import ProvenanceRecord
from indoeuropop.reporting.reproducibility import ReproducibilityFingerprint

ArtifactRole = Literal[
    "config",
    "targets",
    "provenance",
    "plot",
    "fingerprint",
    "emulator_training",
    "emulator_validation",
    "sweep_runs",
    "sensitivity",
    "target_fit",
    "other",
]

ARTIFACT_ROLES = frozenset(
    {
        "config",
        "targets",
        "provenance",
        "plot",
        "fingerprint",
        "emulator_training",
        "emulator_validation",
        "sweep_runs",
        "sensitivity",
        "target_fit",
        "other",
    }
)

HEX_DIGITS = frozenset("0123456789abcdef")
EXPERIMENT_MANIFEST_SCHEMA_VERSION = "indoeuropop-experiment-manifest-v1"


@dataclass(frozen=True)
class ExperimentArtifact:
    """One file or generated output attached to an experiment manifest.

    The artifact record is intentionally descriptive rather than inferential:
    it says what a file is, where it lives, and optionally what its SHA-256
    digest is. It does not claim that the file is historically authoritative.
    """

    name: str
    role: ArtifactRole
    path: str
    checksum_sha256: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and normalize artifact metadata."""
        normalized_name = self.name.strip()
        normalized_path = self.path.strip()
        if not normalized_name:
            raise ValueError("artifact name must be non-empty")
        if self.role not in ARTIFACT_ROLES:
            raise ValueError("artifact role is not supported")
        if not normalized_path:
            raise ValueError("artifact path must be non-empty")
        object.__setattr__(self, "name", normalized_name)
        object.__setattr__(self, "path", normalized_path)
        object.__setattr__(
            self,
            "checksum_sha256",
            _normalized_sha256(self.checksum_sha256),
        )
        object.__setattr__(self, "metadata", _normalized_metadata(self.metadata))

    @property
    def has_checksum(self) -> bool:
        """Return whether this artifact includes a SHA-256 checksum."""
        return self.checksum_sha256 != ""

    def to_provenance_record(self) -> ProvenanceRecord:
        """Return this artifact as a derived provenance record."""
        metadata = {
            "artifact_role": self.role,
            "artifact_path": self.path,
        }
        if self.has_checksum:
            metadata["artifact_checksum_sha256"] = self.checksum_sha256
        for key, value in self.metadata.items():
            metadata[f"detail_{key}"] = value
        return ProvenanceRecord(
            name=f"experiment_artifact_{self.name}",
            kind="derived",
            value=self.path,
            unit="path",
            metadata=metadata,
        )


@dataclass(frozen=True)
class ExperimentManifest:
    """A reproducibility envelope for one model run or workflow output set.

    A manifest can contain generated files, model fingerprints, or both. It is
    a small bridge between the scientific workflow docs and the typed
    provenance records already used by reports.
    """

    name: str
    description: str = ""
    artifacts: tuple[ExperimentArtifact, ...] = ()
    fingerprints: tuple[ReproducibilityFingerprint, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate manifest identity, contents, and uniqueness."""
        normalized_name = self.name.strip()
        normalized_description = self.description.strip()
        normalized_artifacts = tuple(self.artifacts)
        normalized_fingerprints = tuple(self.fingerprints)
        if not normalized_name:
            raise ValueError("manifest name must be non-empty")
        if not normalized_artifacts and not normalized_fingerprints:
            raise ValueError("manifest must include artifacts or fingerprints")
        _ensure_unique(
            (artifact.name for artifact in normalized_artifacts),
            "artifact names must be unique",
        )
        _ensure_unique(
            (fingerprint.digest_sha256 for fingerprint in normalized_fingerprints),
            "fingerprint digests must be unique",
        )
        object.__setattr__(self, "name", normalized_name)
        object.__setattr__(self, "description", normalized_description)
        object.__setattr__(self, "artifacts", normalized_artifacts)
        object.__setattr__(self, "fingerprints", normalized_fingerprints)
        object.__setattr__(self, "metadata", _normalized_metadata(self.metadata))

    def artifact_names(self) -> tuple[str, ...]:
        """Return artifact names in manifest order."""
        return tuple(artifact.name for artifact in self.artifacts)

    def fingerprint_digests(self) -> tuple[str, ...]:
        """Return fingerprint digests in manifest order."""
        return tuple(fingerprint.digest_sha256 for fingerprint in self.fingerprints)

    def to_provenance_records(self) -> tuple[ProvenanceRecord, ...]:
        """Return manifest, artifact, and fingerprint provenance records."""
        return experiment_manifest_records(self)


def artifact_from_path(
    name: str,
    role: ArtifactRole,
    path: str | Path,
    *,
    checksum: bool = True,
    metadata: Mapping[str, str] | None = None,
) -> ExperimentArtifact:
    """Build an artifact record for a local path.

    When ``checksum`` is true, the file must exist and its SHA-256 digest is
    embedded in the artifact. When it is false, the artifact remains a path
    marker only, which is useful for planned outputs or files produced later in
    a pipeline.
    """
    artifact_path = Path(path)
    checksum_sha256 = sha256_file(artifact_path) if checksum else ""
    return ExperimentArtifact(
        name=name,
        role=role,
        path=str(artifact_path),
        checksum_sha256=checksum_sha256,
        metadata={} if metadata is None else metadata,
    )


def experiment_manifest_records(
    manifest: ExperimentManifest,
) -> tuple[ProvenanceRecord, ...]:
    """Return flat provenance records for an experiment manifest."""
    return (
        _manifest_record(manifest),
        *(artifact.to_provenance_record() for artifact in manifest.artifacts),
        *(
            _fingerprint_record(manifest.name, fingerprint)
            for fingerprint in manifest.fingerprints
        ),
    )


def experiment_artifact_payload(artifact: ExperimentArtifact) -> dict[str, object]:
    """Return a JSON-ready payload for one experiment artifact."""
    return {
        "name": artifact.name,
        "role": artifact.role,
        "path": artifact.path,
        "checksum_sha256": artifact.checksum_sha256,
        "metadata": dict(artifact.metadata),
    }


def experiment_manifest_payload(
    manifest: ExperimentManifest,
) -> dict[str, object]:
    """Return a JSON-ready payload for an experiment manifest."""
    return {
        "schema_version": EXPERIMENT_MANIFEST_SCHEMA_VERSION,
        "name": manifest.name,
        "description": manifest.description,
        "metadata": dict(manifest.metadata),
        "artifacts": [
            experiment_artifact_payload(artifact) for artifact in manifest.artifacts
        ],
        "fingerprints": [
            {
                "kind": fingerprint.kind,
                "digest_sha256": fingerprint.digest_sha256,
                "payload": dict(fingerprint.payload),
            }
            for fingerprint in manifest.fingerprints
        ],
    }


def write_experiment_manifest_json(
    manifest: ExperimentManifest,
    path: str | Path,
) -> Path:
    """Write an experiment manifest as stable, human-readable JSON."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = experiment_manifest_payload(manifest)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _manifest_record(manifest: ExperimentManifest) -> ProvenanceRecord:
    """Return the top-level manifest provenance record."""
    metadata = {
        "artifact_count": str(len(manifest.artifacts)),
        "fingerprint_count": str(len(manifest.fingerprints)),
    }
    if manifest.description:
        metadata["description"] = manifest.description
    for key, value in manifest.metadata.items():
        metadata[f"manifest_{key}"] = value
    return ProvenanceRecord(
        name="experiment_manifest",
        kind="derived",
        value=manifest.name,
        metadata=metadata,
    )


def _fingerprint_record(
    manifest_name: str,
    fingerprint: ReproducibilityFingerprint,
) -> ProvenanceRecord:
    """Return a fingerprint record annotated with its manifest name."""
    base_record = fingerprint.to_provenance_record()
    metadata = dict(base_record.metadata)
    metadata["manifest_name"] = manifest_name
    return ProvenanceRecord(
        name=base_record.name,
        kind=base_record.kind,
        value=base_record.value,
        unit=base_record.unit,
        metadata=metadata,
    )


def _normalized_sha256(value: str) -> str:
    """Return a normalized SHA-256 digest or raise for malformed text."""
    if value == "":
        return ""
    normalized = value.lower()
    if len(normalized) != 64 or any(
        character not in HEX_DIGITS for character in normalized
    ):
        raise ValueError("checksum_sha256 must be a 64-character hex digest")
    return normalized


def _normalized_metadata(metadata: Mapping[str, str]) -> dict[str, str]:
    """Return validated string metadata as a plain dictionary."""
    normalized: dict[str, str] = {}
    for key, value in metadata.items():
        normalized_key = key.strip()
        if not normalized_key:
            raise ValueError("metadata keys must be non-empty")
        if not isinstance(value, str):
            raise ValueError("metadata values must be strings")
        normalized[normalized_key] = value.strip()
    return normalized


def _ensure_unique(values: Iterable[str], message: str) -> None:
    """Raise when an iterable contains duplicate string values."""
    value_tuple = tuple(values)
    if len(set(value_tuple)) != len(value_tuple):
        raise ValueError(message)
