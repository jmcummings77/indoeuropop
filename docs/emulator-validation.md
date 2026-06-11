# Emulator Validation

Emulator validation compares future surrogate-model predictions against
explicit simulator outputs. It does not train an emulator, tune a posterior, or
define a scientifically acceptable error threshold.

## Prediction Records

`EmulatorPrediction` stores a predicted `SummaryVector` for one sweep run and
references that run with its SHA-256 reproducibility fingerprint.

`validate_emulator_predictions` requires predictions to match an
`EmulatorTrainingDataset` exactly:

- every dataset row must have one prediction;
- duplicate predictions are rejected;
- predictions for unknown run fingerprints are rejected;
- selected summary-statistic names must exist in both actual and predicted
  vectors.

## Report

`EmulatorValidationReport` contains one `EmulatorValidationCase` per row, plus
mean and maximum root-mean-square summary distances. If a
`max_allowed_distance` is supplied, each case is marked as inside or outside the
threshold.

## Guardrail

Thresholds are engineering checks, not archaeological conclusions. A surrogate
that passes this scaffold still needs explicit simulator spot checks, held-out
target validation, and domain review before any inference workflow can rely on
its predictions.
