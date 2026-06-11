"""Tests for target observations and comparison helpers."""

from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest

from indoeuropop.models import PopulationState, SimulationResult
from indoeuropop.targets import (
    TARGET_COLUMNS,
    TargetDataset,
    TargetObservation,
    load_target_dataset,
    target_dataset_to_csv,
    target_observation_rows,
    write_target_dataset_csv,
)


def test_target_observation_bounds_and_dataset_filters() -> None:
    """Target observations should expose bounds and filterable metadata."""
    observation = TargetObservation(
        status="published",
        region="britain",
        source="steppe",
        time_bce=2500,
        mean=0.95,
        uncertainty=0.10,
        citation_key="example",
        citation="Example citation",
    )
    dataset = TargetDataset.from_rows([observation])

    assert observation.lower_bound == 0.85
    assert observation.upper_bound == 1.0
    assert dataset.require_observations() == dataset
    assert dataset.regions() == ("britain",)
    assert dataset.sources() == ("steppe",)
    assert dataset.filter(region="britain").observations == (observation,)
    assert dataset.filter(source="steppe").observations == (observation,)
    assert dataset.filter(status="published").observations == (observation,)
    assert dataset.filter(region="iberia").observations == ()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": "draft"},
        {"region": ""},
        {"source": ""},
        {"time_bce": float("inf")},
        {"mean": -0.1},
        {"mean": 1.1},
        {"uncertainty": 0.0},
        {"uncertainty": 1.1},
        {"citation_key": ""},
        {"citation": ""},
    ],
)
def test_target_observation_rejects_invalid_fields(kwargs: dict[str, object]) -> None:
    """Target validation should reject malformed scientific metadata."""
    valid_kwargs: dict[str, object] = {
        "status": "synthetic",
        "region": "britain",
        "source": "steppe",
        "time_bce": 2500,
        "mean": 0.5,
        "uncertainty": 0.1,
        "citation_key": "example",
        "citation": "Example citation",
    }
    valid_kwargs.update(kwargs)

    with pytest.raises(ValueError):
        TargetObservation(**cast(Any, valid_kwargs))


def test_target_dataset_requires_observations() -> None:
    """Empty target datasets should fail before inference use."""
    with pytest.raises(ValueError):
        TargetDataset(()).require_observations()


def test_compare_interpolates_simulation_ancestry() -> None:
    """Target comparison should linearly interpolate simulation ancestry."""
    result = SimulationResult(
        (3000, 2900),
        (
            PopulationState({"britain": {"local": 100, "steppe": 0}}),
            PopulationState({"britain": {"local": 50, "steppe": 50}}),
        ),
    )
    observation = TargetObservation(
        status="synthetic",
        region="britain",
        source="steppe",
        time_bce=2950,
        mean=0.2,
        uncertainty=0.1,
        citation_key="synthetic",
        citation="Synthetic example",
    )

    (comparison,) = TargetDataset.from_rows([observation]).compare(result)

    assert comparison.observation == observation
    assert comparison.predicted == 0.25
    assert comparison.residual == pytest.approx(0.05)
    assert comparison.z_score == pytest.approx(0.5)


def test_compare_rejects_out_of_range_targets() -> None:
    """Comparison should not extrapolate beyond simulated time ranges."""
    result = SimulationResult(
        (3000,),
        (PopulationState({"britain": {"local": 100, "steppe": 0}}),),
    )
    observation = TargetObservation(
        status="synthetic",
        region="britain",
        source="steppe",
        time_bce=2500,
        mean=0.2,
        uncertainty=0.1,
        citation_key="synthetic",
        citation="Synthetic example",
    )

    with pytest.raises(ValueError, match="outside"):
        TargetDataset.from_rows([observation]).compare(result)


def test_load_target_dataset_from_csv(tmp_path: Path) -> None:
    """CSV targets should load into typed observations."""
    target_path = tmp_path / "targets.csv"
    target_path.write_text(
        "\n".join(
            [
                "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note",
                'synthetic,britain,steppe,2500,0.3,0.1,key,"Synthetic citation",Note',
            ]
        ),
        encoding="utf-8",
    )

    dataset = load_target_dataset(target_path)
    observation = dataset.observations[0]

    assert observation.status == "synthetic"
    assert observation.region == "britain"
    assert observation.source == "steppe"
    assert observation.time_bce == 2500
    assert observation.mean == 0.3
    assert observation.uncertainty == 0.1
    assert observation.citation_key == "key"
    assert observation.citation == "Synthetic citation"
    assert observation.note == "Note"


def test_target_dataset_csv_exports_round_trip(tmp_path: Path) -> None:
    """Target datasets should write the same schema accepted by the loader."""
    observation = TargetObservation(
        status="published",
        region="britain",
        source="steppe",
        time_bce=2500,
        mean=0.3,
        uncertainty=0.1,
        citation_key="key",
        citation="Published citation",
        note="Curated row",
    )
    dataset = TargetDataset.from_rows([observation])
    output_path = tmp_path / "targets" / "published-targets.csv"

    rows = target_observation_rows(dataset)
    csv_text = target_dataset_to_csv(dataset)
    returned_path = write_target_dataset_csv(dataset, output_path)
    loaded = load_target_dataset(output_path)

    assert TARGET_COLUMNS[0] == "status"
    assert rows[0]["time_bce"] == "2500"
    assert csv_text.startswith("status,region,source,time_bce")
    assert returned_path == output_path
    assert loaded.observations == (observation,)


@pytest.mark.parametrize(
    "contents,match",
    [
        ("", "header"),
        ("status,region\n", "missing columns"),
        (
            "\n".join(
                [
                    "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note",
                    "synthetic,,steppe,2500,0.3,0.1,key,Citation,Note",
                ]
            ),
            "region is required",
        ),
        (
            "\n".join(
                [
                    "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note",
                    "draft,britain,steppe,2500,0.3,0.1,key,Citation,Note",
                ]
            ),
            "status must be",
        ),
        (
            "\n".join(
                [
                    "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note",
                    "synthetic,britain,steppe,not-a-year,0.3,0.1,key,Citation,Note",
                ]
            ),
            "invalid target CSV row 2",
        ),
        (
            "status,region,source,time_bce,mean,uncertainty,citation_key,citation,note\n",
            "at least one observation",
        ),
    ],
)
def test_load_target_dataset_rejects_bad_csv(
    tmp_path: Path, contents: str, match: str
) -> None:
    """CSV loading should report malformed files clearly."""
    target_path = tmp_path / "bad-targets.csv"
    target_path.write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError, match=match):
        load_target_dataset(target_path)


def test_example_target_file_loads() -> None:
    """The checked-in synthetic example should follow the target schema."""
    dataset = load_target_dataset("examples/target-observations.example.csv")

    assert dataset.regions() == ("britain",)
    assert dataset.sources() == ("steppe",)
    assert all(
        observation.status == "synthetic" for observation in dataset.observations
    )
    np.testing.assert_allclose(
        [observation.mean for observation in dataset.observations],
        [0.05, 0.15, 0.30],
    )
