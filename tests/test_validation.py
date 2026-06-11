"""Tests for validation-split helpers."""

from typing import cast

import pytest

from indoeuropop.analysis.fitting import score_result_against_targets
from indoeuropop.analysis.summary import TrajectorySummary
from indoeuropop.analysis.validation import (
    TargetSplit,
    ValidatedSweepRun,
    ValidationFit,
    ValidationSplitName,
    rank_validated_runs,
    run_validated_parameter_sweep,
    score_result_on_split,
    split_targets_by_region,
)
from indoeuropop.data.targets import TargetDataset, TargetObservation
from indoeuropop.models import PopulationState, SimulationParameters, SimulationResult
from indoeuropop.orchestration.sweeps import ParameterRange, SweepRun, SweepSpec


def _target(region: str, mean: float, uncertainty: float = 0.1) -> TargetObservation:
    """Build one synthetic target observation for validation tests."""
    return TargetObservation(
        status="synthetic",
        region=region,
        source="steppe",
        time_bce=2900,
        mean=mean,
        uncertainty=uncertainty,
        citation_key="synthetic",
        citation="Synthetic validation target",
    )


def _targets() -> TargetDataset:
    """Return a small two-region target dataset."""
    return TargetDataset.from_rows(
        [
            _target("britain", 0.2),
            _target("iberia", 0.3),
            _target("gaul", 0.1),
        ]
    )


def _result(
    *, britain_steppe: float, iberia_steppe: float, gaul_steppe: float
) -> SimulationResult:
    """Build a two-point simulation result with regional steppe proportions."""
    return SimulationResult(
        (3000, 2900),
        (
            PopulationState(
                {
                    "britain": {"local": 100, "steppe": 0},
                    "iberia": {"local": 100, "steppe": 0},
                    "gaul": {"local": 100, "steppe": 0},
                }
            ),
            PopulationState(
                {
                    "britain": {
                        "local": 100 - britain_steppe,
                        "steppe": britain_steppe,
                    },
                    "iberia": {
                        "local": 100 - iberia_steppe,
                        "steppe": iberia_steppe,
                    },
                    "gaul": {"local": 100 - gaul_steppe, "steppe": gaul_steppe},
                }
            ),
        ),
    )


def _summary_for_index(index: int) -> TrajectorySummary:
    """Return a minimal trajectory summary for a synthetic validated run."""
    return TrajectorySummary(
        source="steppe",
        region="britain",
        start_bce=3000,
        end_bce=2900,
        initial_ancestry=0.0,
        final_ancestry=float(index) / 100,
        ancestry_delta=float(index) / 100,
        ancestry_slope_per_century=float(index) / 100,
        min_total_population=100.0,
        final_total_population=100.0,
        is_extinct=False,
    )


def _validated_run(
    index: int, calibration_mean: float, validation_mean: float
) -> ValidatedSweepRun:
    """Build a synthetic validated run with controllable split fit values."""
    calibration_targets = TargetDataset.from_rows(
        [_target("britain", calibration_mean)]
    )
    validation_targets = TargetDataset.from_rows([_target("iberia", validation_mean)])
    result = _result(britain_steppe=20, iberia_steppe=30, gaul_steppe=10)
    run = SweepRun(
        index=index,
        sampled_values={"migration_rate": float(index)},
        parameters=SimulationParameters(),
        summary=_summary_for_index(index),
    )
    return ValidatedSweepRun(
        run=run,
        fit=ValidationFit(
            calibration=score_result_against_targets(result, calibration_targets),
            validation=score_result_against_targets(result, validation_targets),
        ),
    )


def test_split_targets_by_region_partitions_holdout_regions() -> None:
    """Validation-region splits should preserve target rows in order."""
    split = split_targets_by_region(_targets(), validation_regions=("iberia",))

    assert tuple(target.region for target in split.calibration.observations) == (
        "britain",
        "gaul",
    )
    assert tuple(target.region for target in split.validation.observations) == (
        "iberia",
    )


@pytest.mark.parametrize(
    "validation_regions",
    [
        (),
        ("unknown",),
        ("britain", "iberia", "gaul"),
    ],
)
def test_split_targets_by_region_rejects_empty_split_halves(
    validation_regions: tuple[str, ...],
) -> None:
    """Validation splits should require non-empty calibration and holdout sets."""
    with pytest.raises(ValueError):
        split_targets_by_region(_targets(), validation_regions)


def test_target_split_rejects_empty_datasets() -> None:
    """TargetSplit should reject empty calibration or validation datasets."""
    non_empty = TargetDataset.from_rows([_target("britain", 0.2)])
    empty = TargetDataset.from_rows([])

    with pytest.raises(ValueError):
        TargetSplit(calibration=empty, validation=non_empty)
    with pytest.raises(ValueError):
        TargetSplit(calibration=non_empty, validation=empty)


def test_score_result_on_split_returns_calibration_and_validation_fit() -> None:
    """A simulation result should be scored against both target split halves."""
    split = split_targets_by_region(_targets(), validation_regions=("iberia",))

    fit = score_result_on_split(
        _result(britain_steppe=20, iberia_steppe=40, gaul_steppe=20),
        split,
    )

    assert fit.calibration.observation_count == 2
    assert fit.validation.observation_count == 1
    assert fit.metric_value("chi_square", "calibration") == pytest.approx(1)
    assert fit.metric_value("chi_square", "validation") == pytest.approx(1)
    assert fit.generalization_gap("chi_square") == pytest.approx(0)


def test_validation_fit_rejects_unknown_metric_and_split() -> None:
    """Validation fit helpers should reject unsupported selectors."""
    split = split_targets_by_region(_targets(), validation_regions=("iberia",))
    fit = score_result_on_split(
        _result(britain_steppe=20, iberia_steppe=30, gaul_steppe=10),
        split,
    )

    with pytest.raises(ValueError, match="unsupported fit metric"):
        fit.metric_value("unknown", "calibration")
    with pytest.raises(ValueError, match="unsupported fit metric"):
        fit.generalization_gap("unknown")
    with pytest.raises(ValueError, match="unsupported validation split"):
        fit.metric_value("chi_square", cast(ValidationSplitName, "unknown"))


def test_rank_validated_runs_sorts_by_requested_split_metric() -> None:
    """Validated runs should sort by calibration or validation fit."""
    run_one = _validated_run(index=1, calibration_mean=0.0, validation_mean=0.3)
    run_two = _validated_run(index=2, calibration_mean=0.2, validation_mean=0.0)

    ranked_by_calibration = rank_validated_runs((run_one, run_two))
    ranked_by_validation = rank_validated_runs((run_one, run_two), split="validation")

    assert tuple(run.run.index for run in ranked_by_calibration) == (2, 1)
    assert tuple(run.run.index for run in ranked_by_validation) == (1, 2)
    assert run_two.metric_value("chi_square", "calibration") == 0
    assert run_two.generalization_gap("chi_square") > 0


def test_rank_validated_runs_rejects_unknown_metric_and_split() -> None:
    """Validated run ranking should fail clearly for unsupported selectors."""
    run = _validated_run(index=1, calibration_mean=0.2, validation_mean=0.3)

    with pytest.raises(ValueError, match="unsupported fit metric"):
        rank_validated_runs((run,), metric="unknown")
    with pytest.raises(ValueError, match="unsupported validation split"):
        rank_validated_runs((run,), split=cast(ValidationSplitName, "unknown"))


def test_run_validated_parameter_sweep_scores_calibration_and_validation() -> None:
    """Validated sweeps should rank by calibration fit and keep holdout fit."""
    target_split = split_targets_by_region(
        TargetDataset.from_rows([_target("britain", 0.2), _target("iberia", 0.2)]),
        validation_regions=("iberia",),
    )

    validated_runs = run_validated_parameter_sweep(
        SweepSpec(
            initial_state=PopulationState(
                {
                    "britain": {"local": 1000, "steppe": 0},
                    "iberia": {"local": 1000, "steppe": 0},
                }
            ),
            base_parameters=SimulationParameters(
                fertility_rate=0,
                local_mortality_rate=0,
                steppe_mortality_rate=0,
            ),
            parameter_ranges=(ParameterRange("migration_rate", 0.001, 0.003),),
            start_bce=3000,
            end_bce=2900,
            step_years=100,
            sample_count=4,
            seed=3,
            region="britain",
        ),
        target_split,
    )

    assert len(validated_runs) == 4
    assert validated_runs[0].metric_value(
        "chi_square", "calibration"
    ) <= validated_runs[-1].metric_value("chi_square", "calibration")
    assert validated_runs[0].fit.calibration.observation_count == 1
    assert validated_runs[0].fit.validation.observation_count == 1


def test_run_validated_parameter_sweep_rejects_unknown_metric() -> None:
    """Validated sweep execution should validate ranking metric names."""
    target_split = split_targets_by_region(_targets(), validation_regions=("iberia",))

    with pytest.raises(ValueError, match="unsupported fit metric"):
        run_validated_parameter_sweep(
            SweepSpec(
                initial_state=PopulationState({"britain": {"local": 100, "steppe": 0}}),
                base_parameters=SimulationParameters(),
                parameter_ranges=(ParameterRange("migration_rate", 0.0, 0.0),),
            ),
            target_split,
            metric="unknown",
        )
