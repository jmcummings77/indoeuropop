# Validation Splits

Validation splits are a lightweight robustness scaffold for target-fit scoring.
They are not posterior inference and they do not prove that a model is
historically correct.

## Region Holdouts

`split_targets_by_region` partitions a `TargetDataset` into calibration and
validation halves using one or more held-out region labels. Both halves must
contain at least one observation.

```python
from indoeuropop import split_targets_by_region

target_split = split_targets_by_region(targets, validation_regions=("iberia",))
```

The initial splitter is deliberately simple. It is meant to keep early model
comparisons honest by showing whether a parameter setting that fits calibration
targets also behaves reasonably on held-out target rows.

## Validated Sweeps

`run_validated_parameter_sweep` runs the deterministic simulator for each
Latin-hypercube sample, ranks runs by calibration fit, and preserves validation
fit statistics for each sampled parameter set.

`ValidationFit.generalization_gap(metric)` reports validation minus calibration
fit for a supported metric. Positive gaps indicate worse held-out fit for
metrics where lower values are better.

## Guardrail

Validation splits are model-debugging evidence, not a formal posterior,
likelihood, or archaeological conclusion. A future ABC-SMC, Bayesian
optimization, or emulator workflow should reuse explicit calibration and
validation targets rather than tuning every target row at once.
