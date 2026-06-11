# Target Decisions

Target-decision files record reviewed choices about whether curated targets
should enter target-observation builds. They are applied after qpAdm estimate
availability filtering and before target aggregation, so a problematic target
can be deferred without deleting its curation row or source evidence.

## Schema

The CSV columns are:

- `target_id`: target-curation identifier.
- `decision`: one of `retain`, `retain_with_caveat`, `exclude`, `split`, or
  `rerun_qpadm`.
- `reason`: required human-readable review rationale.
- `requested_group_id`: optional source AADR group label.
- `reviewer`: optional reviewer or process label.
- `decision_date`: optional review date.
- `note`: optional extra context.

`retain` and `retain_with_caveat` keep targets in builds. `exclude`, `split`,
and `rerun_qpadm` defer targets from builds while preserving the reviewed
reason.

## Apply Decisions

```bash
uv run indoeuropop apply-target-decisions \
  --sample-metadata results/real-aadr-comparison/aadr-target-sample-metadata.csv \
  --target-curation results/real-aadr-comparison/aadr-target-curation.csv \
  --target-decisions curation/aadr-v66-western-europe-target-decisions.csv \
  --sample-metadata-out results/real-aadr-comparison/decision-filtered-sample-metadata.csv \
  --target-curation-out results/real-aadr-comparison/decision-filtered-target-curation.csv
```

The current committed decision file marks
`Germany_StkrStraubing_BellBeaker` as `rerun_qpadm` because the curation audit
found identical replicated qpAdm estimate, standard error, and p-value rows
across all 12 selected samples. It is therefore deferred from comparison
targets until the qpAdm handoff is reviewed.
