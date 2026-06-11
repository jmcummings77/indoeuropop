"""Reproducible workflows for building real AADR-derived target observations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from indoeuropop.data.aadr import DEFAULT_AADR_DATASET_ID
from indoeuropop.data.aadr_curation import (
    DEFAULT_AADR_AGGREGATION_METHOD,
    AADRGroupMatchMode,
    AADRTargetInputOptions,
    load_aadr_group_selections,
    prepare_aadr_target_inputs,
    write_aadr_target_inputs,
)
from indoeuropop.data.ancestry_estimates import write_sample_ancestry_estimates_csv
from indoeuropop.data.qpadm_estimates import (
    DEFAULT_QPADM_METHOD,
    DEFAULT_QPADM_SOURCE,
    load_qpadm_estimate_table,
    qpadm_estimates_to_sample_ancestry_dataset,
)
from indoeuropop.data.target_pipeline import (
    build_target_dataset,
    filter_target_inputs_for_estimates,
)
from indoeuropop.data.targets import TargetDataset, write_target_dataset_csv


@dataclass(frozen=True)
class AADRQpAdmTargetWorkflowConfig:
    """Input and output paths for an AADR plus qpAdm target build.

    The workflow assumes AADR metadata and EIGENSTRAT files are already present
    locally. It does not download source data or execute ADMIXTOOLS. Instead, it
    connects reviewed AADR group selections with an externally produced qpAdm
    estimate table, then emits versionable CSV outputs and diagnostics.
    """

    aadr_dir: Path
    aadr_groups_path: Path
    qpadm_estimates_path: Path
    sample_metadata_path: Path
    target_curation_path: Path
    ancestry_estimates_path: Path
    target_output_path: Path
    diagnostics_json_path: Path | None = None
    dataset_id: str = DEFAULT_AADR_DATASET_ID
    source: str = DEFAULT_QPADM_SOURCE
    qpadm_method: str = DEFAULT_QPADM_METHOD
    aggregation_method: str = DEFAULT_AADR_AGGREGATION_METHOD
    group_match_mode: AADRGroupMatchMode = "exact"
    allow_missing_groups: bool = False
    default_standard_error: float | None = None
    skip_missing_standard_error: bool = True


@dataclass(frozen=True)
class AADRQpAdmTargetDiagnostics:
    """Review counts from one real target-data build."""

    requested_target_count: int
    selected_sample_count: int
    raw_qpadm_row_count: int
    parsed_qpadm_estimate_count: int
    retained_sample_estimate_count: int
    retained_sample_count: int
    retained_target_count: int
    dropped_target_count: int
    target_observation_count: int
    dropped_target_ids: tuple[str, ...]
    target_counts_by_region: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class AADRQpAdmTargetWorkflowResult:
    """Outputs returned by an AADR plus qpAdm target build."""

    target_dataset: TargetDataset
    diagnostics: AADRQpAdmTargetDiagnostics


def run_aadr_qpadm_target_workflow(
    config: AADRQpAdmTargetWorkflowConfig,
) -> AADRQpAdmTargetWorkflowResult:
    """Run the local AADR to target-observation workflow."""
    selections = load_aadr_group_selections(config.aadr_groups_path)
    inputs = prepare_aadr_target_inputs(
        config.aadr_dir,
        selections,
        options=AADRTargetInputOptions(
            dataset_id=config.dataset_id,
            source=config.source,
            ancestry_method=config.qpadm_method,
            aggregation_method=config.aggregation_method,
            group_match_mode=config.group_match_mode,
            citation_key=config.dataset_id,
            allow_missing_groups=config.allow_missing_groups,
        ),
    )
    write_aadr_target_inputs(
        inputs,
        sample_metadata_path=config.sample_metadata_path,
        target_curation_path=config.target_curation_path,
    )
    qpadm_estimates = load_qpadm_estimate_table(config.qpadm_estimates_path)
    ancestry_estimates = qpadm_estimates_to_sample_ancestry_dataset(
        qpadm_estimates,
        source=config.source,
        method=config.qpadm_method,
        default_standard_error=config.default_standard_error,
        skip_missing_standard_error=config.skip_missing_standard_error,
    )
    write_sample_ancestry_estimates_csv(
        ancestry_estimates,
        config.ancestry_estimates_path,
    )
    filtered = filter_target_inputs_for_estimates(
        inputs.sample_metadata,
        inputs.curation,
        ancestry_estimates,
    )
    target_dataset = build_target_dataset(
        filtered.sample_metadata,
        filtered.curation,
        ancestry_estimates,
    )
    write_target_dataset_csv(target_dataset, config.target_output_path)
    diagnostics = AADRQpAdmTargetDiagnostics(
        requested_target_count=len(inputs.curation.records),
        selected_sample_count=inputs.sample_metadata.sample_count,
        raw_qpadm_row_count=qpadm_table_data_row_count(config.qpadm_estimates_path),
        parsed_qpadm_estimate_count=len(qpadm_estimates),
        retained_sample_estimate_count=ancestry_estimates.estimate_count,
        retained_sample_count=filtered.sample_metadata.sample_count,
        retained_target_count=len(filtered.curation.records),
        dropped_target_count=len(filtered.dropped_target_ids),
        target_observation_count=len(target_dataset.observations),
        dropped_target_ids=filtered.dropped_target_ids,
        target_counts_by_region=target_counts_by_region(target_dataset),
    )
    if config.diagnostics_json_path is not None:
        write_aadr_qpadm_target_diagnostics_json(
            diagnostics,
            config.diagnostics_json_path,
        )
    return AADRQpAdmTargetWorkflowResult(target_dataset, diagnostics)


def qpadm_table_data_row_count(path: str | Path) -> int:
    """Return the number of non-empty qpAdm data rows after the header."""
    lines = tuple(line for line in Path(path).read_text(encoding="utf-8").splitlines())
    non_empty_lines = tuple(line for line in lines if line.strip())
    return max(0, len(non_empty_lines) - 1)


def target_counts_by_region(dataset: TargetDataset) -> tuple[tuple[str, int], ...]:
    """Return target-observation counts grouped by region in first-seen order."""
    counts: dict[str, int] = {}
    for observation in dataset.observations:
        counts[observation.region] = counts.get(observation.region, 0) + 1
    return tuple(counts.items())


def aadr_qpadm_target_diagnostics_payload(
    diagnostics: AADRQpAdmTargetDiagnostics,
) -> dict[str, object]:
    """Return JSON-ready real target-build diagnostics."""
    return {
        "requested_target_count": diagnostics.requested_target_count,
        "selected_sample_count": diagnostics.selected_sample_count,
        "raw_qpadm_row_count": diagnostics.raw_qpadm_row_count,
        "parsed_qpadm_estimate_count": diagnostics.parsed_qpadm_estimate_count,
        "retained_sample_estimate_count": diagnostics.retained_sample_estimate_count,
        "retained_sample_count": diagnostics.retained_sample_count,
        "retained_target_count": diagnostics.retained_target_count,
        "dropped_target_count": diagnostics.dropped_target_count,
        "target_observation_count": diagnostics.target_observation_count,
        "dropped_target_ids": list(diagnostics.dropped_target_ids),
        "target_counts_by_region": dict(diagnostics.target_counts_by_region),
    }


def write_aadr_qpadm_target_diagnostics_json(
    diagnostics: AADRQpAdmTargetDiagnostics,
    path: str | Path,
) -> Path:
    """Write real target-build diagnostics as JSON and return the path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(aadr_qpadm_target_diagnostics_payload(diagnostics), indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path
