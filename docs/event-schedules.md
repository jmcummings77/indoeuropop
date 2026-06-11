# Event Schedules

Event schedules layer time-bounded stressors over a base simulation. They are
intended for exploratory model structure, not as evidence by themselves.

## Migration Pulses

`MigrationPulse` adds an annual incoming steppe-source migration rate to one
region during an inclusive BCE window. The pulse is evaluated at each simulation
step midpoint.

```toml
[[migration_pulses]]
region = "britain"
start_bce = 2900
end_bce = 2700
annual_rate = 0.003
```

The initial implementation supports only `source = "steppe"` because the v1
simulator has explicit local and steppe source dynamics.

## Forcing Windows

`ForcingWindow` adds temporary climate stress and epidemic mortality to base
parameters. Multiple active windows are summed and capped at `1.0`.

```toml
[[forcing_windows]]
start_bce = 2850
end_bce = 2750
climate_stress_delta = 0.2
epidemic_mortality_delta = 0.01
```

Climate stress reduces fertility and adds a small shared mortality penalty.
Epidemic mortality is still an exogenous hazard in this phase; compartmental
transmission experiments live in the separate epidemic-compartments scaffold and
are not yet wired into scheduled forcing windows.
