"""Tests for output provenance records."""

from typing import cast

import pytest

from indoeuropop.analysis.fitting import score_result_against_targets
from indoeuropop.analysis.summary import summarize_trajectory
from indoeuropop.data.targets import TargetDataset, TargetObservation
from indoeuropop.models import PopulationState, SimulationResult
from indoeuropop.reporting.provenance import (
    ProvenanceRecord,
    RecordKind,
    summary_provenance_records,
    target_fit_provenance_records,
    target_observation_provenance_records,
)


def _published_target() -> TargetObservation:
    """Return one published target observation for provenance tests."""
    return TargetObservation(
        status="published",
        region="britain",
        source="steppe",
        time_bce=2900,
        mean=0.25,
        uncertainty=0.05,
        citation_key="example",
        citation="Example citation",
    )


def _result() -> SimulationResult:
    """Return a tiny trajectory for provenance tests."""
    return SimulationResult(
        (3000, 2900),
        (
            PopulationState({"britain": {"local": 100, "steppe": 0}}),
            PopulationState({"britain": {"local": 80, "steppe": 20}}),
        ),
    )


def test_provenance_record_flattens_metadata() -> None:
    """Records should serialize to stable string-only rows."""
    record = ProvenanceRecord(
        name="final_ancestry",
        kind="simulated",
        value=0.25,
        unit="proportion",
        metadata={"region": "britain"},
    )

    assert record.to_flat_row() == {
        "kind": "simulated",
        "name": "final_ancestry",
        "value": "0.25",
        "unit": "proportion",
        "metadata_region": "britain",
    }

    note_record = ProvenanceRecord(name="note", kind="derived", value="ready")
    assert note_record.to_flat_row()["value"] == "ready"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": ""},
        {"kind": cast(RecordKind, "unsupported")},
        {"value": float("nan")},
        {"value": ""},
        {"metadata": {"": "blank"}},
    ],
)
def test_provenance_record_rejects_invalid_fields(
    kwargs: dict[str, object],
) -> None:
    """Invalid provenance records should fail before reaching reports."""
    base = {
        "name": "metric",
        "kind": "derived",
        "value": 1.0,
        "unit": "score",
        "metadata": {"region": "britain"},
    }
    base.update(kwargs)

    with pytest.raises(ValueError):
        ProvenanceRecord(**base)  # type: ignore[arg-type]


def test_summary_provenance_records_mark_simulated_values() -> None:
    """Trajectory summaries should become simulated provenance records."""
    records = summary_provenance_records(
        summarize_trajectory(_result(), source="steppe", region="britain")
    )
    names = {record.name for record in records}

    assert names == {
        "initial_ancestry",
        "final_ancestry",
        "ancestry_delta",
        "ancestry_slope_per_century",
        "min_total_population",
        "final_total_population",
        "is_extinct",
    }
    assert {record.kind for record in records} == {"simulated"}
    assert records[-1].to_flat_row()["value"] == "false"


def test_target_observation_records_preserve_observation_status() -> None:
    """Target provenance should distinguish published and synthetic targets."""
    published_records = target_observation_provenance_records(_published_target())
    synthetic_records = target_observation_provenance_records(
        TargetObservation(
            status="synthetic",
            region="britain",
            source="steppe",
            time_bce=2900,
            mean=0.25,
            uncertainty=0.05,
            citation_key="synthetic",
            citation="Synthetic target",
        )
    )

    assert {record.kind for record in published_records} == {"observed"}
    assert {record.kind for record in synthetic_records} == {"synthetic"}
    assert published_records[0].metadata["status"] == "published"


def test_target_fit_records_mark_derived_values() -> None:
    """Target-fit metrics should be labeled as derived, not inferred."""
    fit = score_result_against_targets(
        _result(),
        TargetDataset.from_rows([_published_target()]),
    )

    records = target_fit_provenance_records(fit)

    assert {record.kind for record in records} == {"derived"}
    assert {record.metadata["observation_count"] for record in records} == {"1"}
    assert {record.name for record in records} == {
        "mean_absolute_error",
        "root_mean_squared_error",
        "chi_square",
        "reduced_chi_square",
        "max_abs_z_score",
    }
