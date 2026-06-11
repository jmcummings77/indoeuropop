"""Tests for building target observations from curated sample estimates."""

import pytest

from indoeuropop.data.ancestry_estimates import (
    SampleAncestryEstimate,
    SampleAncestryEstimateDataset,
)
from indoeuropop.data.sample_metadata import SampleMetadataDataset, SampleMetadataRecord
from indoeuropop.data.target_curation import TargetCurationDataset, TargetCurationRecord
from indoeuropop.data.target_pipeline import (
    TargetBuildOptions,
    _mean,
    _target_uncertainty,
    build_target_dataset,
    filter_target_inputs_for_estimates,
    load_and_build_target_dataset,
)


def _sample(
    sample_id: str,
    *,
    region: str = "britain",
    status: str = "published",
    time_bce: float = 2900,
) -> SampleMetadataRecord:
    """Build one sample metadata record for target-pipeline tests."""
    return SampleMetadataRecord(
        status=status,  # type: ignore[arg-type]
        dataset_id="published-samples",
        sample_id=sample_id,
        accession_id=f"accession-{sample_id}",
        publication_key="published-source",
        publication="Published source",
        region=region,
        site="Example Site",
        time_bce=time_bce,
        date_uncertainty=50,
        sex="unknown",
        method="metadata_curation",
    )


def _estimate(
    sample_id: str,
    estimate: float,
    *,
    standard_error: float = 0.05,
    status: str = "published",
) -> SampleAncestryEstimate:
    """Build one sample ancestry estimate for target-pipeline tests."""
    return SampleAncestryEstimate(
        status=status,  # type: ignore[arg-type]
        sample_id=sample_id,
        source="steppe",
        estimate=estimate,
        standard_error=standard_error,
        method="qpadm_like",
    )


def _curation(
    *,
    target_id: str = "britain-steppe-3000-2800",
    aggregation_method: str = "mean",
    sample_ids: tuple[str, ...] = ("I001", "I002"),
    status: str = "published",
    start_bce: float = 3000,
    end_bce: float = 2800,
) -> TargetCurationRecord:
    """Build one target curation record for target-pipeline tests."""
    return TargetCurationRecord(
        status=status,  # type: ignore[arg-type]
        target_id=target_id,
        region="britain",
        source="steppe",
        start_bce=start_bce,
        end_bce=end_bce,
        sample_ids=sample_ids,
        sample_count=len(sample_ids),
        ancestry_method="qpadm_like",
        aggregation_method=aggregation_method,
        citation_key="published-source",
        citation="Published source",
        note="Curated published target",
    )


def _metadata_dataset(
    *records: SampleMetadataRecord,
) -> SampleMetadataDataset:
    """Return sample metadata for target-pipeline tests."""
    return SampleMetadataDataset.from_rows(
        records or (_sample("I001"), _sample("I002"))
    )


def _estimate_dataset(
    *estimates: SampleAncestryEstimate,
) -> SampleAncestryEstimateDataset:
    """Return sample ancestry estimates for target-pipeline tests."""
    return SampleAncestryEstimateDataset.from_rows(
        estimates or (_estimate("I001", 0.1), _estimate("I002", 0.3))
    )


def _curation_dataset(record: TargetCurationRecord) -> TargetCurationDataset:
    """Return a one-row curation dataset."""
    return TargetCurationDataset.from_rows((record,))


def test_build_target_dataset_aggregates_unweighted_mean() -> None:
    """The target pipeline should aggregate curated sample estimates."""
    dataset = build_target_dataset(
        _metadata_dataset(),
        _curation_dataset(_curation()),
        _estimate_dataset(),
    )
    observation = dataset.observations[0]

    assert observation.status == "published"
    assert observation.region == "britain"
    assert observation.source == "steppe"
    assert observation.time_bce == 2900
    assert observation.mean == pytest.approx(0.2)
    assert observation.uncertainty == pytest.approx(0.07905694150420949)
    assert observation.citation_key == "published-source"
    assert "target_id=britain-steppe-3000-2800" in observation.note
    assert "sample_count=2" in observation.note


def test_build_target_dataset_supports_precision_weighted_mean() -> None:
    """Precision-weighted aggregation should favor lower-uncertainty estimates."""
    dataset = build_target_dataset(
        _metadata_dataset(),
        _curation_dataset(_curation(aggregation_method="precision_weighted_mean")),
        _estimate_dataset(
            _estimate("I001", 0.1, standard_error=0.01),
            _estimate("I002", 0.3, standard_error=0.1),
        ),
    )

    assert dataset.observations[0].mean == pytest.approx(0.10198019801980199)


def test_build_target_dataset_applies_uncertainty_floor() -> None:
    """Documented uncertainty floors should be applied after propagation."""
    dataset = build_target_dataset(
        _metadata_dataset(_sample("I001")),
        _curation_dataset(_curation(sample_ids=("I001",))),
        _estimate_dataset(_estimate("I001", 0.1, standard_error=0.01)),
        options=TargetBuildOptions(minimum_uncertainty=0.05),
    )

    assert dataset.observations[0].uncertainty == 0.05


def test_build_target_dataset_writes_generated_note_without_curation_note() -> None:
    """Generated target notes should work without source-row notes."""
    curation = TargetCurationRecord(
        status="published",
        target_id="target-without-note",
        region="britain",
        source="steppe",
        start_bce=3000,
        end_bce=2800,
        sample_ids=("I001",),
        sample_count=1,
        ancestry_method="qpadm_like",
        aggregation_method="mean",
        citation_key="published-source",
        citation="Published source",
    )

    dataset = build_target_dataset(
        _metadata_dataset(_sample("I001")),
        _curation_dataset(curation),
        _estimate_dataset(_estimate("I001", 0.1)),
    )

    assert dataset.observations[0].note.startswith("target_id=target-without-note")


def test_load_and_build_target_dataset_from_files() -> None:
    """Checked-in example inputs should build a loadable target dataset."""
    dataset = load_and_build_target_dataset(
        sample_metadata_path="examples/sample-metadata.example.csv",
        curation_path="examples/target-curation.example.csv",
        estimates_path="examples/sample-ancestry-estimates.example.csv",
    )

    assert len(dataset.observations) == 1
    assert dataset.observations[0].status == "synthetic"
    assert dataset.observations[0].mean == 0.08


def test_filter_target_inputs_for_estimates_drops_incomplete_targets() -> None:
    """Target-input filtering should keep only complete target rows."""
    curation = TargetCurationDataset.from_rows(
        (
            _curation(sample_ids=("I001",), start_bce=3000, end_bce=2800),
            _curation(
                target_id="britain-steppe-missing",
                sample_ids=("I002",),
                start_bce=3000,
                end_bce=2800,
            ),
        )
    )
    result = filter_target_inputs_for_estimates(
        _metadata_dataset(_sample("I001"), _sample("I002")),
        curation,
        _estimate_dataset(_estimate("I001", 0.1)),
    )

    assert tuple(record.sample_id for record in result.sample_metadata.records) == (
        "I001",
    )
    assert result.curation.target_ids() == ("britain-steppe-3000-2800",)
    assert result.dropped_target_ids == ("britain-steppe-missing",)


def test_target_build_options_reject_invalid_uncertainty_floor() -> None:
    """Target-build options should reject invalid uncertainty floors."""
    with pytest.raises(ValueError, match="minimum_uncertainty"):
        TargetBuildOptions(minimum_uncertainty=-0.1)


def test_target_uncertainty_rejects_invalid_propagated_value() -> None:
    """Internal uncertainty validation should reject impossible weights."""
    with pytest.raises(ValueError, match="uncertainty"):
        _target_uncertainty(
            (0.0,),
            (_estimate("I001", 0.1),),
            0.1,
            TargetBuildOptions(),
        )


def test_mean_rejects_empty_collection() -> None:
    """Internal mean helper should reject empty inputs."""
    with pytest.raises(ValueError, match="empty"):
        _mean(())


def test_build_target_dataset_rejects_ambiguous_sample_metadata() -> None:
    """Curation sample IDs must resolve to exactly one metadata row."""
    metadata = SampleMetadataDataset.from_rows(
        (
            _sample("I001"),
            SampleMetadataRecord(
                status="published",
                dataset_id="other-dataset",
                sample_id="I001",
                accession_id="other-accession",
                publication_key="other",
                publication="Other publication",
                region="britain",
                site="Example Site",
                time_bce=2900,
                date_uncertainty=50,
                sex="unknown",
                method="metadata_curation",
            ),
        )
    )

    with pytest.raises(ValueError, match="ambiguous"):
        build_target_dataset(
            metadata,
            _curation_dataset(_curation(sample_ids=("I001",))),
            _estimate_dataset(_estimate("I001", 0.1)),
        )


@pytest.mark.parametrize(
    "metadata,curation,estimates,match",
    [
        (
            _metadata_dataset(_sample("I002")),
            _curation(sample_ids=("I001",)),
            _estimate_dataset(_estimate("I001", 0.1)),
            "missing sample_id",
        ),
        (
            _metadata_dataset(_sample("I001", status="synthetic")),
            _curation(sample_ids=("I001",)),
            _estimate_dataset(_estimate("I001", 0.1)),
            "mixes input statuses",
        ),
        (
            _metadata_dataset(_sample("I001", region="iberia")),
            _curation(sample_ids=("I001",)),
            _estimate_dataset(_estimate("I001", 0.1)),
            "expected britain",
        ),
        (
            _metadata_dataset(_sample("I001", time_bce=2600)),
            _curation(sample_ids=("I001",)),
            _estimate_dataset(_estimate("I001", 0.1)),
            "outside the curation time window",
        ),
        (
            _metadata_dataset(_sample("I001")),
            _curation(sample_ids=("I001",)),
            _estimate_dataset(_estimate("I002", 0.1)),
            "missing ancestry estimate",
        ),
        (
            _metadata_dataset(_sample("I001")),
            _curation(sample_ids=("I001",), aggregation_method="median"),
            _estimate_dataset(_estimate("I001", 0.1)),
            "unsupported aggregation_method",
        ),
    ],
)
def test_build_target_dataset_rejects_invalid_pipeline_links(
    metadata: SampleMetadataDataset,
    curation: TargetCurationRecord,
    estimates: SampleAncestryEstimateDataset,
    match: str,
) -> None:
    """Invalid links between curation, metadata, and estimates should fail."""
    with pytest.raises(ValueError, match=match):
        build_target_dataset(
            metadata,
            _curation_dataset(curation),
            estimates,
        )


def test_build_target_dataset_can_relax_region_and_time_checks() -> None:
    """Optional checks can be relaxed for explicitly documented curation."""
    dataset = build_target_dataset(
        _metadata_dataset(_sample("I001", region="iberia", time_bce=2600)),
        _curation_dataset(_curation(sample_ids=("I001",))),
        _estimate_dataset(_estimate("I001", 0.1)),
        options=TargetBuildOptions(
            require_region_match=False,
            require_time_window_match=False,
        ),
    )

    assert dataset.observations[0].mean == 0.1
