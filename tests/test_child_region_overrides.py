"""Tests for curated child-region override workflows."""

import tomllib
from pathlib import Path

import pytest

from indoeuropop.models import PopulationState, SimulationParameters
from indoeuropop.models.parameterization import (
    ParameterSet,
    RegionParameters,
    SourceParameters,
)
from indoeuropop.orchestration.child_region_overrides import (
    ChildRegionOverrideOutputPaths,
    ChildRegionOverrideSet,
    apply_child_region_overrides,
    load_child_region_overrides,
    run_child_region_override_workflow,
)
from indoeuropop.orchestration.sweeps import ParameterRange, SweepSpec
from indoeuropop.simulation.config import load_sweep_spec
from indoeuropop.simulation.events import MigrationPulse, SimulationSchedule


def test_checked_in_central_europe_child_override_loads_with_review_metadata() -> None:
    """The tracked central-Europe override should load and document its gate."""
    path = Path("curation/aadr-v66-central-europe-child-overrides.toml")
    overrides = load_child_region_overrides(path)
    with path.open("rb") as override_file:
        metadata = tomllib.load(override_file)["review"]

    assert metadata["status"] == "review_candidate"
    assert metadata["protected_degradation_tolerance"] == pytest.approx(0.03)
    assert metadata["protected_holdouts"] == ["britain"]
    assert len(overrides.counts) == 2
    assert overrides.replace_migration_pulses is True
    assert (
        overrides.counts["central_europe__germany_tiefbrunn_cordedware_1"]["steppe"]
        == 42.0
    )
    assert len(overrides.migration_pulses) == 2


def test_child_region_override_workflow_writes_loadable_config(
    tmp_path: Path,
) -> None:
    """Override TOML should replace counts, pulses, and parameter tables."""
    override_path = tmp_path / "overrides.toml"
    output_path = tmp_path / "overridden-config.toml"
    override_path.write_text(_override_toml(), encoding="utf-8")

    result = run_child_region_override_workflow(
        _spec(),
        load_child_region_overrides(override_path),
        paths=ChildRegionOverrideOutputPaths(overridden_config_toml=output_path),
    )
    reloaded = load_sweep_spec(output_path)

    assert result.overridden_config_toml_path == output_path
    assert result.spec.initial_state.counts["central_europe__tiefbrunn"] == {
        "local": 760.0,
        "steppe": 42.0,
    }
    assert tuple(pulse.region for pulse in result.spec.schedule.migration_pulses) == (
        "central_europe__manching",
        "britain",
        "central_europe__tiefbrunn",
    )
    assert result.spec.schedule.migration_pulses[-1].annual_rate == pytest.approx(
        0.00014
    )
    assert (
        result.spec.parameter_set.region_parameters[
            "central_europe__tiefbrunn"
        ].migration_rate
        == 0.0002
    )
    assert (
        result.spec.parameter_set.source_parameters["central_europe__tiefbrunn"][
            "steppe"
        ].reproductive_multiplier
        == 1.18
    )
    assert reloaded.initial_state.counts == result.spec.initial_state.counts
    assert reloaded.schedule.migration_pulses == result.spec.schedule.migration_pulses


def test_child_region_override_append_mode_keeps_existing_pulses() -> None:
    """Append mode should add curated pulses without replacing inherited ones."""
    override_pulse = MigrationPulse(
        region="central_europe__tiefbrunn",
        start_bce=2940,
        end_bce=2500,
        annual_rate=0.00011,
    )
    overridden = apply_child_region_overrides(
        _spec(),
        ChildRegionOverrideSet(
            migration_pulses=(override_pulse,),
            replace_migration_pulses=False,
        ),
    )

    assert tuple(
        pulse.region
        for pulse in overridden.schedule.migration_pulses
        if pulse.region == "central_europe__tiefbrunn"
    ) == ("central_europe__tiefbrunn", "central_europe__tiefbrunn")


def test_child_region_count_override_preserves_schedule_without_pulses() -> None:
    """Count-only overrides should leave the schedule object unchanged."""
    spec = _spec()
    overridden = apply_child_region_overrides(
        spec,
        ChildRegionOverrideSet(
            counts={"central_europe__tiefbrunn": {"local": 760, "steppe": 42}}
        ),
    )

    assert overridden.schedule is spec.schedule


@pytest.mark.parametrize(
    ("contents", "match"),
    [
        ("", "at least one override"),
        ("options = 1\n", "options must be a table"),
        (
            '[options]\nreplace_migration_pulses = "yes"\n',
            "replace_migration_pulses",
        ),
        ("counts = 1\n", "counts must be a table of tables"),
        ("[counts.central_europe__tiefbrunn]\nlocal = -1\n", "non-negative"),
        ("migration_pulses = 1\n", "migration_pulses must be a list"),
        (
            "[region_parameters]\ncentral_europe__tiefbrunn = 1\n",
            "region_parameters must be a table of tables",
        ),
        (
            "[source_parameters.central_europe__tiefbrunn]\nsteppe = 1\n",
            "source_parameters must be a nested table",
        ),
    ],
)
def test_load_child_region_overrides_rejects_malformed_toml(
    tmp_path: Path,
    contents: str,
    match: str,
) -> None:
    """Malformed override files should fail with clear validation errors."""
    override_path = tmp_path / "bad-overrides.toml"
    override_path.write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError, match=match):
        load_child_region_overrides(override_path)


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        (
            ChildRegionOverrideSet(counts={"unknown": {"local": 1.0}}),
            "count override",
        ),
        (
            ChildRegionOverrideSet(
                migration_pulses=(
                    MigrationPulse(
                        region="unknown",
                        start_bce=2990,
                        end_bce=2500,
                        annual_rate=0.0001,
                    ),
                )
            ),
            "migration pulse override",
        ),
        (
            ChildRegionOverrideSet(
                region_parameters={"unknown": RegionParameters(migration_rate=0.001)}
            ),
            "region parameter override",
        ),
        (
            ChildRegionOverrideSet(
                source_parameters={
                    "unknown": {"steppe": SourceParameters(fertility_rate=0.04)}
                }
            ),
            "source parameter override",
        ),
    ],
)
def test_apply_child_region_overrides_rejects_unknown_regions(
    overrides: ChildRegionOverrideSet,
    match: str,
) -> None:
    """Override tables should only target regions already in the sweep spec."""
    with pytest.raises(ValueError, match=match):
        apply_child_region_overrides(_spec(), overrides)


def _spec() -> SweepSpec:
    """Return a small structured sweep spec for override tests."""
    return SweepSpec(
        initial_state=PopulationState(
            {
                "central_europe__tiefbrunn": {"local": 1200, "steppe": 2.5},
                "central_europe__manching": {"local": 1200, "steppe": 2.5},
                "britain": {"local": 7000, "steppe": 5},
            }
        ),
        base_parameters=SimulationParameters(migration_rate=0.00005),
        parameter_ranges=(ParameterRange("migration_rate", 0.0, 0.00003),),
        start_bce=3300,
        end_bce=1700,
        step_years=25,
        sample_count=2,
        seed=661,
        source="steppe",
        schedule=SimulationSchedule(
            migration_pulses=(
                MigrationPulse(
                    region="central_europe__tiefbrunn",
                    start_bce=3000,
                    end_bce=2300,
                    annual_rate=0.00006,
                ),
                MigrationPulse(
                    region="central_europe__manching",
                    start_bce=3000,
                    end_bce=2300,
                    annual_rate=0.00006,
                ),
                MigrationPulse(
                    region="britain",
                    start_bce=2550,
                    end_bce=1800,
                    annual_rate=0.00008,
                ),
            )
        ),
        parameter_set=ParameterSet(
            region_parameters={
                "central_europe__tiefbrunn": RegionParameters(migration_rate=0.00006)
            },
            source_parameters={
                "central_europe__tiefbrunn": {
                    "steppe": SourceParameters(reproductive_multiplier=1.05)
                }
            },
        ),
    )


def _override_toml() -> str:
    """Return one curated child-region override TOML payload."""
    return """
    [options]
    replace_migration_pulses = true

    [counts.central_europe__tiefbrunn]
    local = 760
    steppe = 42

    [[migration_pulses]]
    region = "central_europe__tiefbrunn"
    start_bce = 2980
    end_bce = 2450
    annual_rate = 0.00014

    [region_parameters.central_europe__tiefbrunn]
    migration_rate = 0.0002

    [source_parameters.central_europe__tiefbrunn.steppe]
    reproductive_multiplier = 1.18
    """
