# Reproducibility Fingerprints

Reproducibility fingerprints identify simulator outputs with canonical JSON and
SHA-256 digests. They are intended for audit trails before any emulator,
ABC-SMC, or Bayesian optimization layer is introduced.

## Fingerprinted Artifacts

The first fingerprint scaffold supports:

- `SimulationResult` payloads, including times and source-count states;
- individual `SweepRun` payloads, including sampled values, parameters, and
  trajectory summaries;
- ordered sweep-run collections.

`canonical_json_payload` serializes payloads with sorted keys, compact
separators, and no non-finite floating values. `fingerprint_*` helpers wrap that
payload with the `indoeuropop-fingerprint-v1` schema and compute a SHA-256
digest.

## Provenance Bridge

`ReproducibilityFingerprint.to_provenance_record()` converts a digest into a
derived `ProvenanceRecord`. Reports can therefore include output identity
without mixing fingerprints with observed targets or inferred quantities.

## Guardrail

A matching fingerprint means a modeled artifact serialized to the same
canonical payload. It is not scientific validation, a posterior estimate, or a
claim that the model is historically correct.
