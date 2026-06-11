"""Tests for target-aligned structural-region workflow helpers."""

from pathlib import Path

import pytest

from indoeuropop.data.target_notes import target_note_value
from indoeuropop.data.targets import (
    TargetDataset,
    TargetObservation,
    load_target_dataset,
)
from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.models.parameterization import (
    ParameterSet,
    RegionParameters,
    SourceParameters,
)
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec
from indoeuropop.orchestration.target_structure import (
    TargetStructureOutputPaths,
    run_target_structure_workflow,
    structure_sweep_spec,
    structure_target_dataset,
    sweep_spec_to_toml,
)
from indoeuropop.simulation.config import load_sweep_spec
from indoeuropop.simulation.events import (
    ForcingWindow,
    MigrationPulse,
    SimulationSchedule,
)


def test_run_target_structure_workflow_writes_loadable_outputs(
    tmp_path: Path,
) -> None:
    """The workflow should split selected target regions and config tables."""
    targets_path = tmp_path / "structured-targets.csv"
    config_path = tmp_path / "structured-config.toml"

    result = run_target_structure_workflow(
        _spec(region="central_europe"),
        _targets(),
        structure_regions=("central_europe",),
        paths=TargetStructureOutputPaths(
            structured_targets_csv=targets_path,
            structured_config_toml=config_path,
        ),
    )
    structured_spec = result.spec
    reloaded_targets = load_target_dataset(targets_path)
    reloaded_spec = load_sweep_spec(config_path)

    assert tuple(mapping.structured_region for mapping in result.mappings) == (
        "central_europe__germany_tiefbrunn_cordedware_1",
        "central_europe__germany_alberstedt_lnba",
    )
    assert tuple(target.region for target in result.targets.observations) == (
        "central_europe__germany_tiefbrunn_cordedware_1",
        "central_europe__germany_alberstedt_lnba",
        "britain",
    )
    assert reloaded_targets.observations == result.targets.observations
    assert structured_spec.region is None
    assert set(structured_spec.initial_state.regions()) == {
        "central_europe__germany_tiefbrunn_cordedware_1",
        "central_europe__germany_alberstedt_lnba",
        "britain",
    }
    assert structured_spec.initial_state.source_total(
        "local", "central_europe__germany_tiefbrunn_cordedware_1"
    ) == pytest.approx(500.0)
    assert tuple(
        pulse.region for pulse in structured_spec.schedule.migration_pulses
    ) == (
        "central_europe__germany_tiefbrunn_cordedware_1",
        "central_europe__germany_alberstedt_lnba",
        "britain",
    )
    assert set(structured_spec.parameter_set.region_parameters) == {
        "central_europe__germany_tiefbrunn_cordedware_1",
        "central_europe__germany_alberstedt_lnba",
        "britain",
    }
    assert (
        structured_spec.parameter_set.source_parameters[
            "central_europe__germany_tiefbrunn_cordedware_1"
        ]["steppe"].reproductive_multiplier
        == 1.1
    )
    assert (
        target_note_value(result.targets.observations[0].note, "parent_region")
        == "central_europe"
    )
    assert reloaded_spec.initial_state.counts == structured_spec.initial_state.counts
    assert reloaded_spec.schedule.migration_pulses == (
        structured_spec.schedule.migration_pulses
    )


def test_structure_sweep_spec_without_mappings_returns_original_spec() -> None:
    """An empty mapping set should leave the sweep spec unchanged."""
    spec = _spec(region="britain")

    assert structure_sweep_spec(spec, ()) is spec


@pytest.mark.parametrize(
    ("structure_field", "expected_region"),
    [
        ("region", "britain__britain"),
        ("source", "britain__steppe"),
        ("citation_key", "britain__synthetic"),
    ],
)
def test_structure_target_dataset_supports_direct_fields(
    structure_field: str,
    expected_region: str,
) -> None:
    """Direct target fields should be usable as structure labels."""
    structured_targets, mappings = structure_target_dataset(
        TargetDataset.from_rows([_target("britain", "britain_group", 0.05)]),
        structure_field=structure_field,
    )

    assert structured_targets.observations[0].region == expected_region
    assert mappings[0].structured_region == expected_region


def test_structure_target_dataset_rejects_invalid_structure_selectors() -> None:
    """Invalid structure fields and labels should raise explanatory errors."""
    with pytest.raises(ValueError, match="structure_field"):
        structure_target_dataset(_targets(), structure_field="unknown")
    with pytest.raises(ValueError, match="target note missing"):
        structure_target_dataset(_targets(), structure_field="note:missing")
    with pytest.raises(ValueError, match="structured region labels"):
        structure_target_dataset(
            TargetDataset.from_rows([_target("central_europe", "!!!", 0.05)]),
            structure_field="note:requested_group_id",
        )


def test_sweep_spec_to_toml_quotes_non_bare_keys() -> None:
    """Generated TOML should quote labels that are not bare TOML keys."""
    spec = SweepSpec(
        initial_state=PopulationState({"region with space": {"local source": 10}}),
        base_parameters=SimulationParameters(migration_rate=0.001),
        parameter_ranges=(ParameterRange("migration_rate", 0.001, 0.002),),
        sample_count=1,
        seed=5,
        source="local source",
        region="region with space",
    )
    toml_text = sweep_spec_to_toml(spec)

    assert '[counts."region with space"]' in toml_text
    assert '"local source" = 10' in toml_text
    assert 'region = "region with space"' in toml_text


def _spec(region: str | None = "britain") -> SweepSpec:
    """Return a small multi-region sweep spec for structure tests."""
    return SweepSpec(
        initial_state=PopulationState(
            {
                "central_europe": {"local": 1000, "steppe": 40},
                "britain": {"local": 900, "steppe": 30},
            }
        ),
        base_parameters=SimulationParameters(migration_rate=0.001),
        parameter_ranges=(ParameterRange("migration_rate", 0.001, 0.003),),
        start_bce=3000,
        end_bce=2900,
        step_years=50,
        sample_count=2,
        seed=17,
        source="steppe",
        region=region,
        schedule=_schedule(),
        parameter_set=_parameter_set(),
    )


def _schedule() -> SimulationSchedule:
    """Return a schedule-like object with pulses and forcing windows."""
    return SimulationSchedule(
        migration_pulses=(
            MigrationPulse(
                region="central_europe",
                start_bce=2990,
                end_bce=2950,
                annual_rate=0.002,
            ),
            MigrationPulse(
                region="britain",
                start_bce=2990,
                end_bce=2950,
                annual_rate=0.001,
            ),
        ),
        forcing_windows=(
            ForcingWindow(
                start_bce=2980,
                end_bce=2960,
                climate_stress_delta=0.05,
                epidemic_mortality_delta=0.01,
            ),
        ),
    )


def _parameter_set() -> ParameterSet:
    """Return region and source overrides for structure tests."""
    return ParameterSet(
        region_parameters={
            "central_europe": RegionParameters(migration_rate=0.003),
            "britain": RegionParameters(climate_stress=0.02),
        },
        source_parameters={
            "central_europe": {"steppe": SourceParameters(reproductive_multiplier=1.1)},
            "britain": {"steppe": SourceParameters(fertility_rate=0.04)},
        },
    )


def _targets() -> TargetDataset:
    """Return targets with two central European groups and one control region."""
    return TargetDataset.from_rows(
        [
            _target("central_europe", "Germany_Tiefbrunn_CordedWare-1", 0.1),
            _target("central_europe", "Germany_Alberstedt_LNBA", 0.2),
            _target("britain", "Britain_BellBeaker", 0.15),
        ]
    )


def _target(region: str, requested_group_id: str, mean: float) -> TargetObservation:
    """Return one synthetic target with structure-ready note metadata."""
    return TargetObservation(
        status="synthetic",
        region=region,
        source="steppe",
        time_bce=2900,
        mean=mean,
        uncertainty=0.05,
        citation_key="synthetic",
        citation="Synthetic target",
        note=f"requested_group_id={requested_group_id}",
    )
