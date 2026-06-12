# IndoEuroPop

IndoEuroPop is a research-engineering scaffold for mechanistic models of
Late Neolithic and Early Bronze Age population dynamics in western Eurasia.

![Map of Yamaya expansions](https://upload.wikimedia.org/wikipedia/commons/b/b1/Indo-European_migrations.jpg)

My primary motive for pursuing this project is curiosity about the possible role that Yersinia Pestis (aka the Plague or the Black Death) played in enabling the rapid and far flung expansion of the Yamnaya Steppe Pastoralists (YSP) and their culture across huge swathes of Eurasia during the Early Bronze Age (ca. 4000-1000 BCE), which is very likely the mechanism by which Indo-European languages came to dominate such a wide and diverse swathe of territory, stretching from India to Ireland.

In particular, I am curious about the extent to which differential immune system advantages may have enabled near complete YSP replacement of the preexisting Western Hunter Gatherer (WHG) and Anatolian-derived Neolithic Farmer (ANF) populations of Western Europe. Recent evidence suggests that a shockingly high proportion of both the Yamnaya and the populations they displaced during this period suffered from Y. Pestis infections. The Plague bacillus itself likely derives from zoonotic reservoirs native to the Yamnaya-dominated Eurasian steppe regions, including domesticated animals (especially horses) with which the Yamnya lived in much closer contact than any prior human populations ever had. It is possible that extended, multigenerational exposure to the bacillus on the steppes drove immune system adaptations among the Yamnaya that gave them a differential advantage over neighboring populations of early humans as they expanded outwards from their steppe homeland.

Unbenknowst to the steppe pastoralists, their large domesticated herds may have acted like biowarfare incubators, carrying the deadly infection with them into new territories where the locals had no prior exposure and thus no acquired immunity. Rapid depopulation and the social disruption that naturally follows from a sudden widespread mortality event may have undermined any resistance WHG/ANF peoples may have otherwise offered to an influx of YSP migrants. Even assuming the migrations were peaceful and even welcomed by the indigenous peoples, simply reducing the baseline numbers of people with WHG/ANF heritage prior to a post-migration admixture event necessarily reduces the proportion of that heritage likely to survive mixing with the incoming migrant population. 

Similar phenomenon appear in the historical record from subsequent eras for which documentary evidence survives, suggesting by analogy that the disease hypothesis is worth investigating.

As suggested by the title of the most famous book on this topic (the Horse, the Wheel, and Language), the Yamnaya were the first people to successfully domesticate horses and were early adopters of covered wagons, enabling them to survive on the Eurasian steppes that had formerly been impassable wasteland because it was too difficult for someone on foot to carry sufficient supplies to cross between the limited and isolated sources of fresh water available on the plains. Similarly, the expansion of Mongolian control over most of Eurasia during the 13th century set the conditions for the 14th century outbreak of Y. Pestis in Western Europe now known as the Black Death. In both cases, horse-riding steppe pastoralists with greater resistance to the disease (though not full immunity in all cases, it should be noted) spread across the steppes, linking together areas on the fringes of the steppelands that were formerly isolated from each other by the impassable terrain, while also exposing them to the steppe-dwelling zoonotic reservoir species.

It is also becoming increasingly clear that previous historical research into the pre-Columbian population of the Americas dramatically underestimated both how many Native Americans lived in the New World and (relatedly) how many were killed by novel European diseases following contact in 1492. In fact, much of the European success in conquering the Americas was likely attributable to waves of disease rippling out in advance of European settlers along existing native trade routes. In the 100-150 years after 1492, those waves of disease killed something like 80-90% of the local people living in the Americas, often before the Europeans ever even laid eyes on them, which in turn helped shape the European misconception that the Americas were unpeopled, unsettled lands free for anyone to claim. The sudden introduction of a devastating collection of infectious diseases ensured not only that there would be fewer Native Americans alive to resist European invaders, but also destroyed the political and cultural centers of power that may otherwise have been able to organize resistance. The Plague may have had a similar effect on the indigineous populations of Western Europe, paving the way for the Indo-European expansion.

In this repository, I hope to test alternative models of the YSP expansion against empirical DNA data collected from historical remains dated to this period and the distribution of surviving YSP, WHG, and ANF heritage in modern populations.

## Modeling Philosophy

The
initial focus is on building reproducible code that can later compare migration,
epidemic, climate, violence, fertility, subsistence, and elite-reproduction
hypotheses against ancient-DNA observations.

This repository does **not** yet contain a fitted scientific model,
ancient-DNA genotype processing, or inferred historical results. The first
milestone is a small, tested Python package that makes the modeling assumptions
explicit and easy to replace.

The project treats steppe-related ancestry as an observable derived from modeled
population counts rather than as a value that is manually adjusted. This keeps
the code honest: births, deaths, migration, and epidemic stress must change the
underlying state before ancestry changes.

The scaffold is intentionally cautious about archaeology and genetics. Major
steppe-related ancestry shifts in Corded Ware and Bell Beaker contexts are a
starting motivation, but the package does not assume that any one mechanism
explains all regions. Plague, elite dominance, climate stress, and violence are
implemented as model components to test, not conclusions to smuggle in.

## Quick Start

```bash
uv sync --all-extras --dev
uv run indoeuropop demo
uv run indoeuropop demo --plot results/demo-ancestry.png
uv run indoeuropop demo --provenance-csv results/provenance.csv
uv run indoeuropop demo --manifest-json results/demo-manifest.json
```

Run the full verification suite:

```bash
uv run pytest --cov=indoeuropop --cov-report=term-missing --cov-fail-under=100
uv run black --check .
uv run ruff check .
uv run mypy src tests
```

Compare a demo run against the synthetic target example:

```bash
uv run indoeuropop demo --targets examples/target-observations.example.csv
```

Download or materialize cataloged source files:

```bash
uv run indoeuropop download-sources \
  --data-sources examples/data-sources.example.toml \
  --output-dir data/raw \
  --download-manifest-csv results/downloads.csv
```

The downloader checks root `/data/` first for an artifact with the expected
filename. Existing files are reused by default and are not replaced unless
`--overwrite` is supplied explicitly.

Export local AADR annotations as sample metadata:

```bash
uv run indoeuropop load-aadr \
  --aadr-dir data \
  --sample-metadata-out data/aadr-sample-metadata.csv
```

Suggest reviewable AADR group selections from local annotation geography,
chronology, and group labels:

```bash
uv run indoeuropop suggest-aadr-groups \
  --aadr-dir data \
  --aadr-groups-out results/aadr-group-suggestions.tsv
```

Prepare real AADR sample metadata and curation inputs for later target
building:

```bash
uv run indoeuropop prepare-aadr-target-inputs \
  --aadr-dir data \
  --aadr-groups results/aadr-group-suggestions.tsv \
  --sample-metadata-out results/aadr-target-sample-metadata.csv \
  --target-curation-out results/aadr-target-curation.csv
```

Plan an external ADMIXTOOLS qpAdm run from the committed western-Europe target
seed:

```bash
uv run indoeuropop plan-qpadm-run \
  --genotype-prefix data \
  --aadr-groups curation/aadr-v66-western-europe-qpadm-targets.tsv \
  --qpadm-estimates data/qpadm/steppe-estimates.csv \
  --qpadm-f2-dir data/qpadm/f2 \
  --qpadm-manifest-json results/qpadm-run.json
```

Convert externally computed qpAdm-style steppe estimates into sample-level
ancestry estimates:

```bash
uv run indoeuropop load-qpadm-estimates \
  --qpadm-estimates data/qpadm/steppe-estimates.csv \
  --ancestry-estimates-out results/sample-ancestry-estimates.csv \
  --skip-missing-standard-error
```

Filter curation rows to those with complete valid estimates:

```bash
uv run indoeuropop filter-target-inputs \
  --sample-metadata results/aadr-target-sample-metadata.csv \
  --target-curation results/aadr-target-curation.csv \
  --ancestry-estimates results/sample-ancestry-estimates.csv \
  --sample-metadata-out results/filtered-aadr-target-sample-metadata.csv \
  --target-curation-out results/filtered-aadr-target-curation.csv
```

Build the reviewed real AADR/qpAdm target observations and diagnostics in one
workflow:

```bash
uv run indoeuropop build-aadr-qpadm-targets \
  --aadr-dir data \
  --aadr-groups curation/aadr-v66-western-europe-qpadm-targets.tsv \
  --qpadm-estimates data/qpadm/steppe-estimates.csv \
  --sample-metadata-out results/aadr-target-sample-metadata.csv \
  --target-curation-out results/aadr-target-curation.csv \
  --ancestry-estimates-out results/sample-ancestry-estimates.csv \
  --target-output results/aadr-target-observations.csv \
  --target-decisions curation/aadr-v66-western-europe-target-decisions.csv \
  --target-diagnostics-json results/aadr-target-diagnostics.json
```

After running the focused external qpAdm rerun, merge the rerun table with the
baseline estimates and write a pre/post target-availability review:

```bash
uv run indoeuropop ingest-qpadm-reruns \
  --aadr-dir data \
  --aadr-groups curation/aadr-v66-western-europe-qpadm-targets.tsv \
  --qpadm-estimates data/qpadm/steppe-estimates.csv \
  --qpadm-rerun-estimates data/qpadm/steppe-rerun-estimates.csv \
  --sample-metadata-out results/qpadm-rerun/aadr-target-sample-metadata.csv \
  --target-curation-out results/qpadm-rerun/aadr-target-curation.csv \
  --ancestry-estimates-out results/qpadm-rerun/merged-sample-ancestry-estimates.csv \
  --target-output results/qpadm-rerun/aadr-target-observations.csv \
  --baseline-target-output results/qpadm-rerun/baseline-target-observations.csv \
  --accepted-target-output results/qpadm-rerun/accepted-target-observations.csv \
  --qpadm-rerun-comparison-csv results/qpadm-rerun/qpadm-rerun-comparison.csv \
  --qpadm-rerun-report-md results/qpadm-rerun/qpadm-rerun-report.md \
  --target-decisions curation/aadr-v66-western-europe-target-decisions.csv \
  --target-diagnostics-json results/qpadm-rerun/qpadm-rerun-diagnostics.json
```

Use `results/qpadm-rerun/accepted-target-observations.csv` for model
comparison; the broader `aadr-target-observations.csv` is a buildability review
surface that can still include targets awaiting a reviewed decision.

Apply reviewed target decisions to already prepared target inputs:

```bash
uv run indoeuropop apply-target-decisions \
  --sample-metadata results/real-aadr-comparison/aadr-target-sample-metadata.csv \
  --target-curation results/real-aadr-comparison/aadr-target-curation.csv \
  --target-decisions curation/aadr-v66-western-europe-target-decisions.csv \
  --sample-metadata-out results/real-aadr-comparison/decision-filtered-sample-metadata.csv \
  --target-curation-out results/real-aadr-comparison/decision-filtered-target-curation.csv
```

Build target observations from curated sample-level inputs:

```bash
uv run indoeuropop build-targets \
  --sample-metadata examples/sample-metadata.example.csv \
  --target-curation examples/target-curation.example.csv \
  --ancestry-estimates examples/sample-ancestry-estimates.example.csv \
  --target-output results/built-targets.csv
```

Run a deterministic sweep from TOML:

```bash
uv run indoeuropop sweep \
  --config examples/sweep.example.toml \
  --sweep-runs-csv results/sweep-runs.csv \
  --sensitivity-csv results/sensitivity.csv \
  --manifest-json results/sweep-manifest.json
```

Rank deterministic sweep runs against a target CSV:

```bash
uv run indoeuropop sweep \
  --config examples/sweep.example.toml \
  --targets path/to/matching-targets.csv \
  --target-fit-csv results/target-fit.csv \
  --fit-metric root_mean_squared_error
```

Run a first-class target comparison workflow with best-run residuals and a
diagnostic overlay plot:

```bash
uv run indoeuropop compare-targets \
  --config examples/sweep.example.toml \
  --targets examples/sweep-targets.example.csv \
  --target-fit-csv results/target-fit.csv \
  --target-residuals-csv results/target-residuals.csv \
  --plot results/target-comparison.png \
  --manifest-json results/target-comparison-manifest.json \
  --fit-metric root_mean_squared_error
```

Compare the committed real-data review config against regenerated AADR/qpAdm
targets:

```bash
uv run indoeuropop compare-targets \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/real-aadr-comparison/aadr-target-observations.csv \
  --target-fit-csv results/real-aadr-comparison/target-fit.csv \
  --target-residuals-csv results/real-aadr-comparison/target-residuals.csv \
  --plot results/real-aadr-comparison/target-comparison.png \
  --manifest-json results/real-aadr-comparison/target-comparison-manifest.json \
  --fit-metric root_mean_squared_error
```

Run held-out validation on accepted post-rerun targets:

```bash
uv run indoeuropop validate-targets \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/qpadm-rerun/accepted-target-observations.csv \
  --validation-fit-csv results/qpadm-rerun/accepted-validation-fit.csv \
  --validation-report-md results/qpadm-rerun/accepted-validation-report.md \
  --manifest-json results/qpadm-rerun/accepted-validation-manifest.json \
  --fit-metric root_mean_squared_error
```

For a more granular leave-one-target-group-out diagnostic, use the target-note
metadata key written by the AADR/qpAdm target builder:

```bash
uv run indoeuropop validate-targets \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/qpadm-rerun/accepted-target-observations.csv \
  --validation-field note:requested_group_id \
  --validation-fit-csv results/qpadm-rerun/accepted-group-validation-fit.csv \
  --validation-report-md results/qpadm-rerun/accepted-group-validation-report.md \
  --manifest-json results/qpadm-rerun/accepted-group-validation-manifest.json \
  --fit-metric root_mean_squared_error
```

In the current local accepted-target validation, both leave-one-region-out folds
selected run `9`. Holding out Britain gave validation RMSE `0.122664`; holding
out central Europe gave validation RMSE `0.305043`. Leave-one-requested-group
validation again selected run `9` for every fold, with the largest validation
RMSE on `Germany_Tiefbrunn_CordedWare-1` (`0.630451`).

Project target-note groups into explicit child model regions when a broad
region is too coarse for the validation question:

```bash
uv run indoeuropop structure-target-regions \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/qpadm-rerun/accepted-target-observations.csv \
  --structure-region central_europe \
  --structured-targets-out results/qpadm-rerun/central-europe-structured-targets.csv \
  --structured-config-out results/qpadm-rerun/central-europe-structured-comparison.toml
```

The generated config splits selected parent initial counts evenly across the
target-aligned child regions and copies parent pulses and parameter overrides
to those children. That is an infrastructure scaffold for reviewing structure;
it is not evidence that those child regions have distinct historical dynamics
until child-specific priors or overrides are curated.

Apply reviewed child-region overrides before rerunning comparison or
validation:

```bash
uv run indoeuropop apply-child-region-overrides \
  --config results/qpadm-rerun/central-europe-structured-comparison.toml \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides.toml \
  --overridden-config-out results/qpadm-rerun/central-europe-curated-comparison.toml
```

Override TOML files can replace a child region's starting counts, migration
pulses, and parameter tables:

```toml
[counts.central_europe__germany_tiefbrunn_cordedware_1]
local = 760
steppe = 42

[[migration_pulses]]
region = "central_europe__germany_tiefbrunn_cordedware_1"
start_bce = 2980
end_bce = 2450
annual_rate = 0.00014

[region_parameters.central_europe__germany_tiefbrunn_cordedware_1]
migration_rate = 0.0002

[source_parameters.central_europe__germany_tiefbrunn_cordedware_1.steppe]
reproductive_multiplier = 1.18
```

Migration pulses in the override file replace inherited pulses for the same
regions by default. Add `[options] replace_migration_pulses = false` to append
them instead.

The checked-in central-Europe override is a review candidate, not a final
historical prior. Its metadata sets Britain as the protected holdout and
records an explicit protected-fold tolerance of `0.03` RMSE for the current
validation gate.

Rerun validation after applying the curated override:

```bash
uv run indoeuropop validate-targets \
  --config results/qpadm-rerun/central-europe-curated-comparison.toml \
  --targets results/qpadm-rerun/central-europe-structured-targets.csv \
  --validation-field region \
  --validation-fit-csv results/qpadm-rerun/central-europe-curated-validation-fit.csv \
  --validation-report-md results/qpadm-rerun/central-europe-curated-validation-report.md \
  --manifest-json results/qpadm-rerun/central-europe-curated-validation-manifest.json \
  --fit-metric root_mean_squared_error
```

Review whether an override improved priority folds without degrading protected
folds beyond the committed tolerance:

```bash
uv run indoeuropop review-override-deltas \
  --baseline-validation-fit-csv results/qpadm-rerun/central-europe-structured-validation-fit.csv \
  --override-validation-fit-csv results/qpadm-rerun/central-europe-curated-validation-fit.csv \
  --priority-validation-value central_europe__germany_tiefbrunn_cordedware_1 \
  --priority-validation-value central_europe__germany_manchingoberstimm_bellbeaker \
  --protected-validation-value britain \
  --refinement-tolerance 0.03 \
  --override-delta-csv results/qpadm-rerun/central-europe-curated-override-delta.csv \
  --override-delta-report-md results/qpadm-rerun/central-europe-curated-override-delta.md \
  --manifest-json results/qpadm-rerun/central-europe-curated-override-delta-manifest.json \
  --fit-metric root_mean_squared_error
```

Explore a narrow one-factor sensitivity surface around the tracked child
override candidate:

```bash
uv run indoeuropop sweep-child-overrides \
  --config results/qpadm-rerun/central-europe-structured-comparison.toml \
  --targets results/qpadm-rerun/central-europe-structured-targets.csv \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides.toml \
  --priority-validation-value central_europe__germany_tiefbrunn_cordedware_1 \
  --priority-validation-value central_europe__germany_manchingoberstimm_bellbeaker \
  --protected-validation-value britain \
  --refinement-tolerance 0.03 \
  --override-sensitivity-csv results/qpadm-rerun/central-europe-child-override-sensitivity.csv \
  --override-sensitivity-report-md results/qpadm-rerun/central-europe-child-override-sensitivity.md \
  --manifest-json results/qpadm-rerun/central-europe-child-override-sensitivity-manifest.json \
  --fit-metric root_mean_squared_error
```

The default sensitivity grid evaluates the curated candidate plus one-at-a-time
changes to child-region counts (`0.9x`, `1.1x`), pulse rates (`0.85x`, `1.15x`),
pulse windows (`-50`, `+50` BCE years), and Steppe reproductive multipliers
(`0.95x`, `1.05x`). Rows are ranked by priority improvement while preserving
the protected Britain tolerance.

Run the second-stage count-by-reproduction interaction grid when the one-factor
surface suggests the Steppe reproductive multiplier is carrying the fit:

```bash
uv run indoeuropop sweep-child-override-interactions \
  --config results/qpadm-rerun/central-europe-structured-comparison.toml \
  --targets results/qpadm-rerun/central-europe-structured-targets.csv \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides.toml \
  --priority-validation-value central_europe__germany_tiefbrunn_cordedware_1 \
  --priority-validation-value central_europe__germany_manchingoberstimm_bellbeaker \
  --protected-validation-value britain \
  --refinement-tolerance 0.03 \
  --override-sensitivity-csv results/qpadm-rerun/central-europe-child-override-interactions.csv \
  --override-sensitivity-report-md results/qpadm-rerun/central-europe-child-override-interactions.md \
  --manifest-json results/qpadm-rerun/central-europe-child-override-interactions-manifest.json \
  --fit-metric root_mean_squared_error
```

The interaction grid varies Steppe counts (`0.9x`, `1.0x`, `1.1x`) and Steppe
reproductive multipliers (`0.9x`, `0.95x`, `1.0x`, `1.05x`) together, one child
region at a time. That keeps the search local and makes it easier to see
whether the preferred reproductive multiplier is stable or just compensating
for Steppe count assumptions.

The interaction-best file is now the active review candidate; the first curated
candidate remains as a superseded benchmark. Reproduce the promotion check by
comparing the active candidate head-to-head against that superseded file:

```bash
uv run indoeuropop apply-child-region-overrides \
  --config results/qpadm-rerun/central-europe-structured-comparison.toml \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides-interaction-best.toml \
  --overridden-config-out results/qpadm-rerun/central-europe-interaction-best-comparison.toml

uv run indoeuropop validate-targets \
  --config results/qpadm-rerun/central-europe-interaction-best-comparison.toml \
  --targets results/qpadm-rerun/central-europe-structured-targets.csv \
  --validation-field region \
  --validation-fit-csv results/qpadm-rerun/central-europe-interaction-best-validation-fit.csv \
  --validation-report-md results/qpadm-rerun/central-europe-interaction-best-validation-report.md \
  --manifest-json results/qpadm-rerun/central-europe-interaction-best-validation-manifest.json \
  --fit-metric root_mean_squared_error

uv run indoeuropop review-override-deltas \
  --baseline-validation-fit-csv results/qpadm-rerun/central-europe-curated-validation-fit.csv \
  --override-validation-fit-csv results/qpadm-rerun/central-europe-interaction-best-validation-fit.csv \
  --priority-validation-value central_europe__germany_tiefbrunn_cordedware_1 \
  --priority-validation-value central_europe__germany_manchingoberstimm_bellbeaker \
  --protected-validation-value britain \
  --refinement-tolerance 0 \
  --override-delta-csv results/qpadm-rerun/central-europe-curated-vs-interaction-best-delta.csv \
  --override-delta-report-md results/qpadm-rerun/central-europe-curated-vs-interaction-best-delta.md \
  --manifest-json results/qpadm-rerun/central-europe-curated-vs-interaction-best-delta-manifest.json \
  --fit-metric root_mean_squared_error
```

The promotion decision is recorded in
`docs/central-europe-override-decision.md`. It treats the interaction-best file
as the current review candidate, not as final demographic inference.

Validate the promoted and superseded curation metadata directly from the CLI:

```bash
uv run indoeuropop validate-curation-decisions \
  --curation-decision-file curation/aadr-v66-central-europe-child-overrides.toml \
  --curation-decision-file curation/aadr-v66-central-europe-child-overrides-interaction-best.toml \
  --require-artifacts
```

Summarize the complete local real-data artifact state before starting another
modeling increment:

```bash
uv run indoeuropop refresh-real-pipeline
```

The refresh command reruns the accepted-target structural split, same-baseline
structured-pulse versus child-override head-to-head comparison, and readiness
report using the current standard project paths. It is the preferred way to
refresh generated Central Europe structural artifacts after target, curation, or
override metadata changes.

To inspect readiness without regenerating structural artifacts:

```bash
uv run indoeuropop review-pipeline-readiness \
  --readiness-report-md results/qpadm-rerun/real-pipeline-readiness.md
```

The readiness report is read-only. It checks the local data-source catalog,
required generated artifacts, diagnostics-to-CSV count consistency, and strict
curation-decision artifact validation, including the same-baseline head-to-head
report manifest for the active central-Europe override. A ready report means
the current accepted-target pipeline is coherent enough for the next modeling
increment; it does not make the demographic interpretation final.

Run the first bounded inference scaffold over accepted targets:

```bash
uv run indoeuropop infer-target-parameters \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/qpadm-rerun/accepted-target-observations.csv \
  --fit-metric root_mean_squared_error \
  --acceptance-count 6 \
  --posterior-samples-csv results/qpadm-rerun/abc-accepted-samples.csv \
  --posterior-summary-csv results/qpadm-rerun/abc-posterior-summary.csv \
  --inference-report-md results/qpadm-rerun/abc-inference-report.md \
  --posterior-predictive-csv results/qpadm-rerun/abc-posterior-predictive.csv \
  --posterior-predictive-report-md results/qpadm-rerun/abc-posterior-predictive.md \
  --posterior-predictive-plot results/qpadm-rerun/abc-posterior-predictive.png \
  --holdout-targets results/qpadm-rerun/baseline-target-observations.csv \
  --holdout-posterior-predictive-csv results/qpadm-rerun/abc-holdout-posterior-predictive.csv \
  --holdout-posterior-predictive-report-md results/qpadm-rerun/abc-holdout-posterior-predictive.md \
  --holdout-posterior-predictive-plot results/qpadm-rerun/abc-holdout-posterior-predictive.png \
  --manifest-json results/qpadm-rerun/abc-inference-manifest.json
```

This is an ABC-style rejection baseline: it reruns the configured deterministic
sweep, ranks samples against target observations, retains a bounded subset, and
writes accepted sample, parameter-summary, and posterior predictive diagnostic
artifacts. The optional holdout target file is a separate diagnostic comparison
surface; it should be interpreted as a model-checking aid rather than a formal
claim of out-of-sample predictive validity unless the target split was designed
before inspection. Treat the command as an auditable starting point for
inference tooling, not as calibrated posterior evidence.

Run the sequential calibration scaffold once the accepted-target baseline is
ready:

```bash
uv run indoeuropop infer-target-parameters-smc \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/qpadm-rerun/accepted-target-observations.csv \
  --fit-metric root_mean_squared_error \
  --acceptance-count 6 \
  --smc-generations 3 \
  --smc-sample-count 30 \
  --smc-generations-csv results/qpadm-rerun/abc-smc-generations.csv \
  --posterior-samples-csv results/qpadm-rerun/abc-smc-final-samples.csv \
  --posterior-summary-csv results/qpadm-rerun/abc-smc-final-summary.csv \
  --inference-report-md results/qpadm-rerun/abc-smc-report.md \
  --posterior-predictive-csv results/qpadm-rerun/abc-smc-posterior-predictive.csv \
  --posterior-predictive-report-md results/qpadm-rerun/abc-smc-posterior-predictive.md \
  --posterior-predictive-plot results/qpadm-rerun/abc-smc-posterior-predictive.png \
  --manifest-json results/qpadm-rerun/abc-smc-manifest.json
```

This command reruns deterministic scored sweeps across sequential generations,
uses accepted-sample quantiles to narrow parameter ranges, and writes generation
thresholds plus final posterior-style diagnostics. It is an auditable
ABC-SMC-style calibration layer, not a fully weighted particle posterior; use
it to decide which parameter ranges deserve richer sampling or emulator work.

Evaluate a focused structural candidate for the early Central Europe residual:

```bash
uv run indoeuropop evaluate-migration-pulse-candidate \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/qpadm-rerun/accepted-target-observations.csv \
  --fit-metric root_mean_squared_error \
  --acceptance-count 6 \
  --pulse-candidate-name central-europe-early-pulse \
  --pulse-region central_europe \
  --pulse-start-bce 3000 \
  --pulse-end-bce 2600 \
  --pulse-annual-rate 0.00005 \
  --candidate-config-out results/qpadm-rerun/central-europe-early-pulse-comparison.toml \
  --posterior-predictive-report-md results/qpadm-rerun/central-europe-early-pulse-baseline.md \
  --posterior-predictive-plot results/qpadm-rerun/central-europe-early-pulse-baseline.png \
  --candidate-posterior-predictive-report-md results/qpadm-rerun/central-europe-early-pulse-candidate.md \
  --candidate-posterior-predictive-plot results/qpadm-rerun/central-europe-early-pulse-candidate.png \
  --candidate-comparison-report-md results/qpadm-rerun/central-europe-early-pulse-comparison.md \
  --manifest-json results/qpadm-rerun/central-europe-early-pulse-manifest.json
```

This appends one time-localized migration pulse and compares baseline versus
candidate posterior predictive diagnostics. It is meant to test whether the
Tiefbrunn-era mismatch looks like a transition-timing problem; it should not be
promoted without target chronology and qpAdm-review support.

Compare the promoted child-region override candidate against that broad-pulse
diagnostic:

```bash
uv run indoeuropop evaluate-child-region-candidate \
  --config results/qpadm-rerun/central-europe-structured-comparison.toml \
  --targets results/qpadm-rerun/central-europe-structured-targets.csv \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides-interaction-best.toml \
  --fit-metric root_mean_squared_error \
  --acceptance-count 6 \
  --child-region-candidate-name central-europe-child-interaction-best \
  --candidate-config-out results/qpadm-rerun/central-europe-child-interaction-best-posterior-comparison.toml \
  --posterior-predictive-report-md results/qpadm-rerun/central-europe-child-interaction-best-baseline.md \
  --posterior-predictive-plot results/qpadm-rerun/central-europe-child-interaction-best-baseline.png \
  --candidate-posterior-predictive-report-md results/qpadm-rerun/central-europe-child-interaction-best-candidate.md \
  --candidate-posterior-predictive-plot results/qpadm-rerun/central-europe-child-interaction-best-candidate.png \
  --candidate-comparison-report-md results/qpadm-rerun/central-europe-child-interaction-best-vs-broad-pulse.md \
  --reference-comparison-manifest results/qpadm-rerun/central-europe-early-pulse-manifest.json \
  --focus-observation-index 9 \
  --manifest-json results/qpadm-rerun/central-europe-child-interaction-best-manifest.json
```

This run uses the structured Central Europe target split and applies the
interaction-best override candidate. The reference manifest lets the report
compare improvement deltas with the broad-pulse diagnostic while warning that
the two deltas use different baselines.

Run the same-baseline promotion gate when comparing the structured broad-pulse
and child-region hypotheses directly:

```bash
uv run indoeuropop compare-structured-candidates \
  --config results/qpadm-rerun/central-europe-structured-comparison.toml \
  --targets results/qpadm-rerun/central-europe-structured-targets.csv \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides-interaction-best.toml \
  --fit-metric root_mean_squared_error \
  --acceptance-count 6 \
  --structured-pulse-candidate-name central-europe-structured-broad-pulse \
  --structured-pulse-region-prefix central_europe__ \
  --structured-pulse-start-bce 3000 \
  --structured-pulse-end-bce 2600 \
  --structured-pulse-annual-rate 0.00005 \
  --child-region-candidate-name central-europe-child-interaction-best \
  --structured-pulse-config-out results/qpadm-rerun/central-europe-structured-broad-pulse-comparison.toml \
  --child-candidate-config-out results/qpadm-rerun/central-europe-child-interaction-best-head-to-head.toml \
  --posterior-predictive-report-md results/qpadm-rerun/central-europe-head-to-head-baseline.md \
  --posterior-predictive-plot results/qpadm-rerun/central-europe-head-to-head-baseline.png \
  --structured-pulse-posterior-predictive-report-md results/qpadm-rerun/central-europe-structured-broad-pulse.md \
  --structured-pulse-posterior-predictive-plot results/qpadm-rerun/central-europe-structured-broad-pulse.png \
  --child-posterior-predictive-report-md results/qpadm-rerun/central-europe-child-interaction-best-head-to-head.md \
  --child-posterior-predictive-plot results/qpadm-rerun/central-europe-child-interaction-best-head-to-head.png \
  --head-to-head-report-md results/qpadm-rerun/central-europe-structured-pulse-vs-child-head-to-head.md \
  --focus-observation-index 9 \
  --manifest-json results/qpadm-rerun/central-europe-structured-pulse-vs-child-head-to-head-manifest.json
```

This direct gate keeps the structured baseline fixed, copies the broad pulse to
matching `central_europe__*` child regions, and reports candidate-minus-baseline
posterior predictive deltas for both hypotheses.

Run the SMC-calibrated version of the same structural comparison with Britain
held out from calibration:

```bash
uv run indoeuropop compare-structured-candidates-smc \
  --config results/qpadm-rerun/central-europe-structured-comparison.toml \
  --targets results/qpadm-rerun/central-europe-structured-targets.csv \
  --validation-field region \
  --validation-value britain \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides-interaction-best.toml \
  --fit-metric root_mean_squared_error \
  --acceptance-count 6 \
  --smc-generations 3 \
  --smc-sample-count 30 \
  --structured-pulse-candidate-name central-europe-structured-broad-pulse \
  --structured-pulse-region-prefix central_europe__ \
  --structured-pulse-start-bce 3000 \
  --structured-pulse-end-bce 2600 \
  --structured-pulse-annual-rate 0.00005 \
  --child-region-candidate-name central-europe-child-interaction-best \
  --smc-comparison-output-dir results/qpadm-rerun/structured-smc
```

This command calibrates the structured baseline, structured broad-pulse, and
child-override models with the same SMC controls. `--validation-value britain`
uses the structured target file itself to split calibration and holdout rows:
Britain is held out while the target-aligned Central Europe rows drive
calibration. The output directory contains per-model SMC diagnostics, holdout
posterior predictive reports, a structural head-to-head report, and a manifest.

Run the multi-fold structural SMC validation before promoting either structural
candidate:

```bash
uv run indoeuropop validate-structured-candidates-smc \
  --config results/qpadm-rerun/central-europe-structured-comparison.toml \
  --targets results/qpadm-rerun/central-europe-structured-targets.csv \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides-interaction-best.toml \
  --fit-metric root_mean_squared_error \
  --acceptance-count 6 \
  --smc-generations 3 \
  --smc-sample-count 30 \
  --structured-pulse-candidate-name central-europe-structured-broad-pulse \
  --structured-pulse-region-prefix central_europe__ \
  --structured-pulse-start-bce 3000 \
  --structured-pulse-end-bce 2600 \
  --structured-pulse-annual-rate 0.00005 \
  --child-region-candidate-name central-europe-child-interaction-best \
  --smc-validation-output-dir results/qpadm-rerun/structured-smc-validation
```

By default, this command builds pre-registered folds from the target file and
override review metadata: Britain/protected holdouts, priority child regions,
all `central_europe__*` child regions, and coarse chronology bands. It writes
per-fold SMC bundles plus a top-level validation CSV, Markdown report, and
manifest summarizing calibration/holdout preference stability.

When validation reports calibration/holdout candidate disagreements, join those
folds back to the held-out target metadata and posterior predictive residuals:

```bash
uv run indoeuropop review-structured-smc-disagreements \
  --smc-validation-summary-csv results/qpadm-rerun/structured-smc-validation/structural-smc-validation-summary.csv \
  --smc-validation-output-dir results/qpadm-rerun/structured-smc-validation \
  --smc-disagreement-csv results/qpadm-rerun/structured-smc-validation/structural-smc-disagreement-diagnostics.csv \
  --smc-disagreement-report-md results/qpadm-rerun/structured-smc-validation/structural-smc-disagreement-diagnostics.md
```

Positive `child_minus_structured_pulse_abs_residual_delta` values mean the
child-override candidate fit that held-out target worse than the broad
structured-pulse candidate. Treat this report as a curation and residual audit
surface before changing the structural model.

Batch-audit those disagreement targets against the sample-level AADR metadata
and qpAdm estimate inputs:

```bash
uv run indoeuropop audit-structured-smc-disagreement-targets \
  --smc-disagreement-csv results/qpadm-rerun/structured-smc-validation/structural-smc-disagreement-diagnostics.csv \
  --target-curation results/qpadm-rerun/aadr-target-curation.csv \
  --sample-metadata results/qpadm-rerun/aadr-target-sample-metadata.csv \
  --ancestry-estimates results/qpadm-rerun/merged-sample-ancestry-estimates.csv \
  --disagreement-target-audit-csv results/qpadm-rerun/structured-smc-validation/structural-smc-disagreement-target-audit-samples.csv \
  --disagreement-target-audit-md results/qpadm-rerun/structured-smc-validation/structural-smc-disagreement-target-audit.md
```

This writes a target-level Markdown review plus a long-form sample CSV with
sample dates, sex labels, sites, publication keys, qpAdm estimates, standard
errors, p-values, and review flags such as `high_se`, `critical`, or
`out_of_window`.

Run the target-fragility sensitivity gate to remove disagreement targets with
sample-level fragility flags or repeated identical sample estimates, then rerun
only the validation folds that still have calibration and holdout rows:

```bash
uv run indoeuropop validate-structured-smc-target-fragility \
  --config results/qpadm-rerun/central-europe-structured-comparison.toml \
  --targets results/qpadm-rerun/central-europe-structured-targets.csv \
  --child-region-overrides curation/aadr-v66-central-europe-child-overrides-interaction-best.toml \
  --fit-metric root_mean_squared_error \
  --acceptance-count 6 \
  --smc-generations 3 \
  --smc-sample-count 30 \
  --structured-pulse-candidate-name central-europe-structured-broad-pulse \
  --structured-pulse-region-prefix central_europe__ \
  --structured-pulse-start-bce 3000 \
  --structured-pulse-end-bce 2600 \
  --structured-pulse-annual-rate 0.00005 \
  --child-region-candidate-name central-europe-child-interaction-best \
  --target-fragility-audit-csv results/qpadm-rerun/structured-smc-validation/structural-smc-disagreement-target-audit-samples.csv \
  --target-fragility-output-dir results/qpadm-rerun/structured-smc-fragility-gate
```

The gate writes `filtered-targets.csv`, `target-fragility-decisions.csv`, a
Markdown summary, and a nested multi-fold validation rerun under `validation/`.
By default it excludes `high_se`, `critical`, `missing_metadata`,
`missing_estimate`, and `out_of_window` flags plus repeated identical estimates.

Review any remaining disagreement folds with uncertainty-normalized z-scores
before treating raw residual differences as structural evidence:

```bash
uv run indoeuropop review-structured-smc-uncertainty \
  --smc-validation-summary-csv results/qpadm-rerun/structured-smc-fragility-gate/validation/structural-smc-validation-summary.csv \
  --smc-validation-output-dir results/qpadm-rerun/structured-smc-fragility-gate/validation \
  --smc-uncertainty-csv results/qpadm-rerun/structured-smc-fragility-gate/structural-smc-uncertainty.csv \
  --smc-uncertainty-report-md results/qpadm-rerun/structured-smc-fragility-gate/structural-smc-uncertainty.md
```

The default materiality threshold treats child-minus-pulse chi-square deltas
below `1.0` as `uncertainty_tie`, which is useful when broad target uncertainty
dominates small candidate residual differences.

Compare validation-guided narrowed and expanded parameter ranges against the
current grid:

```bash
uv run indoeuropop refine-target-parameters \
  --config curation/aadr-v66-western-europe-comparison.toml \
  --targets results/qpadm-rerun/accepted-target-observations.csv \
  --priority-validation-value central_europe \
  --protected-validation-value britain \
  --refinement-summary-csv results/qpadm-rerun/accepted-region-refinement-summary.csv \
  --refinement-ranges-csv results/qpadm-rerun/accepted-region-refinement-ranges.csv \
  --refinement-report-md results/qpadm-rerun/accepted-region-refinement-report.md \
  --manifest-json results/qpadm-rerun/accepted-region-refinement-manifest.json \
  --fit-metric root_mean_squared_error
```

For the current accepted targets, the narrowed grid improves central Europe by
RMSE `0.010448` but degrades Britain by `0.019410`; the expanded grid improves
central Europe by `0.007753` but degrades Britain by `0.061346`. A
leave-one-requested-group refinement focused on
`Germany_Tiefbrunn_CordedWare-1` reduces that group's RMSE by `0.031027` in the
expanded grid, but degrades the protected Britain groups by up to `0.168369`.

Review the best-run residuals:

```bash
uv run indoeuropop review-target-residuals \
  --target-residuals results/real-aadr-comparison/target-residuals.csv \
  --target-diagnostics-json results/real-aadr-comparison/aadr-target-diagnostics.json \
  --target-review-md results/real-aadr-comparison/target-residual-review.md
```

Audit the top residual's curation and qpAdm estimate evidence:

```bash
uv run indoeuropop audit-target-curation \
  --target-residuals results/real-aadr-comparison/target-residuals.csv \
  --target-curation results/real-aadr-comparison/aadr-target-curation.csv \
  --sample-metadata results/real-aadr-comparison/aadr-target-sample-metadata.csv \
  --ancestry-estimates results/real-aadr-comparison/sample-ancestry-estimates.csv \
  --target-audit-md results/real-aadr-comparison/stkr-straubing-curation-audit.md
```

## Package Layout

```text
src/indoeuropop/
  __init__.py        public exports and legacy module import aliases
  _api.py            top-level `from indoeuropop import ...` export surface
  analysis/          diagnostics, fitting, validation, summaries, emulators
  data/              AADR loading, source catalogs, estimates, target building
  models/            shared state types plus age and sex structure helpers
  orchestration/     CLI commands, experiment manifests, sweeps, workflows
  reporting/         provenance, reproducibility, CSV exports, plots
  simulation/        config loading, event schedules, epidemic and run engines
docs/
  aadr-group-suggestions.md
  aadr-loading.md
  aadr-target-inputs.md
  alternative-implementation-evaluation.md
  experiment-manifests.md
  project-plan.md    implementation roadmap and scientific guardrails
  qpadm-estimates.md
  qpadm-workflow.md
  real-target-workflow.md
  source-downloads.md
  sweep-workflows.md
  target-comparison-workflow.md
  target-data-schema.md
  target-residual-review.md
  workflow-api.md
examples/
  sample-ancestry-estimates.example.csv
  sweep.example.toml
  sweep-targets.example.csv
  target-observations.example.csv
curation/
  aadr-v66-western-europe-comparison.toml
  aadr-v66-western-europe-qpadm-targets.tsv
scripts/
  run_qpadm.R        external ADMIXTOOLS 2 runner
tests/
  test_*.py          100% coverage tests for logic-bearing modules
```

Root-level `/data/` and `/results/` are ignored for local raw data, f2 caches,
and generated artifacts. The package code under `src/indoeuropop/data/` is
tracked normally.

## Current Capabilities

- Construct validated population states with region/source counts.
- Derive ancestry proportions from source counts.
- Represent and project age-structured counts, then collapse them back to
  source-count states for existing diagnostics and plots.
- Represent sex-structured counts and estimate expected newborn source
  contributions under explicit sex-specific reproductive weights.
- Represent susceptible, infected, recovered, and deceased counts for explicit
  epidemic transmission experiments.
- Run a small deterministic mean-field scenario.
- Run a seeded tau-leap stochastic scenario for smoke testing.
- Load the same inputs from TOML.
- Run configured deterministic or tau-leap scenarios through reusable workflow
  helpers outside the CLI.
- Materialize optional plot, provenance CSV, and manifest JSON outputs through
  reusable workflow helpers.
- Layer time-bounded migration pulses and climate/epidemic forcing windows over
  base parameters.
- Override shared region rates and source-specific rates through parameter
  tables.
- Run seeded Latin-hypercube parameter sweeps and summarize trajectories.
- Export sweep summaries and sensitivity diagnostics to stable CSV tables.
- Load deterministic sweep specifications from TOML and run them from the CLI.
- Run deterministic sweep workflows that can write sweep CSVs, sensitivity CSVs,
  target-fit CSVs, and manifest JSON files.
- Convert trajectory summaries into named, scaled summary-statistic vectors.
- Analyze sweep sensitivity with lightweight correlation diagnostics.
- Score simulations and deterministic sweeps against target observations.
- Run a target-comparison workflow that writes ranked fits, best-run residuals,
  overlay plots, and a checksummed manifest.
- Run held-out target-validation workflows by region or target-note metadata
  key, with ranked validation rows, Markdown summaries, and manifests.
- Compare baseline, narrowed, and expanded validation-guided parameter grids
  while tracking priority improvements and protected holdout degradation.
- Generate Markdown target-residual review reports from comparison artifacts.
- Split targets into calibration and validation sets for held-out fit checks.
- Compare deterministic and tau-leap ancestry trajectories for debugging.
- Validate simulation outputs for time-order, label, extinction, and growth
  diagnostics.
- Label output values as simulated, observed, synthetic, derived, or future
  inferred records for reporting.
- Export provenance and diagnostic records to rectangular CSV tables.
- Fingerprint simulation results and sweep outputs with canonical SHA-256
  digests.
- Bundle run artifacts and fingerprints into experiment manifests that can be
  converted to provenance records.
- Prepare sweep runs as parameter and summary matrices for future emulator
  experiments.
- Compare future emulator predictions against explicit simulator summaries.
- Write CLI provenance reports for demo simulations.
- Write CLI experiment manifests with artifact checksums and simulation
  fingerprints.
- Load synthetic or published target-observation CSV files.
- Build target-observation CSVs from sample metadata, curation records, and
  sample ancestry estimates.
- Filter target-pipeline inputs to rows with complete valid ancestry estimates
  before aggregation.
- Register local and planned external data sources with citations and optional
  SHA-256 checksums.
- Download or copy cataloged source files into a raw-data cache with optional
  checksum verification and a manifest CSV.
- Load local AADR annotation files into the project sample metadata schema.
- Suggest reviewable AADR group-selection files from local annotation
  coordinates, dates, and group labels.
- Prepare AADR group selections as modeled-region sample metadata and
  target-curation inputs for later ancestry-estimate aggregation.
- Load synthetic or published sample metadata rows without aggregating them into
  ancestry targets.
- Load sample-level ancestry estimates before target aggregation.
- Convert externally computed qpAdm-style estimate tables into the sample
  ancestry estimate schema.
- Plan external ADMIXTOOLS qpAdm runs with resolved genotype prefixes, a
  committed target seed, and an auditable JSON manifest.
- Plan qpAdm reruns from reviewed target decisions, grouped by failure reason
  with JSON and annotated AADR group-selection TSV outputs.
- Merge external qpAdm rerun outputs with baseline estimates and compare
  target availability before updating reviewed target decisions.
- Run an exploratory multi-region comparison sweep against retained AADR v66
  western-Europe qpAdm target observations.
- Audit residual outliers against curation rows, sample metadata, and qpAdm
  estimate evidence before changing simulator parameters.
- Apply reviewed target-decision files to defer excluded, split, or rerun-pending
  targets from observation builds without deleting their curation evidence.
- Validate active/superseded curation-decision metadata and linked local
  artifacts from the CLI.
- Document target curation windows, sample selections, and methods before
  creating target observations.
- Compare simulated ancestry trajectories to target observations.
- Plot ancestry and population-total trajectories without requiring a display.

## Not Yet Included

- Automated ancient-DNA genotype processing.
- Poseidon, SLiM, msprime, fully weighted ABC-SMC, or predictive emulator
  integration.
- Regionally calibrated parameter priors.
- Scholarly claims about fitted causal mechanisms.

Those pieces belong in later phases after the state model, tests, and
documentation are stable.
