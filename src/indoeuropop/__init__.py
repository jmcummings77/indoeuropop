"""Tools for scaffolded Indo-European population dynamics experiments."""

from indoeuropop.config import SimulationConfig, default_config, load_config
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
from indoeuropop.sensitivity import SensitivityResult, analyze_sensitivity
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
    "AncestryComparison",
    "DiagnosticIssue",
    "ForcingWindow",
    "MigrationPulse",
    "ParameterRange",
    "ParameterSet",
    "PopulationState",
    "RegionParameters",
    "ResolvedSourceParameters",
    "ScoredSweepRun",
    "SensitivityResult",
    "SimulationConfig",
    "SimulationParameters",
    "SimulationResult",
    "SimulationSchedule",
    "SourceParameters",
    "SweepRun",
    "SweepSpec",
    "TargetComparison",
    "TargetDataset",
    "TargetFit",
    "TargetObservation",
    "TimeWindow",
    "TrajectorySummary",
    "analyze_sensitivity",
    "compare_ancestry_trajectories",
    "compare_deterministic_and_tau_leap",
    "default_config",
    "has_errors",
    "latin_hypercube_samples",
    "load_config",
    "load_target_dataset",
    "parameters_with_overrides",
    "plot_ancestry",
    "plot_ancestry_comparison",
    "plot_population_total",
    "rank_scored_runs",
    "run_deterministic",
    "run_parameter_sweep",
    "run_scored_parameter_sweep",
    "run_tau_leap",
    "score_result_against_targets",
    "score_target_fit",
    "summarize_trajectory",
    "validate_simulation_result",
]
