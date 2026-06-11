"""Public analysis exports for top-level package imports."""

from indoeuropop.analysis.debugging import (
    AncestryComparison,
    compare_ancestry_trajectories,
    compare_deterministic_and_tau_leap,
)
from indoeuropop.analysis.diagnostics import (
    DiagnosticIssue,
    has_errors,
    validate_simulation_result,
)
from indoeuropop.analysis.emulator_training import (
    EmulatorTrainingDataset,
    EmulatorTrainingRow,
    emulator_training_dataset_from_sweep_runs,
)
from indoeuropop.analysis.emulator_validation import (
    EmulatorPrediction,
    EmulatorValidationCase,
    EmulatorValidationReport,
    validate_emulator_predictions,
)
from indoeuropop.analysis.fitting import (
    ScoredSweepRun,
    TargetFit,
    rank_scored_runs,
    run_scored_parameter_sweep,
    score_result_against_targets,
    score_target_fit,
)
from indoeuropop.analysis.sensitivity import SensitivityResult, analyze_sensitivity
from indoeuropop.analysis.summary import TrajectorySummary, summarize_trajectory
from indoeuropop.analysis.summary_statistics import (
    SummaryStatistic,
    SummaryVector,
    trajectory_summary_vector,
)
from indoeuropop.analysis.validation import (
    TargetSplit,
    ValidatedSweepRun,
    ValidationFit,
    rank_validated_runs,
    run_validated_parameter_sweep,
    score_result_on_split,
    split_targets_by_region,
)

__all__ = [
    "AncestryComparison",
    "DiagnosticIssue",
    "EmulatorPrediction",
    "EmulatorTrainingDataset",
    "EmulatorTrainingRow",
    "EmulatorValidationCase",
    "EmulatorValidationReport",
    "ScoredSweepRun",
    "SensitivityResult",
    "SummaryStatistic",
    "SummaryVector",
    "TargetFit",
    "TargetSplit",
    "TrajectorySummary",
    "ValidatedSweepRun",
    "ValidationFit",
    "analyze_sensitivity",
    "compare_ancestry_trajectories",
    "compare_deterministic_and_tau_leap",
    "emulator_training_dataset_from_sweep_runs",
    "has_errors",
    "rank_scored_runs",
    "rank_validated_runs",
    "run_scored_parameter_sweep",
    "run_validated_parameter_sweep",
    "score_result_against_targets",
    "score_result_on_split",
    "score_target_fit",
    "split_targets_by_region",
    "summarize_trajectory",
    "trajectory_summary_vector",
    "validate_emulator_predictions",
    "validate_simulation_result",
]
