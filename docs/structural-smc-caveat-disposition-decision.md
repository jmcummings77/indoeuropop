# Structural SMC Caveat Disposition Decision

Date: 2026-07-15

Status: promote
`curation/aadr-v66-structural-smc-caveat-dispositions.csv` as the reviewed
caveat input for the current AADR v66 structural SMC robustness decision.

## Scope

The tracked CSV records human-reviewed dispositions for the 42 rows in the
current structural SMC caveat drilldown. Those rows were derived from the
target-fragility gate, fit-metric sensitivity gate, and source-model
sensitivity gate for the `central-europe-child-interaction-best` candidate.

This decision freezes a review state. It does not promote the candidate to a
historical explanation, validate individual qpAdm estimates, or turn the
engineering SMC scaffold into a formal population-genetic posterior.

## Evidence

The review used these generated evidence surfaces:

- `results/qpadm-rerun/structured-smc-fragility-gate/target-fragility-gate.md`;
- `results/qpadm-rerun/structured-smc-fit-metric-sensitivity/fit-metric-sensitivity.md`;
- `results/qpadm-rerun/structured-smc-source-model-sensitivity/source-model-sensitivity.md`;
- `results/qpadm-rerun/structural-smc-caveat-drilldown/structural-smc-caveat-drilldown.csv`;
- the corresponding uncertainty reports and sample-level disagreement-target
  audit; and
- the priority queue as a triage aid rather than a scientific decision rule.

The frozen evidence manifest records SHA-256 checksums for the exact tracked
decision inputs and generated summaries used to rebuild the unified decision.
Downloaded AADR data and the full generated SMC run directories remain outside
Git.

## Dispositions

The reviewed table contains 38 `accepted_caveat` rows and 4 `not_applicable`
rows. It contains no unresolved or promotion-blocking dispositions.

The six target-fragility rows are accepted only as exclusions from promotion
evidence. Their existing `retain_with_caveat` target decisions allow
exploratory comparison; they are not treated as calibrated target evidence.

Fit-metric disagreements for the Czechia and Poland folds are retained as weak
diagnostics because holdout preferences are stable across the two metrics while
uncertainty weighting reduces the target-level differences to ties.

Source-model disagreements are identical on the baseline and accepted source
surfaces. Tiefbrunn and the early chronology fold retain local-fit evidence for
the child candidate, but that evidence is not generalized into a demographic
claim. The remaining disagreements become weak diagnostics after uncertainty
weighting.

The missing Manching override rows are `not_applicable` because common-target
alignment removes the accepted-only Manching target from both source-model
comparison surfaces. The skipped Britain and late chronology folds are also
`not_applicable` because the six-target common fragility-filtered surface has no
holdout observations for those folds.

## Decision

The reviewed dispositions remove the unresolved-review caution from the
unified robustness decision. The candidate remains `review_with_caveats`, with
the recommendation `promote_only_with_documented_caveats`, because seven
substantive target, metric, and source-model diagnostics remain.

This is a model-governance decision. A non-blocked robustness result means the
configured screens did not find preference instability that crosses the
promotion threshold. It is not scientific acceptance of the candidate or its
parameter values.

## Rebuild

Rebuild the decision and freeze its evidence manifest with:

```bash
uv run indoeuropop validate-structured-smc-robustness \
  --robustness-candidate-name central-europe-child-interaction-best \
  --target-fragility-decisions-csv results/qpadm-rerun/structured-smc-fragility-gate/target-fragility-decisions.csv \
  --target-fragility-report-md results/qpadm-rerun/structured-smc-fragility-gate/target-fragility-gate.md \
  --fit-metric-sensitivity-summary-csv results/qpadm-rerun/structured-smc-fit-metric-sensitivity/fit-metric-sensitivity-summary.csv \
  --fit-metric-sensitivity-report-md results/qpadm-rerun/structured-smc-fit-metric-sensitivity/fit-metric-sensitivity.md \
  --source-model-sensitivity-summary-csv results/qpadm-rerun/structured-smc-source-model-sensitivity/source-model-sensitivity-summary.csv \
  --source-model-sensitivity-report-md results/qpadm-rerun/structured-smc-source-model-sensitivity/source-model-sensitivity.md \
  --caveat-drilldown-csv results/qpadm-rerun/structural-smc-caveat-drilldown/structural-smc-caveat-drilldown.csv \
  --caveat-drilldown-report-md results/qpadm-rerun/structural-smc-caveat-drilldown/structural-smc-caveat-drilldown.md \
  --caveat-dispositions-csv curation/aadr-v66-structural-smc-caveat-dispositions.csv \
  --caveat-disposition-report-md results/qpadm-rerun/structural-smc-caveat-dispositions.md \
  --robustness-decision-record-md docs/structural-smc-caveat-disposition-decision.md \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides-interaction-best.toml \
  --robustness-output-dir results/qpadm-rerun/structural-smc-robustness-decision \
  --manifest-json curation/aadr-v66-structural-smc-evidence-manifest.json
```

Re-run this command whenever a gate summary, the caveat drilldown, the tracked
dispositions, the candidate override, or this decision record changes. Review
the new checksums and decision counts before replacing the tracked manifest.
