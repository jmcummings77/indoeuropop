# Target Decisions

Target-decision files record reviewed choices about whether curated targets
should enter target-observation builds. In the real AADR plus qpAdm workflow,
they are applied to the full requested curation before qpAdm estimate
availability filtering, so decisions can document targets whose current
external qpAdm rows are already unusable.

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

The current committed decision file defers every target row that is not retained
by the local AADR v66 comparison build. Most are marked `rerun_qpadm` because
all selected samples have steppe fractions outside the valid `0-1` range in the
current external table. `Germany_OsterhofenAltenmarkt_BellBeaker` is deferred
because its standard errors are outside the accepted range.
`Germany_StkrStraubing_BellBeaker` remains deferred because the curation audit
found identical replicated qpAdm estimate, standard error, and p-value rows
across all 12 selected samples.
