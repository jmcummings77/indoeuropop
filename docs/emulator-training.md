# Emulator Training Data

Emulator training data prepares deterministic sweep outputs for future
surrogate-model experiments. It does not train an emulator, select a model
family, or perform inference.

## Dataset Rows

`EmulatorTrainingRow` combines:

- sampled parameter values from one `SweepRun`;
- a named `SummaryVector` derived from the run's `TrajectorySummary`;
- the run's reproducibility fingerprint.

`emulator_training_dataset_from_sweep_runs` builds rows from sweep runs and
also records the ordered sweep-collection fingerprint.

## Matrices

`EmulatorTrainingDataset.parameter_matrix()` returns sampled parameter values in
stable sorted parameter-name order. `summary_matrix()` returns raw or normalized
summary statistics in `SummaryVector` order. Optional column selections must use
known names and cannot be empty.

These matrices are intended as explicit, reviewable inputs for later emulator
code. Their column names, scaling choices, and fingerprints should be stored
with any future trained surrogate.

## Guardrail

A training matrix is not a posterior, a fitted emulator, or a claim that the
simulator is scientifically valid. Future emulator code must be revalidated
against explicit simulator runs and held-out targets before its predictions are
used for inference.
