# Alternative Implementation Evaluation

The project at `/Users/jmcummings/Claude/Projects/indoeuropop_claude` was
reviewed as an alternate response to the same prompt. Because it is user-owned
code and data, compatible pieces were fair to incorporate directly.

## Incorporated

- A tolerant qpAdm-table conversion concept, adapted into
  `indoeuropop.data.qpadm_estimates` so externally computed ancestry estimates can
  enter the existing target-data pipeline.
- A coordinate/date-based AADR group-suggestion concept, adapted into
  `indoeuropop.data.aadr_groups` so local AADR releases can produce reviewable
  group-selection candidates instead of relying only on hand-written labels.
- Data-oriented CLI separation into `indoeuropop.orchestration.data_cli`, keeping the main
  CLI small while exposing AADR loading, AADR target preparation, group
  suggestions, source downloads, and qpAdm conversion through one entry point.

## Not Copied Wholesale

The current repository already has stricter typed dataclasses, provenance,
manifest, sweep, target-aggregation, test, and documentation scaffolds. The
alternate implementation's broader inference and analysis ideas remain useful
conceptually, but copying them now would duplicate surfaces that already exist
or expand the scope beyond a tested target-data bridge.

The alternate repository also contains local AADR data. Those data remain
external to this package and are referenced by path in examples and commands.
Large ancient-DNA releases should stay outside version control unless a later
data-management decision says otherwise.

## Future Candidates

- More detailed haplogroup or lineage summary helpers, if the project adds
  lineage-specific target data.
- ADMIXTOOLS workflow documentation or scripts, if the repository starts
  orchestrating qpAdm model runs instead of only accepting external estimates.
- Additional spatial priors, if the coarse region-box suggestion layer proves
  too blunt during target review.

