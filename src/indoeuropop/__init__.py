"""Tools for scaffolded Indo-European population dynamics experiments."""

from indoeuropop.age_structure import (
    ADULT,
    ELDER,
    JUVENILE,
    AgeStructuredState,
    AgeStructureParameters,
    advance_age_structure,
)
from indoeuropop.config import SimulationConfig, default_config, load_config
from indoeuropop.data_sources import (
    DataSourceCatalog,
    DataSourceRecord,
    load_data_source_catalog,
    sha256_file,
    verify_record_checksum,
)
from indoeuropop.debugging import (
    AncestryComparison,
    compare_ancestry_trajectories,
    compare_deterministic_and_tau_leap,
)
from indoeuropop.diagnostics import (
    DiagnosticIssue,
    has_errors,
    validate_simulation_result,
)
from indoeuropop.events import (
    ForcingWindow,
    MigrationPulse,
    SimulationSchedule,
    TimeWindow,
)
from indoeuropop.fitting import (
    ScoredSweepRun,
    TargetFit,
    rank_scored_runs,
    run_scored_parameter_sweep,
    score_result_against_targets,
    score_target_fit,
)
from indoeuropop.models import PopulationState, SimulationParameters, SimulationResult
from indoeuropop.parameterization import (
    ParameterSet,
    RegionParameters,
    ResolvedSourceParameters,
    SourceParameters,
)
from indoeuropop.provenance import (
    ProvenanceRecord,
    summary_provenance_records,
    target_fit_provenance_records,
    target_observation_provenance_records,
)
from indoeuropop.reporting import (
    diagnostic_issue_records,
    provenance_fieldnames,
    provenance_records_to_csv,
    provenance_rows,
    write_provenance_csv,
)
from indoeuropop.sample_metadata import (
    RegionSampleCount,
    SampleMetadataDataset,
    SampleMetadataRecord,
    load_sample_metadata,
)
from indoeuropop.sensitivity import SensitivityResult, analyze_sensitivity
from indoeuropop.sex_bias import (
    FEMALE,
    MALE,
    SEXES,
    SexBiasParameters,
    SexStructuredState,
    expected_births_by_source,
)
from indoeuropop.simulation import run_deterministic, run_tau_leap
from indoeuropop.summary import TrajectorySummary, summarize_trajectory
from indoeuropop.sweeps import (
    ParameterRange,
    SweepRun,
    SweepSpec,
    latin_hypercube_samples,
    parameters_with_overrides,
    run_parameter_sweep,
)
from indoeuropop.target_curation import (
    TargetCurationDataset,
    TargetCurationRecord,
    load_target_curation,
)
from indoeuropop.targets import (
    TargetComparison,
    TargetDataset,
    TargetObservation,
    load_target_dataset,
)
from indoeuropop.visualization import (
    plot_ancestry,
    plot_ancestry_comparison,
    plot_population_total,
)

__all__ = [
    "ADULT",
    "ELDER",
    "FEMALE",
    "JUVENILE",
    "MALE",
    "SEXES",
    "AgeStructureParameters",
    "AgeStructuredState",
    "AncestryComparison",
    "DataSourceCatalog",
    "DataSourceRecord",
    "DiagnosticIssue",
    "ForcingWindow",
    "MigrationPulse",
    "ParameterRange",
    "ParameterSet",
    "PopulationState",
    "ProvenanceRecord",
    "RegionParameters",
    "RegionSampleCount",
    "ResolvedSourceParameters",
    "SampleMetadataDataset",
    "SampleMetadataRecord",
    "ScoredSweepRun",
    "SensitivityResult",
    "SexBiasParameters",
    "SexStructuredState",
    "SimulationConfig",
    "SimulationParameters",
    "SimulationResult",
    "SimulationSchedule",
    "SourceParameters",
    "SweepRun",
    "SweepSpec",
    "TargetComparison",
    "TargetCurationDataset",
    "TargetCurationRecord",
    "TargetDataset",
    "TargetFit",
    "TargetObservation",
    "TimeWindow",
    "TrajectorySummary",
    "advance_age_structure",
    "analyze_sensitivity",
    "compare_ancestry_trajectories",
    "compare_deterministic_and_tau_leap",
    "default_config",
    "diagnostic_issue_records",
    "expected_births_by_source",
    "has_errors",
    "latin_hypercube_samples",
    "load_config",
    "load_data_source_catalog",
    "load_sample_metadata",
    "load_target_curation",
    "load_target_dataset",
    "parameters_with_overrides",
    "plot_ancestry",
    "plot_ancestry_comparison",
    "plot_population_total",
    "provenance_fieldnames",
    "provenance_records_to_csv",
    "provenance_rows",
    "rank_scored_runs",
    "run_deterministic",
    "run_parameter_sweep",
    "run_scored_parameter_sweep",
    "run_tau_leap",
    "score_result_against_targets",
    "score_target_fit",
    "sha256_file",
    "summarize_trajectory",
    "summary_provenance_records",
    "target_fit_provenance_records",
    "target_observation_provenance_records",
    "validate_simulation_result",
    "verify_record_checksum",
    "write_provenance_csv",
]
