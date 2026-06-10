# Output Provenance

Output provenance records keep simulated, observed, synthetic, derived, and
future inferred values separate. This is a reporting guardrail: it prevents a
target observation, simulation summary, fit score, or eventual posterior
estimate from appearing in the same table without an explicit status.

## Record Kinds

- `simulated`: produced directly from simulator output.
- `observed`: loaded from a published target row.
- `synthetic`: loaded from an example or smoke-test target row.
- `derived`: computed from other values, such as target-fit metrics.
- `inferred`: reserved for later inference outputs.

## Helpers

`summary_provenance_records` converts a `TrajectorySummary` into simulated
records. `target_observation_provenance_records` converts one target observation
into target mean and uncertainty records. `target_fit_provenance_records`
converts aggregate fit metrics into derived records.

The first scaffold does not create inferred records. A ranked sweep score is
therefore still `derived`, not a posterior estimate.
