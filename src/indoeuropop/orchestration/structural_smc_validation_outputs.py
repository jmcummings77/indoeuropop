"""Output paths and manifests for multi-fold structural SMC validation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import cast

from indoeuropop.orchestration.experiments import (
    ArtifactRole,
    ExperimentArtifact,
    ExperimentManifest,
    artifact_from_path,
)
from indoeuropop.orchestration.structural_smc_validation_models import (
    StructuralSMCValidationFoldResult,
    StructuralSMCValidationOutputPaths,
)


def structural_smc_validation_output_paths_from_dir(
    output_dir: str | Path,
    *,
    config: Path | None = None,
    targets: Path | None = None,
    child_region_overrides: Path | None = None,
) -> StructuralSMCValidationOutputPaths:
    """Return conventional multi-fold structural SMC output paths."""
    root = Path(output_dir)
    return StructuralSMCValidationOutputPaths(
        output_dir=root,
        config=config,
        targets=targets,
        child_region_overrides=child_region_overrides,
        summary_csv=root / "structural-smc-validation-summary.csv",
        report_md=root / "structural-smc-validation.md",
        manifest_json=root / "structural-smc-validation-manifest.json",
    )


def structural_smc_validation_artifacts(
    paths: StructuralSMCValidationOutputPaths,
    results: Iterable[StructuralSMCValidationFoldResult],
) -> tuple[ExperimentArtifact, ...]:
    """Return checksum-bearing artifacts for a multi-fold validation run."""
    artifacts: list[ExperimentArtifact] = []
    for name, role, path in (
        ("config", "config", paths.config),
        ("targets", "targets", paths.targets),
        ("child_region_overrides", "config", paths.child_region_overrides),
        ("summary_csv", "target_fit", paths.summary_csv),
        ("report_md", "other", paths.report_md),
    ):
        if path is not None:
            artifacts.append(artifact_from_path(name, cast(ArtifactRole, role), path))
    for result in results:
        artifacts.extend(_fold_artifacts(result))
    return tuple(artifacts)


def structural_smc_validation_manifest(
    results: tuple[StructuralSMCValidationFoldResult, ...],
    *,
    artifacts: Iterable[ExperimentArtifact] = (),
    command: str = "programmatic-validate-structured-candidates-smc",
    metadata: Mapping[str, str] | None = None,
) -> ExperimentManifest:
    """Return a top-level manifest for multi-fold structural validation."""
    manifest_metadata = {
        "command": command,
        "fold_count": str(len(results)),
        "preference_disagreement_count": str(
            sum(result.has_preference_disagreement for result in results)
        ),
        "calibration_child_preferred_count": str(
            _candidate_count(results, "calibration", "child_override")
        ),
        "holdout_child_preferred_count": str(
            _candidate_count(results, "holdout", "child_override")
        ),
    }
    manifest_metadata.update({} if metadata is None else metadata)
    return ExperimentManifest(
        name="structural-smc-validation",
        description="Multi-fold structural SMC validation manifest",
        artifacts=tuple(artifacts),
        metadata=manifest_metadata,
    )


def _fold_artifacts(
    result: StructuralSMCValidationFoldResult,
) -> tuple[ExperimentArtifact, ...]:
    """Return report and manifest artifacts for one fold."""
    artifacts: list[ExperimentArtifact] = []
    comparison = result.comparison
    for suffix, path in (
        ("report_md", comparison.head_to_head_report_md_path),
        ("manifest_json", comparison.manifest_json_path),
    ):
        if path is not None:
            artifacts.append(
                artifact_from_path(f"{result.spec.name}_{suffix}", "other", path)
            )
    return tuple(artifacts)


def _candidate_count(
    results: tuple[StructuralSMCValidationFoldResult, ...],
    split: str,
    candidate: str,
) -> int:
    """Return how often one candidate is preferred in a split."""
    if split == "calibration":
        return sum(
            result.calibration_preferred_candidate == candidate for result in results
        )
    return sum(result.holdout_preferred_candidate == candidate for result in results)
