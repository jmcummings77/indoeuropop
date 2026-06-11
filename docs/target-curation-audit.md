# Target Curation Audit

The target-curation audit command expands one residual outlier into the
evidence that produced it. It joins the residual CSV, target-curation CSV,
sample metadata CSV, and sample ancestry-estimate CSV so reviewers can inspect
whether an apparent model miss is really a simulator issue, a qpAdm issue, a
target grouping issue, or an input-join issue.

By default, the command audits the residual with the largest absolute z-score.
Use `--target-id` or `--requested-group-id` to audit a specific target.
For deferred targets such as Stkr-Straubing, run the audit against a residual
CSV generated before applying the target-decision file.

## CLI

```bash
uv run indoeuropop audit-target-curation \
  --target-residuals results/real-aadr-comparison/target-residuals.csv \
  --target-curation results/real-aadr-comparison/aadr-target-curation.csv \
  --sample-metadata results/real-aadr-comparison/aadr-target-sample-metadata.csv \
  --ancestry-estimates results/real-aadr-comparison/sample-ancestry-estimates.csv \
  --target-audit-md results/real-aadr-comparison/stkr-straubing-curation-audit.md
```

The Markdown report includes:

- the residual row and curation target ID;
- curation window, sample count, method, and citation key;
- joined metadata and qpAdm estimates for every curated sample;
- missing metadata or missing estimate diagnostics;
- date-window, CRITICAL-assessment, high-standard-error, and replicated-estimate
  checks;
- a cautious recommendation for the next review step.

## Current Stkr-Straubing Finding

The current real AADR comparison audits
`Germany_StkrStraubing_BellBeaker` as the top residual. The audit shows that
the target contains 12 curated samples, all joined successfully, but all 12
carry the same qpAdm steppe estimate, the same standard error, and the same
qpAdm p-value. One selected sample is marked `assessment=CRITICAL` in the AADR
metadata, and the group spans two publication keys.

That pattern should be reviewed as target evidence before changing simulator
parameters. The next scientific step is to inspect the external qpAdm table
granularity and source/outgroup model, then decide whether this site-level
target should be rerun, excluded, split, or retained with an explicit caveat.

The current project decision is recorded in
`curation/aadr-v66-western-europe-target-decisions.csv` as `rerun_qpadm`, which
defers this target from regenerated target observations until the qpAdm handoff
is reviewed.
