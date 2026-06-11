"""Tests for experiment manifest metadata."""

from pathlib import Path
from typing import cast

import pytest

from indoeuropop.experiments import (
    ARTIFACT_ROLES,
    ArtifactRole,
    ExperimentArtifact,
    ExperimentManifest,
    artifact_from_path,
    experiment_manifest_records,
)
from indoeuropop.reproducibility import fingerprint_payload


def test_artifact_from_path_records_checksum_and_metadata(tmp_path: Path) -> None:
    """Artifacts built from files should include stable local checksums."""
    output_path = tmp_path / "trajectory.csv"
    output_path.write_text("time_bce,steppe\n3000,0.1\n", encoding="utf-8")

    artifact = artifact_from_path(
        "trajectory",
        "provenance",
        output_path,
        metadata={" stage ": " smoke "},
    )
    record = artifact.to_provenance_record()

    assert "provenance" in ARTIFACT_ROLES
    assert artifact.has_checksum
    assert len(artifact.checksum_sha256) == 64
    assert artifact.metadata == {"stage": "smoke"}
    assert record.name == "experiment_artifact_trajectory"
    assert record.kind == "derived"
    assert record.value == str(output_path)
    assert record.unit == "path"
    assert record.metadata["artifact_role"] == "provenance"
    assert record.metadata["artifact_checksum_sha256"] == artifact.checksum_sha256
    assert record.metadata["detail_stage"] == "smoke"


def test_artifact_from_path_can_skip_checksum(tmp_path: Path) -> None:
    """Planned or later-generated artifacts should not require checksums."""
    planned_path = tmp_path / "planned.png"

    artifact = artifact_from_path(
        "planned-plot",
        "plot",
        planned_path,
        checksum=False,
    )

    assert not artifact.has_checksum
    assert artifact.checksum_sha256 == ""
    assert "artifact_checksum_sha256" not in artifact.to_provenance_record().metadata


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": ""},
        {"role": cast(ArtifactRole, "unsupported")},
        {"path": ""},
        {"checksum_sha256": "not-a-digest"},
        {"metadata": {"": "blank"}},
        {"metadata": {"stage": object()}},
    ],
)
def test_experiment_artifact_rejects_invalid_fields(
    kwargs: dict[str, object],
) -> None:
    """Invalid artifact metadata should fail before reports use it."""
    values: dict[str, object] = {
        "name": "trajectory",
        "role": "provenance",
        "path": "outputs/trajectory.csv",
        "checksum_sha256": "B" * 64,
        "metadata": {"stage": "smoke"},
    }
    values.update(kwargs)

    with pytest.raises(ValueError):
        ExperimentArtifact(**values)  # type: ignore[arg-type]


def test_experiment_manifest_collects_records_in_order(tmp_path: Path) -> None:
    """A manifest should bridge artifacts and fingerprints into provenance."""
    artifact_path = tmp_path / "summary.csv"
    artifact_path.write_text("metric,value\nfinal_ancestry,0.25\n", encoding="utf-8")
    artifact = artifact_from_path("summary", "provenance", artifact_path)
    fingerprint = fingerprint_payload("simulation_result", {"run": "demo"})
    manifest = ExperimentManifest(
        name="demo run",
        description="Smoke-test manifest",
        artifacts=(artifact,),
        fingerprints=(fingerprint,),
        metadata={"scenario": "synthetic"},
    )

    records = manifest.to_provenance_records()
    standalone_records = experiment_manifest_records(manifest)

    assert records == standalone_records
    assert manifest.artifact_names() == ("summary",)
    assert manifest.fingerprint_digests() == (fingerprint.digest_sha256,)
    assert [record.name for record in records] == [
        "experiment_manifest",
        "experiment_artifact_summary",
        "simulation_result_fingerprint",
    ]
    assert records[0].value == "demo run"
    assert records[0].metadata == {
        "artifact_count": "1",
        "fingerprint_count": "1",
        "description": "Smoke-test manifest",
        "manifest_scenario": "synthetic",
    }
    assert records[2].metadata["manifest_name"] == "demo run"


def test_experiment_manifest_allows_fingerprint_only_outputs() -> None:
    """Some early workflow checks may only have reproducibility fingerprints."""
    fingerprint = fingerprint_payload("simulation_result", {"run": "demo"})

    manifest = ExperimentManifest(
        name="fingerprint-only",
        fingerprints=(fingerprint,),
    )

    assert manifest.artifact_names() == ()
    assert manifest.fingerprint_digests() == (fingerprint.digest_sha256,)
    assert len(manifest.to_provenance_records()) == 2


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"name": ""}, "name"),
        ({"artifacts": (), "fingerprints": ()}, "artifacts or fingerprints"),
        (
            {
                "artifacts": (
                    ExperimentArtifact("duplicate", "other", "one.txt"),
                    ExperimentArtifact("duplicate", "other", "two.txt"),
                )
            },
            "artifact names",
        ),
        (
            {
                "fingerprints": (
                    fingerprint_payload("simulation_result", {"run": "demo"}),
                    fingerprint_payload("simulation_result", {"run": "demo"}),
                )
            },
            "fingerprint digests",
        ),
        ({"metadata": {"": "blank"}}, "metadata"),
        ({"metadata": {"stage": object()}}, "metadata"),
    ],
)
def test_experiment_manifest_rejects_invalid_metadata(
    kwargs: dict[str, object],
    match: str,
) -> None:
    """Manifest-level validation should catch incomplete run envelopes."""
    values: dict[str, object] = {
        "name": "demo",
        "artifacts": (ExperimentArtifact("summary", "other", "summary.csv"),),
        "fingerprints": (),
        "metadata": {"scenario": "synthetic"},
    }
    values.update(kwargs)

    with pytest.raises(ValueError, match=match):
        ExperimentManifest(**values)  # type: ignore[arg-type]
