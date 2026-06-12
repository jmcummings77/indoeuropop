"""Shared types for real-pipeline readiness reporting."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from indoeuropop.data.curation_decisions import CurationDecisionValidationReport

DEFAULT_DATA_SOURCE_CATALOG = Path("curation/local-aadr-v66-data-sources.toml")
DEFAULT_CURATION_DECISION_FILES = (
    Path("curation/aadr-v66-central-europe-child-overrides.toml"),
    Path("curation/aadr-v66-central-europe-child-overrides-interaction-best.toml"),
)


@dataclass(frozen=True)
class PipelineArtifactRequirement:
    """One required local source, curation, or generated-result artifact."""

    label: str
    path: Path
    role: str
    required: bool = True

    def __post_init__(self) -> None:
        """Validate artifact metadata used in readiness reports."""
        if not self.label:
            raise ValueError("label must be non-empty")
        if not self.role:
            raise ValueError("role must be non-empty")
        if not str(self.path):
            raise ValueError("path must be non-empty")


@dataclass(frozen=True)
class PipelineArtifactStatus:
    """Existence and size status for one local pipeline artifact."""

    label: str
    relative_path: str
    role: str
    required: bool
    exists: bool
    size_bytes: int | None = None

    @property
    def status(self) -> str:
        """Return a compact status label for Markdown and CLI output."""
        if self.exists:
            return "present"
        if self.required:
            return "missing"
        return "optional-missing"


@dataclass(frozen=True)
class ReadinessMetric:
    """One scalar metric extracted from diagnostics or review artifacts."""

    name: str
    value: str
    source: str

    def __post_init__(self) -> None:
        """Validate metric fields before report rendering."""
        if not self.name:
            raise ValueError("metric name must be non-empty")
        if not self.value:
            raise ValueError("metric value must be non-empty")
        if not self.source:
            raise ValueError("metric source must be non-empty")


@dataclass(frozen=True)
class RealPipelineReadinessReport:
    """Status summary for the local real-data modeling pipeline."""

    artifacts: tuple[PipelineArtifactStatus, ...]
    metrics: tuple[ReadinessMetric, ...]
    issues: tuple[str, ...]
    curation_decisions: CurationDecisionValidationReport

    @property
    def ready(self) -> bool:
        """Return whether all required checks passed."""
        return not self.issues and self.curation_decisions.valid


DEFAULT_PIPELINE_ARTIFACTS = (
    PipelineArtifactRequirement(
        "data source catalog",
        DEFAULT_DATA_SOURCE_CATALOG,
        "source_catalog",
    ),
    PipelineArtifactRequirement(
        "baseline AADR target diagnostics",
        Path("results/real-aadr-comparison/aadr-target-diagnostics.json"),
        "diagnostics",
    ),
    PipelineArtifactRequirement(
        "baseline AADR target observations",
        Path("results/real-aadr-comparison/aadr-target-observations.csv"),
        "targets",
    ),
    PipelineArtifactRequirement(
        "baseline target comparison manifest",
        Path("results/real-aadr-comparison/target-comparison-manifest.json"),
        "manifest",
    ),
    PipelineArtifactRequirement(
        "qpAdm rerun diagnostics",
        Path("results/qpadm-rerun/qpadm-rerun-diagnostics.json"),
        "diagnostics",
    ),
    PipelineArtifactRequirement(
        "accepted qpAdm target observations",
        Path("results/qpadm-rerun/accepted-target-observations.csv"),
        "targets",
    ),
    PipelineArtifactRequirement(
        "accepted target validation fit",
        Path("results/qpadm-rerun/accepted-validation-fit.csv"),
        "validation",
    ),
    PipelineArtifactRequirement(
        "accepted target validation manifest",
        Path("results/qpadm-rerun/accepted-validation-manifest.json"),
        "manifest",
    ),
    PipelineArtifactRequirement(
        "central-Europe structured targets",
        Path("results/qpadm-rerun/central-europe-structured-targets.csv"),
        "targets",
    ),
    PipelineArtifactRequirement(
        "interaction-best override curation",
        Path("curation/aadr-v66-central-europe-child-overrides-interaction-best.toml"),
        "curation",
    ),
    PipelineArtifactRequirement(
        "interaction-best validation fit",
        Path("results/qpadm-rerun/central-europe-interaction-best-validation-fit.csv"),
        "validation",
    ),
    PipelineArtifactRequirement(
        "interaction-best override delta CSV",
        Path(
            "results/qpadm-rerun/central-europe-curated-vs-interaction-best-delta.csv"
        ),
        "delta_review",
    ),
    PipelineArtifactRequirement(
        "interaction-best override delta manifest",
        Path(
            "results/qpadm-rerun/"
            "central-europe-curated-vs-interaction-best-delta-manifest.json"
        ),
        "manifest",
    ),
    PipelineArtifactRequirement(
        "same-baseline structural head-to-head report",
        Path(
            "results/qpadm-rerun/"
            "central-europe-structured-pulse-vs-child-head-to-head.md"
        ),
        "model_selection",
    ),
    PipelineArtifactRequirement(
        "same-baseline structural head-to-head manifest",
        Path(
            "results/qpadm-rerun/"
            "central-europe-structured-pulse-vs-child-head-to-head-manifest.json"
        ),
        "manifest",
    ),
    PipelineArtifactRequirement(
        "override promotion decision",
        Path("docs/central-europe-override-decision.md"),
        "decision_record",
    ),
)
