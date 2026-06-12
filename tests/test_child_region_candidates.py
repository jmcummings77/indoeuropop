"""Tests for child-region structural candidate analysis helpers."""

from __future__ import annotations

import pytest

from indoeuropop.analysis.child_region_candidates import (
    ChildRegionCandidate,
    StructuralComparisonReference,
    root_mean_squared_error_advantage,
)


def test_child_region_candidate_normalizes_and_validates_fields() -> None:
    """Child-region candidates should normalize labels and reject bad counts."""
    candidate = ChildRegionCandidate(
        name="  interaction best  ",
        override_path="  curation/overrides.toml  ",
        overridden_region_count=2,
        migration_pulse_count=1,
    )

    assert candidate.name == "interaction best"
    assert candidate.override_path == "curation/overrides.toml"

    with pytest.raises(ValueError, match="name"):
        ChildRegionCandidate(name="")
    with pytest.raises(ValueError, match="overridden_region_count"):
        ChildRegionCandidate(name="candidate", overridden_region_count=-1)
    with pytest.raises(ValueError, match="migration_pulse_count"):
        ChildRegionCandidate(name="candidate", migration_pulse_count=-1)


def test_structural_reference_validates_and_compares_rmse_advantage() -> None:
    """Reference comparisons should expose child-minus-reference RMSE deltas."""
    reference = StructuralComparisonReference(
        name=" broad pulse ",
        root_mean_squared_error_delta=-0.02,
        coverage_rate_delta=-0.1,
        focus_residual_delta=-0.03,
    )

    assert reference.name == "broad pulse"
    assert root_mean_squared_error_advantage(-0.05, reference) == pytest.approx(-0.03)

    with pytest.raises(ValueError, match="name"):
        StructuralComparisonReference("", 0.0, 0.0, 0.0)
    with pytest.raises(ValueError, match="finite"):
        StructuralComparisonReference("reference", float("nan"), 0.0, 0.0)
    with pytest.raises(ValueError, match="candidate_delta"):
        root_mean_squared_error_advantage(float("inf"), reference)
