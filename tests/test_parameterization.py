"""Tests for region and source-specific parameter tables."""

from typing import Any, cast

import pytest

from indoeuropop.models import SimulationParameters
from indoeuropop.models.parameterization import (
    ParameterSet,
    RegionParameters,
    SourceParameters,
)


def test_region_parameters_apply_only_non_none_overrides() -> None:
    """RegionParameters should preserve defaults for unspecified fields."""
    base = SimulationParameters(migration_rate=0.001, climate_stress=0.1)
    region_parameters = RegionParameters(migration_rate=0.003)

    resolved = region_parameters.apply(base)

    assert resolved.migration_rate == 0.003
    assert resolved.climate_stress == 0.1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"migration_rate": -0.1},
        {"migration_rate": 1.1},
        {"climate_stress": float("nan")},
    ],
)
def test_region_parameters_reject_invalid_values(kwargs: dict[str, float]) -> None:
    """Region-level rates should remain probability-like."""
    with pytest.raises(ValueError):
        RegionParameters(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"fertility_rate": -0.1},
        {"mortality_rate": 1.1},
        {"epidemic_risk": float("inf")},
        {"reproductive_multiplier": -0.1},
    ],
)
def test_source_parameters_reject_invalid_values(kwargs: dict[str, float]) -> None:
    """Source-level overrides should reject invalid rates and multipliers."""
    with pytest.raises(ValueError):
        SourceParameters(**kwargs)


def test_parameter_set_resolves_defaults_and_overrides() -> None:
    """ParameterSet should layer source overrides over global source defaults."""
    base = SimulationParameters(
        fertility_rate=0.02,
        local_mortality_rate=0.03,
        steppe_mortality_rate=0.025,
        local_epidemic_risk=1.0,
        steppe_epidemic_risk=0.4,
        elite_reproductive_advantage=1.2,
    )
    parameter_set = ParameterSet(
        source_parameters={
            "britain": {
                "steppe": SourceParameters(fertility_rate=0.04),
                "local": SourceParameters(reproductive_multiplier=0.8),
            }
        }
    )

    steppe = parameter_set.source_for(base, region="britain", source="steppe")
    local = parameter_set.source_for(base, region="britain", source="local")
    unknown = parameter_set.source_for(base, region="britain", source="unknown")

    assert steppe.fertility_rate == 0.04
    assert steppe.mortality_rate == 0.025
    assert steppe.epidemic_risk == 0.4
    assert steppe.reproductive_multiplier == 1.2
    assert local.fertility_rate == 0.02
    assert local.reproductive_multiplier == 0.8
    assert unknown.mortality_rate == 0.03


def test_parameter_set_resolves_region_parameters() -> None:
    """ParameterSet should return base parameters for unconfigured regions."""
    base = SimulationParameters(migration_rate=0.001)
    parameter_set = ParameterSet(
        region_parameters={"britain": RegionParameters(migration_rate=0.004)}
    )

    assert parameter_set.parameters_for_region(base, "britain").migration_rate == 0.004
    assert parameter_set.parameters_for_region(base, "iberia") == base


@pytest.mark.parametrize(
    "kwargs",
    [
        {"region_parameters": {"": RegionParameters()}},
        {"source_parameters": {"": {"steppe": SourceParameters()}}},
        {"source_parameters": {"britain": {"": SourceParameters()}}},
    ],
)
def test_parameter_set_rejects_blank_table_keys(kwargs: dict[str, object]) -> None:
    """Parameter tables should not accept blank region or source names."""
    with pytest.raises(ValueError):
        ParameterSet(**cast(Any, kwargs))
