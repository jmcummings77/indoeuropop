"""Output paths and manifests for structural SMC comparisons."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from indoeuropop.analysis.child_region_candidates import ChildRegionCandidate
from indoeuropop.analysis.structural_candidates import PosteriorPredictiveMetricDelta
from indoeuropop.analysis.structural_head_to_head import StructuredPulseCandidate
from indoeuropop.orchestration.abc_smc import (
    ABCSMCOutputPaths,
    ABCSMCWorkflowResult,
    abc_smc_artifacts,
    abc_smc_scored_runs,
)
from indoeuropop.orchestration.experiments import (
    ArtifactRole,
    ExperimentArtifact,
    ExperimentManifest,
    artifact_from_path,
)
from indoeuropop.orchestration.sweeps import SweepRun
from indoeuropop.reporting.reproducibility import fingerprint_sweep_collection


@dataclass(frozen=True)
class StructuralSMCOutputPaths:
    """Input and output paths for SMC structural candidate comparison."""

    config: Path | None = None
    targets: Path | None = None
    holdout_targets: Path | None = None
    child_region_overrides: Path | None = None
    structured_pulse_config_toml: Path | None = None
    child_candidate_config_toml: Path | None = None
    baseline: ABCSMCOutputPaths = field(default_factory=ABCSMCOutputPaths)
    structured_pulse: ABCSMCOutputPaths = field(default_factory=ABCSMCOutputPaths)
    child: ABCSMCOutputPaths = field(default_factory=ABCSMCOutputPaths)
    head_to_head_report_md: Path | None = None
    manifest_json: Path | None = None


@dataclass(frozen=True)
class StructuralSMCComparisonResult:
    """Result for SMC-based structured pulse versus child override comparison."""

    structured_pulse_candidate: StructuredPulseCandidate
    structured_pulse_region_count: int
    child_candidate: ChildRegionCandidate
    baseline: ABCSMCWorkflowResult
    structured_pulse_result: ABCSMCWorkflowResult
    child_result: ABCSMCWorkflowResult
    structured_pulse_delta: PosteriorPredictiveMetricDelta
    child_delta: PosteriorPredictiveMetricDelta
    structured_pulse_holdout_delta: PosteriorPredictiveMetricDelta | None = None
    child_holdout_delta: PosteriorPredictiveMetricDelta | None = None
    artifacts: tuple[ExperimentArtifact, ...] = ()
    manifest: ExperimentManifest | None = None
    structured_pulse_config_toml_path: Path | None = None
    child_candidate_config_toml_path: Path | None = None
    head_to_head_report_md_path: Path | None = None
    manifest_json_path: Path | None = None

    @property
    def child_minus_structured_pulse_rmse_delta(self) -> float:
        """Return child calibration RMSE delta minus structured-pulse delta."""
        return (
            self.child_delta.root_mean_squared_error_delta
            - self.structured_pulse_delta.root_mean_squared_error_delta
        )

    @property
    def child_minus_structured_pulse_holdout_rmse_delta(self) -> float | None:
        """Return child holdout RMSE delta minus pulse delta when available."""
        if (
            self.child_holdout_delta is None
            or self.structured_pulse_holdout_delta is None
        ):
            return None
        return (
            self.child_holdout_delta.root_mean_squared_error_delta
            - self.structured_pulse_holdout_delta.root_mean_squared_error_delta
        )


def structural_smc_output_paths_from_dir(
    output_dir: str | Path,
    *,
    config: Path | None = None,
    targets: Path | None = None,
    holdout_targets: Path | None = None,
    child_region_overrides: Path | None = None,
) -> StructuralSMCOutputPaths:
    """Return conventional structural SMC output paths under one directory."""
    root = Path(output_dir)
    return StructuralSMCOutputPaths(
        config=config,
        targets=targets,
        holdout_targets=holdout_targets,
        child_region_overrides=child_region_overrides,
        structured_pulse_config_toml=root / "smc-structured-pulse-comparison.toml",
        child_candidate_config_toml=root / "smc-child-override-comparison.toml",
        baseline=_named_smc_paths(root, "smc-baseline"),
        structured_pulse=_named_smc_paths(root, "smc-structured-pulse"),
        child=_named_smc_paths(root, "smc-child-override"),
        head_to_head_report_md=root / "smc-structured-head-to-head.md",
        manifest_json=root / "smc-structured-head-to-head-manifest.json",
    )


def structural_smc_artifacts(
    paths: StructuralSMCOutputPaths,
) -> tuple[ExperimentArtifact, ...]:
    """Return checksum-bearing artifacts for structural SMC outputs."""
    artifacts: list[ExperimentArtifact] = []
    for name, role, path in (
        ("config", "config", paths.config),
        ("targets", "targets", paths.targets),
        ("holdout_targets", "targets", paths.holdout_targets),
        ("child_region_overrides", "config", paths.child_region_overrides),
        ("structured_pulse_config_toml", "config", paths.structured_pulse_config_toml),
        ("child_candidate_config_toml", "config", paths.child_candidate_config_toml),
        ("head_to_head_report_md", "other", paths.head_to_head_report_md),
    ):
        if path is not None:
            artifacts.append(artifact_from_path(name, cast(ArtifactRole, role), path))
    artifacts.extend(_prefixed_artifacts("baseline", paths.baseline))
    artifacts.extend(_prefixed_artifacts("structured_pulse", paths.structured_pulse))
    artifacts.extend(_prefixed_artifacts("child", paths.child))
    return tuple(artifacts)


def structural_smc_manifest(
    result: StructuralSMCComparisonResult,
    *,
    runs: Iterable[SweepRun],
    artifacts: Iterable[ExperimentArtifact] = (),
    command: str = "programmatic-compare-structured-candidates-smc",
    name: str = "structured-smc-head-to-head",
    description: str = "SMC same-baseline structural comparison manifest",
    metadata: Mapping[str, str] | None = None,
) -> ExperimentManifest:
    """Return a manifest for one structural SMC comparison."""
    manifest_metadata = _manifest_metadata(result, command)
    manifest_metadata.update({} if metadata is None else metadata)
    return ExperimentManifest(
        name=name,
        description=description,
        artifacts=tuple(artifacts),
        fingerprints=(fingerprint_sweep_collection(tuple(runs)),),
        metadata=manifest_metadata,
    )


def structural_smc_scored_runs(
    workflows: Iterable[ABCSMCWorkflowResult],
) -> tuple[SweepRun, ...]:
    """Return all scored sweep runs from compared SMC workflows."""
    runs: list[SweepRun] = []
    for workflow in workflows:
        runs.extend(abc_smc_scored_runs(workflow.inference))
    return tuple(runs)


def _named_smc_paths(output_dir: Path, stem: str) -> ABCSMCOutputPaths:
    """Return conventional SMC artifact paths for one named model."""
    return ABCSMCOutputPaths(
        generations_csv=output_dir / f"{stem}-generations.csv",
        final_samples_csv=output_dir / f"{stem}-final-samples.csv",
        final_summary_csv=output_dir / f"{stem}-final-summary.csv",
        inference_report_md=output_dir / f"{stem}-report.md",
        posterior_predictive_csv=output_dir / f"{stem}-posterior-predictive.csv",
        posterior_predictive_report_md=output_dir / f"{stem}-posterior-predictive.md",
        posterior_predictive_plot=output_dir / f"{stem}-posterior-predictive.png",
        holdout_posterior_predictive_csv=(
            output_dir / f"{stem}-holdout-posterior-predictive.csv"
        ),
        holdout_posterior_predictive_report_md=(
            output_dir / f"{stem}-holdout-posterior-predictive.md"
        ),
        holdout_posterior_predictive_plot=(
            output_dir / f"{stem}-holdout-posterior-predictive.png"
        ),
    )


def _prefixed_artifacts(
    prefix: str,
    paths: ABCSMCOutputPaths,
) -> tuple[ExperimentArtifact, ...]:
    """Return nested SMC artifacts with unique names."""
    return tuple(
        ExperimentArtifact(
            name=f"{prefix}_{artifact.name}",
            role=artifact.role,
            path=artifact.path,
            checksum_sha256=artifact.checksum_sha256,
            metadata=artifact.metadata,
        )
        for artifact in abc_smc_artifacts(paths)
    )


def _manifest_metadata(
    result: StructuralSMCComparisonResult,
    command: str,
) -> dict[str, str]:
    """Return manifest metadata for a structural SMC comparison."""
    metadata = {
        "command": command,
        "structured_pulse_candidate_name": result.structured_pulse_candidate.name,
        "structured_pulse_region_prefix": (
            result.structured_pulse_candidate.region_prefix
        ),
        "structured_pulse_region_count": str(result.structured_pulse_region_count),
        "child_candidate_name": result.child_candidate.name,
        "baseline_threshold_schedule": _thresholds(result.baseline),
        "structured_pulse_threshold_schedule": _thresholds(
            result.structured_pulse_result
        ),
        "child_threshold_schedule": _thresholds(result.child_result),
        "baseline_rmse": _rmse(result.baseline),
        "structured_pulse_rmse": _rmse(result.structured_pulse_result),
        "child_rmse": _rmse(result.child_result),
        "structured_pulse_root_mean_squared_error_delta": (
            f"{result.structured_pulse_delta.root_mean_squared_error_delta:.12g}"
        ),
        "child_root_mean_squared_error_delta": (
            f"{result.child_delta.root_mean_squared_error_delta:.12g}"
        ),
        "child_minus_structured_pulse_root_mean_squared_error_delta": (
            f"{result.child_minus_structured_pulse_rmse_delta:.12g}"
        ),
    }
    holdout_delta = result.child_minus_structured_pulse_holdout_rmse_delta
    if holdout_delta is not None:
        metadata["holdout_child_minus_structured_pulse_rmse_delta"] = (
            f"{holdout_delta:.12g}"
        )
    return metadata


def _thresholds(result: ABCSMCWorkflowResult) -> str:
    """Return one compact threshold schedule."""
    return ",".join(
        f"{threshold:.12g}" for threshold in result.inference.threshold_schedule
    )


def _rmse(result: ABCSMCWorkflowResult) -> str:
    """Return calibration posterior predictive RMSE text."""
    assert result.posterior_predictive is not None
    return f"{result.posterior_predictive.root_mean_squared_error:.12g}"
