# Parameter Tables

Parameter tables let one scenario keep global defaults while overriding selected
rates for specific regions and sources. They are optional; a config with only
`[parameters]` continues to use the global defaults.

## Region Parameters

Region parameters override rates shared by every source in a modeled region.

```toml
[region_parameters.britain]
migration_rate = 0.003
epidemic_mortality_rate = 0.01
violence_mortality_rate = 0.002
climate_stress = 0.1
```

Forcing windows are applied after region parameters, so temporary climate or
epidemic stress adds to the region-specific baseline and is capped at `1.0`.

## Source Parameters

Source parameters override fertility, mortality, epidemic risk, or reproductive
multiplier for one region/source pair.

```toml
[source_parameters.britain.steppe]
fertility_rate = 0.04
mortality_rate = 0.028
epidemic_risk = 0.4
reproductive_multiplier = 1.1
```

Unspecified values fall back to the global defaults. For the built-in `local`
and `steppe` source labels, defaults are derived from `SimulationParameters`.
Unknown source labels use local-like defaults until a later multi-source model
formalizes broader ancestry components.

## Current Scope

This is still a source-count scaffold, not a calibrated demographic model.
Tables make regional experiments possible without hard-coding region names into
the simulator, but they do not yet provide age structure, sex-biased inheritance,
or explicit pathogen transmission compartments.

The separate age-structure scaffold is documented in `docs/age-structure.md`.
It is available for experiments but is not yet integrated into these parameter
tables or the main simulator.
