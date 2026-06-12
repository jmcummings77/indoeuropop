"""End-to-end refresh workflow for the local real-data pipeline."""

from __future__ import annotations

import os
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from indoeuropop.analysis.inference import ABCRejectionOptions
from indoeuropop.analysis.structural_head_to_head import StructuredPulseCandidate
from indoeuropop.data.targets import load_target_dataset
from indoeuropop.orchestration.child_region_overrides import (
    load_child_region_overrides,
)
from indoeuropop.orchestration.structural_head_to_head import (
    StructuredHeadToHeadWorkflowResult,
    run_structured_head_to_head_workflow,
)
from indoeuropop.orchestration.structural_head_to_head_outputs import (
    StructuredHeadToHeadOutputPaths,
)
from indoeuropop.orchestration.target_structure import (
    TargetStructureOutputPaths,
    TargetStructureWorkflowResult,
    run_target_structure_workflow,
)
from indoeuropop.reporting.readiness import (
    load_real_pipeline_readiness,
    write_real_pipeline_readiness_markdown,
)
from indoeuropop.reporting.readiness_models import (
    DEFAULT_DATA_SOURCE_CATALOG,
    DEFAULT_PIPELINE_ARTIFACTS,
    PipelineArtifactRequirement,
    RealPipelineReadinessReport,
)
from indoeuropop.simulation.config import load_sweep_spec

DEFAULT_ACCEPTED_TARGETS = Path("results/qpadm-rerun/accepted-target-observations.csv")
DEFAULT_BASE_CONFIG = Path("curation/aadr-v66-western-europe-comparison.toml")
DEFAULT_CHILD_OVERRIDES = Path(
    "curation/aadr-v66-central-europe-child-overrides-interaction-best.toml"
)
DEFAULT_CHILD_CANDIDATE_NAME = "central-europe-child-interaction-best"
DEFAULT_FIT_METRIC = "root_mean_squared_error"
DEFAULT_FOCUS_OBSERVATION_INDEX = 9
DEFAULT_STRUCTURE_FIELD = "note:requested_group_id"
DEFAULT_STRUCTURE_REGIONS = ("central_europe",)
DEFAULT_STRUCTURED_CONFIG = Path(
    "results/qpadm-rerun/central-europe-structured-comparison.toml"
)
DEFAULT_STRUCTURED_TARGETS = Path(
    "results/qpadm-rerun/central-europe-structured-targets.csv"
)


@dataclass(frozen=True)
class RealPipelineRefreshPaths:
    """Input and output paths for the standard real-pipeline refresh."""

    base_config: Path = DEFAULT_BASE_CONFIG
    accepted_targets: Path = DEFAULT_ACCEPTED_TARGETS
    structured_targets: Path = DEFAULT_STRUCTURED_TARGETS
    structured_config: Path = DEFAULT_STRUCTURED_CONFIG
    child_region_overrides: Path = DEFAULT_CHILD_OVERRIDES
    structured_pulse_config: Path = Path(
        "results/qpadm-rerun/central-europe-structured-broad-pulse-comparison.toml"
    )
    child_candidate_config: Path = Path(
        "results/qpadm-rerun/central-europe-child-interaction-best-head-to-head.toml"
    )
    baseline_posterior_predictive_report: Path = Path(
        "results/qpadm-rerun/central-europe-head-to-head-baseline.md"
    )
    baseline_posterior_predictive_plot: Path = Path(
        "results/qpadm-rerun/central-europe-head-to-head-baseline.png"
    )
    structured_pulse_posterior_predictive_report: Path = Path(
        "results/qpadm-rerun/central-europe-structured-broad-pulse.md"
    )
    structured_pulse_posterior_predictive_plot: Path = Path(
        "results/qpadm-rerun/central-europe-structured-broad-pulse.png"
    )
    child_posterior_predictive_report: Path = Path(
        "results/qpadm-rerun/central-europe-child-interaction-best-head-to-head.md"
    )
    child_posterior_predictive_plot: Path = Path(
        "results/qpadm-rerun/central-europe-child-interaction-best-head-to-head.png"
    )
    head_to_head_report: Path = Path(
        "results/qpadm-rerun/"
        "central-europe-structured-pulse-vs-child-head-to-head.md"
    )
    head_to_head_manifest: Path = Path(
        "results/qpadm-rerun/"
        "central-europe-structured-pulse-vs-child-head-to-head-manifest.json"
    )
    readiness_report: Path = Path("results/qpadm-rerun/real-pipeline-readiness.md")


@dataclass(frozen=True)
class RealPipelineRefreshResult:
    """Results from refreshing structure, head-to-head, and readiness outputs."""

    target_structure: TargetStructureWorkflowResult
    head_to_head: StructuredHeadToHeadWorkflowResult
    readiness: RealPipelineReadinessReport
    readiness_report_md_path: Path | None = None

    @property
    def ready(self) -> bool:
        """Return whether the refreshed real-pipeline readiness report is ready."""
        return self.readiness.ready


def default_structured_pulse_candidate() -> StructuredPulseCandidate:
    """Return the standard Central Europe broad-pulse structural candidate."""
    return StructuredPulseCandidate(
        name="central-europe-structured-broad-pulse",
        region_prefix="central_europe__",
        start_bce=3000,
        end_bce=2600,
        annual_rate=0.00005,
    )


def run_real_pipeline_refresh_workflow(
    *,
    project_root: str | Path = ".",
    paths: RealPipelineRefreshPaths | None = None,
    structure_field: str = DEFAULT_STRUCTURE_FIELD,
    structure_regions: Iterable[str] = DEFAULT_STRUCTURE_REGIONS,
    structured_pulse_candidate: StructuredPulseCandidate | None = None,
    child_candidate_name: str = DEFAULT_CHILD_CANDIDATE_NAME,
    options: ABCRejectionOptions | None = None,
    interval_probability: float = 0.9,
    focus_observation_index: int | None = DEFAULT_FOCUS_OBSERVATION_INDEX,
    readiness_curation_decision_files: Iterable[str | Path] | None = None,
    readiness_data_source_catalog: str | Path | None = DEFAULT_DATA_SOURCE_CATALOG,
    readiness_required_artifacts: Iterable[PipelineArtifactRequirement] = (
        DEFAULT_PIPELINE_ARTIFACTS
    ),
    require_curation_artifacts: bool = True,
) -> RealPipelineRefreshResult:
    """Refresh the standard real-data structural comparison and readiness gate."""
    output_paths = RealPipelineRefreshPaths() if paths is None else paths
    inference_options = (
        ABCRejectionOptions(
            fit_metric=DEFAULT_FIT_METRIC,
            acceptance_count=6,
        )
        if options is None
        else options
    )
    candidate = (
        default_structured_pulse_candidate()
        if structured_pulse_candidate is None
        else structured_pulse_candidate
    )
    with _working_directory(Path(project_root).resolve()):
        target_structure = run_target_structure_workflow(
            load_sweep_spec(output_paths.base_config),
            load_target_dataset(output_paths.accepted_targets),
            structure_field=structure_field,
            structure_regions=structure_regions,
            paths=TargetStructureOutputPaths(
                structured_targets_csv=output_paths.structured_targets,
                structured_config_toml=output_paths.structured_config,
            ),
        )
        head_to_head = run_structured_head_to_head_workflow(
            target_structure.spec,
            target_structure.targets,
            load_child_region_overrides(output_paths.child_region_overrides),
            candidate,
            child_candidate_name=child_candidate_name,
            options=inference_options,
            paths=_head_to_head_paths(output_paths),
            interval_probability=interval_probability,
            focus_observation_index=focus_observation_index,
            command="refresh-real-pipeline",
            manifest_name="refresh-real-pipeline-head-to-head",
        )
        readiness = load_real_pipeline_readiness(
            project_root=Path("."),
            curation_decision_files=readiness_curation_decision_files,
            data_source_catalog=readiness_data_source_catalog,
            required_artifacts=readiness_required_artifacts,
            require_curation_artifacts=require_curation_artifacts,
        )
        readiness_path = write_real_pipeline_readiness_markdown(
            readiness, output_paths.readiness_report
        )
    return RealPipelineRefreshResult(
        target_structure=target_structure,
        head_to_head=head_to_head,
        readiness=readiness,
        readiness_report_md_path=readiness_path,
    )


def _head_to_head_paths(
    paths: RealPipelineRefreshPaths,
) -> StructuredHeadToHeadOutputPaths:
    """Return output paths for the standard head-to-head refresh step."""
    return StructuredHeadToHeadOutputPaths(
        config=paths.structured_config,
        targets=paths.structured_targets,
        child_region_overrides=paths.child_region_overrides,
        structured_pulse_config_toml=paths.structured_pulse_config,
        child_candidate_config_toml=paths.child_candidate_config,
        baseline_posterior_predictive_report_md=(
            paths.baseline_posterior_predictive_report
        ),
        baseline_posterior_predictive_plot=paths.baseline_posterior_predictive_plot,
        structured_pulse_posterior_predictive_report_md=(
            paths.structured_pulse_posterior_predictive_report
        ),
        structured_pulse_posterior_predictive_plot=(
            paths.structured_pulse_posterior_predictive_plot
        ),
        child_posterior_predictive_report_md=paths.child_posterior_predictive_report,
        child_posterior_predictive_plot=paths.child_posterior_predictive_plot,
        head_to_head_report_md=paths.head_to_head_report,
        manifest_json=paths.head_to_head_manifest,
    )


@contextmanager
def _working_directory(path: Path) -> Iterator[None]:
    """Temporarily run a workflow with project-relative paths from one root."""
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)
